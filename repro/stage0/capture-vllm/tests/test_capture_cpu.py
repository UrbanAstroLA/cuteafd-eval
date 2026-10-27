#!/usr/bin/env python3
"""CPU-only tests of the glm53_capture plugin against the REAL vLLM v0.9.2
`PromptLogprobsWorker.compute_prompt_logprobs` from the image.

Run inside the image, no GPU, no network:
  docker run --rm --network none --entrypoint python3 \
    -v <capture-vllm>:/cap:ro -v <kld>/plugin:/old-plugin:ro \
    -v <runs>/kld/panel-final:/kld-panel:ro \
    sha256:ea0430aa... /cap/tests/test_capture_cpu.py

Only the two Triton helpers that the real method calls
(`get_prompt_logprobs_token_ids`, `compute_topk_scores`) are replaced by CPU
torch equivalents written from the kernels' source.  vLLM's own control flow -
the 1024-row slicing of hidden_states[:num_tokens], the chunked/final row
selection, the accumulation across steps - is the image's code.

Synthetic logits: hidden state row = (request code, position); logits_fn maps it
to a deterministic BF16 row, so the expected log-softmax of every window row is
known independently of any batch layout.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from types import SimpleNamespace

import numpy as np
import torch

sys.path.insert(0, os.environ.get("CAP_PLUGIN", "/cap/plugin"))
from vllm.v1.worker.gpu.sample import prompt_logprob as pl  # noqa: E402
from vllm.v1.outputs import LogprobsTensors  # noqa: E402

RESULTS = []


# ------------------------------------------------- CPU stand-ins for Triton

def cpu_get_prompt_logprobs_token_ids(num_tokens, query_start_loc, idx_mapping,
                                      num_computed_tokens, all_token_ids):
    """_prompt_logprobs_token_ids_kernel: target_pos = computed + 1 + block."""
    out = torch.zeros(num_tokens, dtype=torch.int64)
    qsl = query_start_loc.tolist()
    for b, r in enumerate(idx_mapping.tolist()):
        qs, qe = qsl[b], qsl[b + 1]
        c = int(num_computed_tokens[r])
        n = qe - qs
        out[qs:qe] = all_token_ids[r, c + 1:c + 1 + n].to(torch.int64)
    return out


def cpu_compute_topk_scores(logits, num_logprobs, sampled_token_ids, *a, logits_mode=False, **k):
    """compute_topk_scores fast path + _topk_log_softmax_kernel / _ranks_kernel (FP32)."""
    ids = sampled_token_ids.unsqueeze(-1)
    if num_logprobs > 0:
        ids = torch.cat((ids, torch.topk(logits, num_logprobs, dim=-1).indices), dim=1)
    lf = logits.float()
    if logits_mode:
        scores = lf.gather(-1, ids)
    else:
        lse = torch.logsumexp(lf, dim=-1, keepdim=True)
        scores = lf.gather(-1, ids) - lse
    x = logits.gather(-1, sampled_token_ids.unsqueeze(-1))
    ranks = (logits >= x).sum(-1).to(torch.int32)
    return LogprobsTensors(ids, scores, ranks)


pl.get_prompt_logprobs_token_ids = cpu_get_prompt_logprobs_token_ids
pl.compute_topk_scores = cpu_compute_topk_scores
ORIG_METHOD = pl.PromptLogprobsWorker.compute_prompt_logprobs


# ------------------------------------------------------- synthetic model

class Model:
    def __init__(self, vocab):
        self.vocab = vocab
        g = torch.Generator().manual_seed(1234)
        self.freq = torch.rand(vocab, generator=g, dtype=torch.float64) * 3 + 0.1
        self.phase = torch.rand(vocab, generator=g, dtype=torch.float64) * 6.28

    def logits_rows(self, code_pos):
        """[n,2] (code, pos) -> BF16 logits [n, vocab]."""
        c = code_pos[:, 0:1].to(torch.float64)
        p = code_pos[:, 1:2].to(torch.float64)
        z = 6.0 * torch.sin(self.freq * (0.013 * p + 0.71 * c) + self.phase) \
            + 2.0 * torch.cos(0.37 * p + c)
        return z.to(torch.bfloat16)

    def logits_fn(self, hs):
        return self.logits_rows(hs)

    def expected(self, code, rows):
        cp = torch.stack([torch.full((len(rows),), float(code)),
                          torch.as_tensor(rows, dtype=torch.float64)], 1)
        z = self.logits_rows(cp).to(torch.float64)
        return (z - torch.logsumexp(z, -1, keepdim=True)).to(torch.float32).numpy()


class Engine:
    """Minimal stand-in for the V2 runner's request state + batch building."""

    def __init__(self, model, max_reqs=32, max_len=20000, decode_query_len=4):
        self.model = model
        self.max_reqs = max_reqs
        self.all_token_ids = torch.zeros(max_reqs, max_len, dtype=torch.int32)
        self.num_computed = torch.zeros(max_reqs, dtype=torch.int32)
        self.prompt_len = np.zeros(max_reqs, dtype=np.int32)
        self.reqs = {}
        self.workers = []
        self.decode_query_len = decode_query_len

    def add(self, req_id, tokens, prompt_logprobs=None, computed=0):
        r = len(self.reqs)
        t = np.asarray(tokens, dtype=np.int32)
        self.all_token_ids[r, :t.size] = torch.from_numpy(t)
        self.prompt_len[r] = t.size
        self.num_computed[r] = computed
        self.reqs[req_id] = SimpleNamespace(idx=r, tokens=t, code=r + 1, plp=prompt_logprobs)
        for w in self.workers:
            w.add_request(req_id, r, SimpleNamespace(prompt_logprobs=prompt_logprobs))

    def step(self, sched, workers, drafts=None):
        """sched: {req_id: n_tokens}. Orders the batch like sort_batch_req_ids."""
        drafts = drafts or {}
        key = lambda q: (not drafts.get(q), sched[q] != self.decode_query_len, sched[q])
        order = sorted(sched, key=key)
        n = [sched[q] for q in order]
        qsl = np.concatenate(([0], np.cumsum(n))).astype(np.int32)
        idx = np.array([self.reqs[q].idx for q in order], dtype=np.int32)
        comp = np.array([int(self.num_computed[self.reqs[q].idx]) for q in order], dtype=np.int32)
        plen = np.array([self.prompt_len[self.reqs[q].idx] for q in order], dtype=np.int32)
        # decode requests: computed past the prompt; prefill_len == prompt_len
        ib = SimpleNamespace(
            req_ids=list(order), num_reqs=len(order),
            idx_mapping=torch.from_numpy(idx), idx_mapping_np=idx,
            num_scheduled_tokens=np.array(n, dtype=np.int32), num_tokens=int(qsl[-1]),
            query_start_loc=torch.from_numpy(qsl), query_start_loc_np=qsl,
            num_computed_prefill_tokens_np=np.minimum(comp, plen),
            prefill_len_np=plen.copy(),
            num_draft_tokens_per_req=np.array([len(drafts.get(q, [])) for q in order], dtype=np.int32),
        )
        hs = torch.zeros(ib.num_tokens, 2, dtype=torch.float64)
        for b, q in enumerate(order):
            R = self.reqs[q]
            c = comp[b]
            hs[qsl[b]:qsl[b + 1], 0] = R.code
            hs[qsl[b]:qsl[b + 1], 1] = torch.arange(c, c + n[b], dtype=torch.float64)
        outs = []
        for w in workers:
            outs.append(w.compute_prompt_logprobs(self.model.logits_fn, hs, ib,
                                                   self.all_token_ids, self.num_computed,
                                                   self.prompt_len))
        for q in order:
            self.num_computed[self.reqs[q].idx] += sched[q]
        return outs, ib


# ------------------------------------------------------------- utilities

def write_entry(reg, set_, wid, tokens, rows):
    d = os.path.join(reg, set_)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{wid}.json"), "w") as f:
        json.dump({"window_id": wid, "tokens": [int(x) for x in tokens], "rows": rows}, f)


def fresh_plugin(vocab, reg, out):
    """(Re)arm the plugin around the real method with a clean state."""
    import glm53_capture_plugin as cap
    pl.PromptLogprobsWorker.compute_prompt_logprobs = ORIG_METHOD
    os.environ.update({"GLM53_CAP_ENABLE": "1", "GLM53_CAP_REGISTRY": reg,
                       "GLM53_CAP_OUT": out, "GLM53_CAP_VOCAB": str(vocab),
                       "GLM53_CAP_HOST_THREADS": "4"})
    cap._tp_rank = lambda: 0
    cap.register()
    assert pl.PromptLogprobsWorker.compute_prompt_logprobs is cap._patched_compute_prompt_logprobs
    return cap


class Unpatched(pl.PromptLogprobsWorker):
    """Same class, original method: the reference for 'outputs unchanged'."""
    compute_prompt_logprobs = ORIG_METHOD


def same_results(a, b):
    if a.keys() != b.keys():
        return False
    for k in a:
        for x, y in zip(a[k][:3], b[k][:3]):
            if not torch.equal(x, y):
                return False
    return True


def check_dump(model, out, set_, wid, code, tokens, rows, n_steps=None):
    from glm53_capture_plugin import core
    p = os.path.join(out, set_, f"{wid}.safetensors")
    rec = json.load(open(p + ".receipt.json"))
    t, meta = core.read_safetensors(p)
    exp = model.expected(code, rows)
    sha = core.tokens_sha256(tokens)
    errs = []
    if not rec["complete"]:
        errs.append(f"receipt incomplete: {rec['errors']}")
    if t["logprobs"].shape != (len(rows), model.vocab):
        errs.append(f"shape {t['logprobs'].shape}")
    if not np.array_equal(np.asarray(t["rows"]), np.asarray(rows, dtype=np.int32)):
        errs.append("rows tensor mismatch")
    if bytes(np.asarray(t["tokens_sha256"])).hex() != sha or meta.get("tokens_sha256") != sha:
        errs.append("tokens_sha256 mismatch")
    if not np.array_equal(np.asarray(t["logprobs"]), exp):
        bad = np.flatnonzero(~np.all(np.asarray(t["logprobs"]) == exp, axis=1))
        errs.append(f"{bad.size} rows differ from expected, first {bad[:5].tolist()}")
    cc = rec.get("chosen_check") or {}
    if cc.get("status") != "ok" or not cc.get("vllm_token_ids_match") or cc["max_abs_diff"] > 1e-5:
        errs.append(f"chosen check {cc}")
    if n_steps is not None and rec["n_steps"] != n_steps:
        errs.append(f"n_steps {rec['n_steps']} != {n_steps}")
    # independent reader: the safetensors library in the image
    try:
        from safetensors import safe_open
        with safe_open(p, "np") as f:
            lp = f.get_tensor("logprobs")
            if not np.array_equal(lp, exp):
                errs.append("safetensors lib read differs")
    except Exception as exc:
        errs.append(f"safetensors lib: {exc}")
    steps = [json.loads(x) for x in open(os.path.join(out, set_, f"{wid}.steps.jsonl"))]
    return errs, rec, steps


def run(name, fn):
    t0 = time.time()
    try:
        detail = fn()
        RESULTS.append((name, "PASS", detail, time.time() - t0))
    except AssertionError as e:
        RESULTS.append((name, "FAIL", str(e), time.time() - t0))
    except Exception:
        RESULTS.append((name, "ERROR", traceback.format_exc(), time.time() - t0))


def rand_tokens(n, vocab, seed):
    return np.random.default_rng(seed).integers(0, vocab, n).astype(np.int32)


# ------------------------------------------------------------------ tests

V = 2048


def setup(vocab=V):
    tmp = tempfile.mkdtemp(prefix="captest-")
    reg, out = os.path.join(tmp, "reg"), os.path.join(tmp, "out")
    os.makedirs(reg)
    os.makedirs(out)
    return tmp, reg, out, Model(vocab)


def t_decode_first():
    """Window prefill after 3 decode/verify requests (K3 => 4 rows each)."""
    tmp, reg, out, model = setup()
    w = rand_tokens(1500, V, 1)
    write_entry(reg, "pa", "w0", w, "all")
    cap = fresh_plugin(V, reg, out)
    eng = Engine(model)
    pw, uw = cap_worker(), Unpatched(32)
    eng.workers = [pw, uw]
    for i in range(3):
        eng.add(f"dec{i}", rand_tokens(300, V, 10 + i), None, computed=300 + 7 * i)
    eng.add("win", w, 0)
    outs, ib = eng.step({"dec0": 4, "dec1": 4, "dec2": 4, "win": 1500}, [pw, uw],
                        drafts={"dec0": [1, 2, 3], "dec1": [1, 2, 3], "dec2": [1, 2, 3]})
    assert ib.req_ids[-1] == "win" and ib.query_start_loc_np[3] == 12, ib.req_ids
    assert same_results(outs[0], outs[1]), "patched result differs from unpatched"
    errs, rec, steps = check_dump(model, out, "pa", "w0", eng.reqs["win"].code, w,
                                  np.arange(1499), n_steps=1)
    assert not errs, errs
    assert steps[0]["batch_rows"] == [12, 1512] and steps[0]["prompt_rows"] == [12, 1511], steps[0]
    assert len(steps[0]["others"]) == 3 and steps[0]["others"][0]["drafts"] == 3
    shutil.rmtree(tmp)
    return f"window at batch rows 12..1511, 1499 rows exact; chosen max diff {rec['chosen_check']['max_abs_diff']:.2e}"


def cap_worker():
    return pl.PromptLogprobsWorker(32)


def t_multi_prefill():
    """Two registered windows + one unregistered prompt-logprobs request +
    decodes in one batch; one window spans the 1024-row logits_fn boundary."""
    tmp, reg, out, model = setup()
    a, b, u = rand_tokens(700, V, 2), rand_tokens(900, V, 3), rand_tokens(400, V, 4)
    write_entry(reg, "pb", "A", a, {"last": 200})
    write_entry(reg, "pb", "B", b, list(range(0, 899, 3)))
    cap = fresh_plugin(V, reg, out)
    eng = Engine(model)
    pw, uw = cap_worker(), Unpatched(32)
    eng.workers = [pw, uw]
    eng.add("d0", rand_tokens(50, V, 20), None, computed=60)
    eng.add("A", a, 1)
    eng.add("U", u, 0)
    eng.add("B", b, 0)
    outs, ib = eng.step({"d0": 1, "A": 700, "U": 400, "B": 900}, [pw, uw])
    assert same_results(outs[0], outs[1])
    order = ib.req_ids
    qsl = ib.query_start_loc_np
    assert order == ["d0", "U", "A", "B"], order
    errs_a, ra, sa = check_dump(model, out, "pb", "A", eng.reqs["A"].code, a, np.arange(499, 699))
    errs_b, rb, sb = check_dump(model, out, "pb", "B", eng.reqs["B"].code, b, np.arange(0, 899, 3))
    assert not errs_a and not errs_b, (errs_a, errs_b)
    assert not os.path.exists(os.path.join(out, "default")), "unregistered request dumped"
    calls = sb[0]["logits_calls"]
    assert calls == [[0, 1024], [1024, 977]], calls
    shutil.rmtree(tmp)
    return f"order {order}, qsl {qsl.tolist()}; B spans logits calls {calls}; both exact"


def t_chunked():
    """4300-token window over 3 steps (2045+2045+210) with varying decode
    traffic; scored rows (last 512) straddle the 2nd/3rd chunk boundary."""
    tmp, reg, out, model = setup()
    w = rand_tokens(4300, V, 5)
    write_entry(reg, "q2", "long", w, {"last": 512})
    cap = fresh_plugin(V, reg, out)
    eng = Engine(model)
    pw, uw = cap_worker(), Unpatched(32)
    eng.workers = [pw, uw]
    for i in range(4):
        eng.add(f"d{i}", rand_tokens(100, V, 30 + i), None, computed=120 + i)
    eng.add("W", w, 0)
    plan = [({"W": 2045}, {}),
            ({"d0": 4, "d1": 4, "W": 2045}, {"d0": [1, 2, 3], "d1": [1, 2, 3]}),
            ({"d0": 4, "d1": 4, "d2": 4, "d3": 1, "W": 210}, {"d0": [1, 2, 3], "d1": [1, 2, 3], "d2": [1, 2, 3]})]
    for sched, dr in plan:
        outs, ib = eng.step(sched, [pw, uw], drafts=dr)
        assert same_results(outs[0], outs[1])
    errs, rec, steps = check_dump(model, out, "q2", "long", eng.reqs["W"].code, w,
                                  np.arange(3787, 4299), n_steps=3)
    assert not errs, errs
    got = [(s["chunk_start"], s["chunk_len"], s["rows_written"], s["batch_rows"][0]) for s in steps]
    assert got == [(0, 2045, 0, 0), (2045, 2045, 303, 8), (4090, 210, 209, 13)], got
    shutil.rmtree(tmp)
    return f"steps (start,len,rows,batch_off) {got}; 512 rows exact"


def t_full_vocab():
    """Real width 154,880; 600-row window behind 2 decodes; 256-row copy slices."""
    vocab = 154880
    tmp, reg, out, model = setup(vocab)
    w = rand_tokens(601, vocab, 6)
    write_entry(reg, "pa", "fv", w, "all")
    cap = fresh_plugin(vocab, reg, out)
    eng = Engine(model)
    pw = cap_worker()
    eng.workers = [pw]
    eng.add("d0", rand_tokens(10, vocab, 40), None, computed=11)
    eng.add("d1", rand_tokens(10, vocab, 41), None, computed=12)
    eng.add("W", w, 0)
    eng.step({"d0": 4, "d1": 4, "W": 601}, [pw], drafts={"d0": [1, 2, 3], "d1": [1, 2, 3]})
    errs, rec, _ = check_dump(model, out, "pa", "fv", eng.reqs["W"].code, w, np.arange(600))
    assert not errs, errs
    size = os.path.getsize(os.path.join(out, "pa", "fv.safetensors"))
    from glm53_capture_plugin import core
    hl = int.from_bytes(open(os.path.join(out, "pa", "fv.safetensors"), "rb").read(8), "little")
    assert (8 + hl) % 8 == 0 and size == 8 + hl + core.data_bytes(600, vocab), (hl, size)
    shutil.rmtree(tmp)
    return f"600 x 154880 exact; file {size} B; logits dtype {rec['logits_dtype']}"


def t_guards():
    """Non-zero first chunk refused; unregistered/plain steps untouched;
    registry reload picks up a new file; duplicate in-flight window refused;
    stale staging file refused."""
    tmp, reg, out, model = setup()
    w1, w2 = rand_tokens(300, V, 7), rand_tokens(320, V, 8)
    write_entry(reg, "s", "w1", w1, "all")
    cap = fresh_plugin(V, reg, out)
    eng = Engine(model)
    pw = cap_worker()
    eng.workers = [pw]
    # (a) plain decode step with no prompt-logprobs request: no files at all
    eng.add("d", rand_tokens(20, V, 50), None, computed=25)
    eng.step({"d": 1}, [pw])
    assert not os.path.exists(os.path.join(out, "registry-status.json")), "touched fs on plain step"
    # (b) first chunk at 100 (prefix-cache-like) -> refused with error file
    eng.add("late", w1, 0, computed=100)
    eng.step({"late": 200}, [pw])
    errf = os.path.join(out, "s", "w1.error.jsonl")
    assert os.path.exists(errf) and not os.path.exists(os.path.join(out, "s", "w1.safetensors"))
    os.remove(errf)
    # (c) registry reload: w2 registered after the plugin loaded
    st0 = json.load(open(os.path.join(out, "registry-status.json")))
    assert st0["n_entries"] == 1
    time.sleep(0.01)
    write_entry(reg, "s", "w2", w2, "all")
    eng.add("w2", w2, 0)
    eng.step({"w2": 320}, [pw])
    st1 = json.load(open(os.path.join(out, "registry-status.json")))
    errs, _, _ = check_dump(model, out, "s", "w2", eng.reqs["w2"].code, w2, np.arange(319))
    assert st1["n_entries"] == 2 and not errs, (st1, errs)
    # (d) stale file in staging -> refused
    eng.add("w2b", w2, 0)
    eng.step({"w2b": 320}, [pw])
    lines = open(os.path.join(out, "s", "w2.error.jsonl")).read()
    assert "already exists" in lines, lines
    # (e) same window twice in one batch -> second refused, first complete
    os.remove(os.path.join(out, "s", "w2.error.jsonl"))
    eng.add("x1", w1, 0)
    eng.add("x2", w1, 0)
    eng.step({"x1": 300, "x2": 300}, [pw])
    lines = open(os.path.join(out, "s", "w1.error.jsonl")).read()
    errs, _, _ = check_dump(model, out, "s", "w1", eng.reqs["x1"].code, w1, np.arange(299))
    assert "already in flight" in lines and not errs, (lines, errs)
    # (f) bad registry file is reported, not fatal
    with open(os.path.join(reg, "s", "bad.json"), "w") as f:
        json.dump({"window_id": "bad", "tokens": [1, 2, 3], "rows": [5]}, f)
    eng.add("probe", rand_tokens(5, V, 60), 0)
    eng.step({"probe": 5}, [pw])
    st2 = json.load(open(os.path.join(out, "registry-status.json")))
    assert st2["n_entries"] == 2 and any("bad.json" in e for e in st2["errors"]), st2
    # (g) an aborted request (first chunk only) is superseded by a fresh one
    w3 = rand_tokens(3000, V, 13)
    write_entry(reg, "s", "w3", w3, {"last": 100})
    eng.add("ab1", w3, 0)
    eng.step({"ab1": 2045}, [pw])
    assert os.path.exists(os.path.join(out, "s", "w3.safetensors.partial"))
    eng.add("ab2", w3, 0)
    eng.step({"ab2": 2045}, [pw])
    eng.step({"ab2": 955}, [pw])
    errs, rec, _ = check_dump(model, out, "s", "w3", eng.reqs["ab2"].code, w3, np.arange(2899, 2999))
    assert not errs and rec["superseded_request"] == "ab1", (errs, rec.get("superseded_request"))
    assert not os.path.exists(os.path.join(out, "s", "w3.error.jsonl"))
    shutil.rmtree(tmp)
    return "7 guard cases behave"


def t_rank1_inert():
    tmp, reg, out, model = setup()
    w = rand_tokens(200, V, 9)
    write_entry(reg, "s", "w", w, "all")
    cap = fresh_plugin(V, reg, out)
    cap._tp_rank = lambda: 1
    eng = Engine(model)
    pw, uw = cap_worker(), Unpatched(32)
    eng.workers = [pw, uw]
    eng.add("w", w, 0)
    outs, _ = eng.step({"w": 200}, [pw, uw])
    assert same_results(outs[0], outs[1]) and os.listdir(out) == [], os.listdir(out)
    shutil.rmtree(tmp)
    return "rank 1 writes nothing, result unchanged"


def t_old_plugin_row_offset():
    """The old glm53_kld plugin on the same decode-first batch writes the decode
    rows into the window file (reproduces the row-offset issue from the discovery report)."""
    old_dir, panel = "/old-plugin", "/kld-panel"
    if not (os.path.isdir(old_dir) and os.path.isdir(panel)):
        return "SKIPPED (old plugin / panel not mounted)"
    vocab = 154880
    tmp = tempfile.mkdtemp(prefix="oldbug-")
    sys.path.insert(0, old_dir)
    import glm53_kld_plugin as old
    import vllm.distributed as vd
    vd.get_tensor_model_parallel_rank = lambda: 0
    pl.PromptLogprobsWorker.compute_prompt_logprobs = ORIG_METHOD
    old._state = old._Capture(panel, tmp)
    old._orig_v2 = ORIG_METHOD
    model = Model(vocab)
    toks = np.load(os.path.join(panel, "final-0000.tokens.npy")).astype(np.int32)
    eng = Engine(model, max_len=4096)
    w = pl.PromptLogprobsWorker(32)
    w.compute_prompt_logprobs = old._patched_v2_compute_prompt_logprobs.__get__(w)
    eng.workers = [w]
    eng.add("d0", rand_tokens(10, vocab, 70), None, computed=11)
    eng.add("d1", rand_tokens(10, vocab, 71), None, computed=12)
    eng.add("win", toks, 0)
    eng.step({"d0": 4, "d1": 4, "win": 2048}, [w], drafts={"d0": [1, 2, 3], "d1": [1, 2, 3]})
    f = os.path.join(tmp, "window-0000.safetensors")
    hl = int.from_bytes(open(f, "rb").read(8), "little")
    got = np.memmap(f, dtype=np.float32, mode="r", offset=8 + hl, shape=(2047, vocab))
    raw_win = model.logits_rows(torch.tensor([[float(eng.reqs["win"].code), 0.0]])).float().numpy()[0]
    raw_d0 = model.logits_rows(torch.tensor([[float(eng.reqs["d0"].code), 11.0]])).float().numpy()[0]
    row0_is_decode = bool(np.array_equal(got[0], raw_d0))
    row0_is_window = bool(np.array_equal(got[0], raw_win))
    sys.path.remove(old_dir)
    shutil.rmtree(tmp)
    assert row0_is_decode and not row0_is_window, (row0_is_decode, row0_is_window)
    return "old plugin: dump row 0 == decode request d0's logits (row-offset issue reproduced); new plugin exact on same layout (t_decode_first)"


def t_core_units():
    from glm53_capture_plugin import core
    assert core.request_prompt_rows(10, 20, 0, 10, 100) == (10, 20, 0, False)
    assert core.request_prompt_rows(10, 20, 90, 10, 100) == (10, 19, 90, True)
    slot = np.full(99, -1, np.int32)
    rows = np.array([5, 6, 7, 20, 21, 50], np.int32)
    slot[rows] = np.arange(rows.size)
    r = core.runs_for_call(0, 1024, 3, 60, 0, slot)
    assert r == [(8, 11, 0), (23, 25, 3), (53, 54, 5)], r
    r = core.runs_for_call(1024, 1024, 1000, 1100, 0, np.arange(200, dtype=np.int32))
    assert r == [(0, 76, 24)], r
    try:
        core.runs_for_call(1024, 1024, 1000, 1100, 0, np.arange(99, dtype=np.int32))
        raise AssertionError("out-of-range window rows accepted")
    except IndexError:
        pass
    assert core.parse_rows({"last": 4}, 10).tolist() == [5, 6, 7, 8]
    for bad in ([3, 2], [0, 9], {"x": 1}, []):
        try:
            core.parse_rows(bad, 10)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    assert core.tokens_sha256([1, 2, 3]) == hashlib.sha256(np.array([1, 2, 3], "<i4").tobytes()).hexdigest()
    return "row arithmetic, rows specs, hash"


def main():
    torch.set_num_threads(1)
    print("vllm prompt_logprob.py sha256:",
          hashlib.sha256(open(pl.__file__, "rb").read()).hexdigest())
    for name, fn in [("core_units", t_core_units), ("decode_first", t_decode_first),
                     ("multi_prefill", t_multi_prefill), ("chunked_across_steps", t_chunked),
                     ("full_vocab", t_full_vocab), ("guards", t_guards),
                     ("rank1_inert", t_rank1_inert), ("old_plugin_row_offset", t_old_plugin_row_offset)]:
        run(name, fn)
    ok = True
    for name, status, detail, dt in RESULTS:
        ok &= status == "PASS"
        print(f"{status:5s} {name:22s} {dt:6.1f}s  {detail}")
    print("ALL PASS" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

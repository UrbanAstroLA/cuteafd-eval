"""vLLM general plugin: dump full-vocabulary log-softmax rows for registered
token windows, at registered rows only, from inside the real serving process.

Successor of <kld>/plugin/glm53_kld_plugin (left unchanged).

What it hooks
-------------
`vllm.v1.worker.gpu.sample.prompt_logprob.PromptLogprobsWorker.compute_prompt_logprobs`
(the V2 model runner; the server logs "Using V2 Model Runner").  vLLM calls it
on every step with `self.model.compute_logits` as `logits_fn`.  The wrapper
passes a tee in place of `logits_fn`: it returns exactly what `logits_fn`
returned and, on the side, copies the rows that belong to a registered window
to the host.  It then returns vLLM's own result unchanged.  No second lm_head
projection runs, so the dumped rows are the logits the serving path computed.

Row arithmetic (the fix versus glm53_kld)
-----------------------------------------
vLLM computes prompt logits for the WHOLE batch, `hidden_states[:num_tokens]`,
in 1024-row slices, and the V2 runner orders every batch
decode/verification -> short extend -> prefill.  The old plugin wrote rows from
batch row 0, so any decode traffic in the same step put other requests' logits
in the dump.  Here each request's rows are taken from its own
`query_start_loc_np[i] .. [i+1]` range (minus the last row on the final chunk),
intersected with each 1024-row slice, and mapped to window row
`num_computed_prefill_tokens + offset`.  Several registered windows may share a
batch; a window may arrive over any number of chunked-prefill steps.

Identification is by content: SHA-256 of the prompt's int32 token ids, looked
up only for prompts whose length is registered.  The registry is a directory of
JSON files {window_id, tokens, rows}; it is (re)loaded lazily inside the worker
whenever its file listing changes, so windows can be added without a restart.

Output (rank 0 only), under GLM53_CAP_OUT:
  <set>/<window_id>.safetensors   logprobs F32 [n_rows, vocab], rows I32 [n_rows],
                                  tokens_sha256 U8 [32]
  <set>/<window_id>.safetensors.receipt.json
  <set>/<window_id>.steps.jsonl   one line per engine step that touched the window
  <set>/<window_id>.error.jsonl   only if something went wrong
  steps.jsonl                     all window steps, all sets
  registry-status.json            what the worker has loaded

Safety: inert unless GLM53_CAP_ENABLE=1; never alters vLLM's inputs, outputs or
control flow; every internal failure is logged and recorded, never raised.

Environment
-----------
GLM53_CAP_ENABLE        "1" arms the plugin
GLM53_CAP_REGISTRY      registry directory (read-only mount)
GLM53_CAP_OUT           writable staging directory
GLM53_CAP_VOCAB         expected logits width (default 154880)
GLM53_CAP_HOST_THREADS  torch CPU threads for the host log-softmax (default 8;
                        restored to the worker's value after each slice)
"""
from __future__ import annotations

import collections
import json
import logging
import os
import threading
import time
import traceback

from . import core

logger = logging.getLogger("glm53_capture")

_ROW_CHUNK = 256          # rows per device->host copy (~79 MB of BF16 at full vocab)
_REQ_CACHE_MAX = 4096
_state = None
_orig = None
_lock = threading.Lock()


def _tp_rank() -> int:
    from vllm.distributed import get_tensor_model_parallel_rank
    return get_tensor_model_parallel_rank()


# --------------------------------------------------------------------- state

class _Target:
    """A registered window that is being captured (one in-flight request)."""

    def __init__(self, st, entry, req_id, tokens):
        self.entry, self.req_id, self.tokens = entry, req_id, tokens
        self.dump = core.Dump(st.out_dir, entry, st.vocab,
                              {"request_id": req_id})
        self.errors: list[str] = []
        self.steps: list[dict] = []
        self.t_open = time.time()
        self.next_computed = 0
        self.restarts = 0
        self.logits_dtype = None
        self.step = None           # per-step scratch, set by begin_step
        self.failed = False        # a step failed: never marked complete
        self.superseded = None     # id of an aborted earlier request for this window

    def begin_step(self, rec: dict, b_lo, b_hi, r_lo, is_final):
        self.b_lo, self.b_hi, self.r_lo, self.is_final = b_lo, b_hi, r_lo, is_final
        rec["rows_written"] = 0
        rec["dump_slots"] = []
        self.step = rec

    def err(self, st, msg: str):
        self.errors.append(msg)
        st.record_error(self.entry, msg)


class _State:
    def __init__(self, registry_dir, out_dir, vocab, host_threads):
        self.registry = core.Registry(registry_dir, vocab)
        self.out_dir, self.vocab, self.host_threads = out_dir, vocab, host_threads
        self.step = 0
        self.req_cache: collections.OrderedDict = collections.OrderedDict()
        self.open: dict[str, _Target] = {}
        self.writer = None
        self.loaded_once = False

    # rank 0 writes; every rank all-gathers the logits, so rank 0 has full rows
    def is_writer(self) -> bool:
        if self.writer is None:
            self.writer = (_tp_rank() == 0)
        return self.writer

    def reload_registry(self):
        changed = self.registry.maybe_reload()
        if changed or not self.loaded_once:
            self.loaded_once = True
            os.makedirs(self.out_dir, exist_ok=True)
            s = self.registry.status()
            s["loaded_at"] = time.time()
            s["producer"] = core.PRODUCER
            core.write_json_atomic(os.path.join(self.out_dir, "registry-status.json"), s)
            logger.warning("glm53_capture registry loaded: %d entries, %d errors",
                           s["n_entries"], len(s["errors"]))
            for e in s["errors"][:20]:
                logger.error("glm53_capture registry: %s", e)

    def cache_put(self, req_id, value):
        self.req_cache[req_id] = value
        while len(self.req_cache) > _REQ_CACHE_MAX:
            self.req_cache.popitem(last=False)

    def record_error(self, entry, msg):
        logger.error("glm53_capture %s: %s", entry.key, msg)
        try:
            d = os.path.join(self.out_dir, entry.set)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{entry.window_id}.error.jsonl"), "a") as f:
                f.write(json.dumps({"t": time.time(), "step": self.step,
                                    "window_id": entry.window_id, "error": msg}) + "\n")
        except Exception:
            logger.error("glm53_capture: cannot write error file:\n%s", traceback.format_exc())

    def log_step(self, tgt: _Target, rec: dict):
        line = json.dumps(rec, separators=(",", ":")) + "\n"
        d = os.path.join(self.out_dir, tgt.entry.set)
        with open(os.path.join(d, f"{tgt.entry.window_id}.steps.jsonl"), "a") as f:
            f.write(line)
        with open(os.path.join(self.out_dir, "steps.jsonl"), "a") as f:
            f.write(line)


# --------------------------------------------------------------- identify

def _identify(st: _State, worker, input_batch, all_token_ids, prompt_lens):
    """Return the list of _Target for registered windows in this batch."""
    import numpy as np
    idx = input_batch.idx_mapping_np
    uses = worker.uses_prompt_logprobs[idx]
    if not np.any(uses):
        return None
    if not st.is_writer():
        return None

    req_ids = input_batch.req_ids
    qsl = input_batch.query_start_loc_np
    nsched = input_batch.num_scheduled_tokens
    cpt = input_batch.num_computed_prefill_tokens_np
    pfl = input_batch.prefill_len_np
    drafts = getattr(input_batch, "num_draft_tokens_per_req", None)
    reloaded = False
    found = []
    for i, req_id in enumerate(req_ids):
        if not uses[i]:
            continue
        r = int(idx[i])
        plen = int(prompt_lens[r])
        computed = int(cpt[i])
        # vLLM produces no prompt rows for these (prompt_logprob.py:56-61)
        if computed >= plen or plen < int(pfl[i]):
            continue
        if req_id in st.req_cache:
            hit = st.req_cache[req_id]
        else:
            if not reloaded:
                st.reload_registry()
                reloaded = True
            hit = None
            if plen in st.registry.lengths:
                ids = all_token_ids[r, :plen].to("cpu").numpy()
                e = st.registry.by_key.get((plen, core.tokens_sha256(ids)))
                if e is not None:
                    hit = (e, ids.astype(np.int64))
            st.cache_put(req_id, hit)
        if hit is None:
            continue
        entry, ids = hit
        tgt = _target_for(st, entry, req_id, ids, computed, req_ids)
        if tgt is None:
            continue
        qs, qe, ns = int(qsl[i]), int(qsl[i + 1]), int(nsched[i])
        b_lo, b_hi, r_lo, is_final = core.request_prompt_rows(qs, qe, computed, ns, plen)
        others = []
        for j, rj in enumerate(req_ids):
            if j == i:
                continue
            others.append({"req": str(rj)[:24], "n": int(nsched[j]),
                           "computed": int(cpt[j]),
                           "prefill": bool(cpt[j] < pfl[j]),
                           "drafts": (int(drafts[j]) if drafts is not None else None)})
        rec = {"t": time.time(), "step": st.step, "set": entry.set,
               "window_id": entry.window_id, "req": str(req_id)[:24],
               "batch_idx": i, "chunk_start": computed, "chunk_len": ns,
               "batch_rows": [qs, qe], "prompt_rows": [b_lo, b_hi], "row_lo": r_lo,
               "final_chunk": is_final, "batch_size": len(req_ids),
               "num_tokens": int(input_batch.num_tokens), "others": others}
        tgt.begin_step(rec, b_lo, b_hi, r_lo, is_final)
        found.append(tgt)
    return found or None


def _target_for(st: _State, entry, req_id, ids, computed, batch_req_ids):
    key = entry.key
    tgt = st.open.get(key)
    superseded = None
    if tgt is not None and tgt.req_id != req_id:
        if tgt.req_id in batch_req_ids:
            st.record_error(entry, f"window already in flight as request {tgt.req_id}; "
                                   f"ignoring duplicate request {req_id}. Drive serially.")
            return None
        # The earlier request is not in this batch: it was aborted (client
        # timeout / disconnect) before its final chunk.  Drop its partial file.
        logger.warning("glm53_capture %s: request %s never finished; superseded by %s",
                       key, tgt.req_id, req_id)
        superseded = tgt.req_id
        tmp = tgt.dump.close(False)
        try:
            os.remove(tmp)
        except OSError:
            pass
        st.open.pop(key, None)
        tgt = None
    if tgt is not None:
        if computed == 0 and tgt.next_computed != 0:
            tgt.restarts += 1
            tgt.dump.reset()
            tgt.err(st, "prefill restarted at token 0 (preemption/recompute); "
                        "rows will be rewritten")
        elif computed != tgt.next_computed:
            tgt.err(st, f"chunk starts at {computed}, expected {tgt.next_computed}")
        return tgt
    if computed != 0:
        st.record_error(entry, f"first chunk seen starts at token {computed}, not 0 "
                               "(prefix cache hit or missed step); not capturing")
        st.cache_put(req_id, None)
        return None
    try:
        tgt = _Target(st, entry, req_id, ids)
    except Exception as exc:
        st.record_error(entry, f"cannot open dump: {exc}")
        st.cache_put(req_id, None)
        return None
    tgt.superseded = superseded
    st.open[key] = tgt
    logger.warning("glm53_capture open %s (%d tokens, %d rows)", key,
                   entry.n_tokens, entry.rows.size)
    return tgt


# ------------------------------------------------------------------ write

def _host_logsoftmax(host):
    import torch
    z = host.to(torch.float64)
    return (z - torch.logsumexp(z, dim=-1, keepdim=True)).to(torch.float32).numpy()


def _write_call(st: _State, targets, out, calls):
    import torch
    c0 = sum(m for _, m in calls)
    m = int(out.shape[0])
    calls.append((c0, m))
    prev = torch.get_num_threads()
    change = st.host_threads > 0 and st.host_threads != prev
    try:
        if change:
            torch.set_num_threads(st.host_threads)
        for t in targets:
            if t.step.get("failed"):
                continue
            try:
                if out.dim() != 2 or int(out.shape[-1]) != st.vocab:
                    raise ValueError(f"logits shape {tuple(out.shape)}, expected [*, {st.vocab}]")
                t.logits_dtype = str(out.dtype)
                runs = core.runs_for_call(c0, m, t.b_lo, t.b_hi, t.r_lo, t.dump.slot_of_row)
                for lo, hi, slot in runs:
                    for s in range(lo, hi, _ROW_CHUNK):
                        e = min(s + _ROW_CHUNK, hi)
                        host = out[s:e].detach().to("cpu", copy=True)
                        t.dump.write(slot + (s - lo), _host_logsoftmax(host))
                    t.step["rows_written"] += hi - lo
                    t.step["dump_slots"].append([slot, slot + hi - lo])
            except Exception:
                t.step["failed"] = True
                t.err(st, "write failed:\n" + traceback.format_exc())
    finally:
        if change:
            torch.set_num_threads(prev)


def _chosen_check(t: _Target, result):
    """Compare dumped logprob of tokens[r+1] with vLLM's own prompt logprob."""
    import numpy as np
    lt = result.get(t.req_id) if isinstance(result, dict) else None
    if lt is None:
        return {"status": "no vLLM prompt logprobs for this request"}
    lp = lt.logprobs.to("cpu").float().numpy()
    tid = lt.logprob_token_ids.to("cpu").numpy()
    n_rows_api = lp.shape[0]
    if n_rows_api != t.entry.n_tokens - 1:
        return {"status": f"vLLM returned {n_rows_api} rows, expected {t.entry.n_tokens - 1}"}
    rows = t.entry.rows.astype(np.int64)
    nxt = t.tokens[rows + 1]
    ids_ok = bool(np.array_equal(tid[rows, 0].astype(np.int64), nxt))
    ours = np.asarray(t.dump.mm[np.arange(rows.size), nxt], dtype=np.float64)
    diff = ours - lp[rows, 0].astype(np.float64)
    return {"status": "ok", "rows": int(rows.size), "vllm_token_ids_match": ids_ok,
            "max_abs_diff": float(np.max(np.abs(diff))),
            "mean_abs_diff": float(np.mean(np.abs(diff))),
            "n_abs_diff_gt_1e-3": int(np.sum(np.abs(diff) > 1e-3))}


def _after_step(st: _State, targets, calls, input_batch, result):
    total = sum(m for _, m in calls)
    for t in targets:
        rec = t.step
        rec["logits_calls"] = calls
        rec["logits_dtype"] = t.logits_dtype
        if total != int(input_batch.num_tokens):
            rec["failed"] = True
            t.err(st, f"logits_fn covered {total} rows, batch has {input_batch.num_tokens}")
        expected = rec["prompt_rows"][1] - rec["prompt_rows"][0]
        rec["prompt_rows_this_step"] = expected
        if rec.get("failed"):
            t.failed = True
        t.steps.append({k: rec[k] for k in ("step", "chunk_start", "chunk_len",
                                            "batch_size", "num_tokens", "batch_rows",
                                            "rows_written", "final_chunk")})
        t.next_computed = rec["chunk_start"] + rec["chunk_len"]
        st.log_step(t, rec)
        if t.is_final:
            _finish(st, t, result)


def _finish(st: _State, t: _Target, result):
    st.open.pop(t.entry.key, None)
    import numpy as np
    chosen = None
    try:
        chosen = _chosen_check(t, result)
    except Exception:
        chosen = {"status": "error", "trace": traceback.format_exc()}
    d = t.dump
    complete = bool(d.covered.all()) and not t.failed
    multi = int(np.sum(d.writes > 1))
    if multi and t.restarts == 0:
        t.err(st, f"{multi} rows written more than once")
        complete = False
    if not complete and not t.errors:
        t.err(st, f"final chunk done but only {int(d.covered.sum())}/{d.n_rows} rows written")
    final_path = d.close(complete)
    receipt = {
        "window_id": t.entry.window_id, "set": t.entry.set, "path": final_path,
        "complete": complete, "request_id": t.req_id,
        "n_tokens": t.entry.n_tokens, "tokens_sha256": t.entry.sha,
        "n_rows": d.n_rows, "rows_first": int(t.entry.rows[0]),
        "rows_last": int(t.entry.rows[-1]), "rows_written": int(d.covered.sum()),
        "shape": [d.n_rows, d.vocab], "dtype": "float32", "data_offset": d.data_offset,
        "logits_dtype": t.logits_dtype, "logprob_method": core.LOGPROB_METHOD,
        "row_convention": core.ROW_CONVENTION, "host_threads": st.host_threads,
        "restarts": t.restarts, "superseded_request": t.superseded, "steps": t.steps, "n_steps": len(t.steps),
        "chosen_check": chosen, "errors": t.errors,
        "t_open": t.t_open, "t_close": time.time(), "producer": core.PRODUCER,
    }
    core.write_json_atomic(d.path + ".receipt.json", receipt)
    st.cache_put(t.req_id, None)
    logger.warning("glm53_capture wrote %s (%d/%d rows, %d steps, complete=%s)",
                   final_path, receipt["rows_written"], d.n_rows, len(t.steps), complete)


# ------------------------------------------------------------------- hook

def _patched_compute_prompt_logprobs(self, logits_fn, hidden_states, input_batch,
                                     all_token_ids, num_computed_tokens, prompt_lens):
    st = _state
    targets = None
    try:
        st.step += 1
        targets = _identify(st, self, input_batch, all_token_ids, prompt_lens)
    except Exception:
        logger.error("glm53_capture identify failed:\n%s", traceback.format_exc())
        targets = None
    if not targets:
        return _orig(self, logits_fn, hidden_states, input_batch, all_token_ids,
                     num_computed_tokens, prompt_lens)

    calls: list[tuple[int, int]] = []

    def _tee(hs):
        out = logits_fn(hs)
        try:
            with _lock:
                _write_call(st, targets, out, calls)
        except Exception:
            logger.error("glm53_capture tee failed:\n%s", traceback.format_exc())
        return out

    result = _orig(self, _tee, hidden_states, input_batch, all_token_ids,
                   num_computed_tokens, prompt_lens)
    try:
        with _lock:
            _after_step(st, targets, calls, input_batch, result)
    except Exception:
        logger.error("glm53_capture after-step failed:\n%s", traceback.format_exc())
    return result


def register():
    """Entry point for the `vllm.general_plugins` group."""
    global _state, _orig
    if os.environ.get("GLM53_CAP_ENABLE", "0") != "1":
        return
    reg = os.environ.get("GLM53_CAP_REGISTRY")
    out = os.environ.get("GLM53_CAP_OUT")
    if not reg or not out:
        logger.error("glm53_capture: GLM53_CAP_ENABLE=1 but GLM53_CAP_REGISTRY / "
                     "GLM53_CAP_OUT not both set; plugin stays inert")
        return
    try:
        from vllm.v1.worker.gpu.sample.prompt_logprob import PromptLogprobsWorker
    except Exception:
        logger.error("glm53_capture: cannot import PromptLogprobsWorker; inert:\n%s",
                     traceback.format_exc())
        return
    if getattr(PromptLogprobsWorker.compute_prompt_logprobs, "_glm53_capture", False):
        return
    vocab = int(os.environ.get("GLM53_CAP_VOCAB", core.VOCAB_DEFAULT))
    threads = int(os.environ.get("GLM53_CAP_HOST_THREADS", "8"))
    _state = _State(reg, out, vocab, threads)
    _orig = PromptLogprobsWorker.compute_prompt_logprobs
    _patched_compute_prompt_logprobs._glm53_capture = True
    PromptLogprobsWorker.compute_prompt_logprobs = _patched_compute_prompt_logprobs
    logger.warning("glm53_capture: patched PromptLogprobsWorker.compute_prompt_logprobs "
                   "(registry=%s, out=%s, vocab=%d, host_threads=%d)", reg, out, vocab, threads)

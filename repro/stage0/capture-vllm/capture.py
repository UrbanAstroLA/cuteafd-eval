#!/usr/bin/env python3
"""Register token windows and drive the glm53_capture plugin on the vLLM v0.9.2
server, one window at a time, with the server otherwise idle.

  register  build registry/<set>/<window_id>.json from P-A, P-B or any
            {window_id, tokens, rows} JSON (or a bare JSON list of ids)
  status    show the registry, and what the server's plugin has loaded
  capture   send each window as /v1/completions (prompt = token ids,
            max_tokens 1, prompt_logprobs 0, temperature 0, recorded seed),
            wait for the dump, verify it, move it to runs/<tag>/<set>/
  verify    re-check finished dumps offline

Needs numpy only (host: <venv>/bin/python). Starts and
stops nothing; talks to the server over HTTP on 127.0.0.1.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True          # keep the mounted plugin dir clean
sys.path.insert(0, os.path.join(HERE, "plugin"))
from glm53_capture_plugin import core  # noqa: E402  (pure numpy, no vLLM)

REGISTRY = os.path.join(HERE, "registry")
OUT_DEFAULT = os.environ.get("CAPTURE_OUT_DIR",
                             "<run>/vllm-v092-dumps")
PA_PANEL = "<runs>/kld/panel-final"
PA_MANIFEST = "<datasets>/glm53-flash-teacher-logits/dataset-manifest.json"
PB_WINDOWS = ("<datasets>/2026-10-26-engine-compare/cuteafd-fidelity/"
              "glm5_flash-v2_20261005_bf16root/windows.json")
VOCAB = int(os.environ.get("CAPTURE_VOCAB", core.VOCAB_DEFAULT))   # override only in tests
CHOSEN_TOL = 1e-3          # |dumped - API| logprob of the chosen token, nats
LSE_TOL = 1e-4             # |logsumexp(row)| of a stored log-softmax row


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ================================================================ register

def _entry_doc(wid, set_, tokens, rows_spec, meta):
    toks = [int(x) for x in tokens]
    rows = core.parse_rows(rows_spec, len(toks))
    if rows.size == rows[-1] - rows[0] + 1:
        spec = {"start": int(rows[0]), "stop": int(rows[-1]) + 1}
    else:
        spec = rows.tolist()
    return {"window_id": wid, "set": set_, "n_tokens": len(toks),
            "tokens_sha256": core.tokens_sha256(toks), "rows": spec,
            "n_rows": int(rows.size), "meta": meta, "tokens": toks}


def _from_pa(set_):
    man = json.load(open(PA_MANIFEST))
    docs = []
    for e in man["logit_files"]:
        wid = e["window_id"]
        p = os.path.join(PA_PANEL, f"{wid}.tokens.npy")
        fh = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if fh != e["token_ids_sha256"]:
            raise SystemExit(f"{p}: file sha256 {fh} != dataset manifest {e['token_ids_sha256']}")
        t = np.load(p).astype(np.int64)
        if t.shape != (2048,):
            raise SystemExit(f"{p}: shape {t.shape}")
        docs.append(_entry_doc(wid, set_, t, "all", {
            "source": "P-A brandonmusic BF16 teacher panel", "teacher_file": e["path"],
            "npy_sha256": fh, "domain": e.get("domain")}))
    return docs


def _from_pb(set_, path):
    d = json.load(open(path))
    docs = []
    for w in d["windows"]:
        n, sf = len(w["tokens"]), int(w["score_from"])
        # his position p predicts tokens[p] from tokens[:p]  ==  our row p-1
        docs.append(_entry_doc(w["id"], set_, w["tokens"], {"start": sf - 1, "stop": n - 1}, {
            "source": f"cuteafd-fidelity {d.get('version')} set {d.get('set_sha256')}",
            "score_from": sf, "bucket": w.get("bucket"), "block": w.get("block"),
            "convention": "reference position p = our row p-1"}))
    return docs


def _from_json(set_, paths, last_rows):
    docs = []
    for p in paths:
        d = json.load(open(p))
        if isinstance(d, list):
            if last_rows is None:
                raise SystemExit(f"{p} is a bare token list; give --last-rows")
            wid, toks, rows, meta = os.path.splitext(os.path.basename(p))[0], d, {"last": last_rows}, {}
        else:
            wid, toks = d["window_id"], d["tokens"]
            rows = d.get("rows", {"last": last_rows} if last_rows else None)
            if rows is None:
                raise SystemExit(f"{p} has no rows and no --last-rows given")
            meta = d.get("meta") or {}
        meta = {**meta, "source_file": os.path.abspath(p),
                "source_file_sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()}
        docs.append(_entry_doc(str(wid), set_, toks, rows, meta))
    return docs


def cmd_register(a):
    if a.pa:
        docs = _from_pa(a.set)
    elif a.pb:
        docs = _from_pb(a.set, a.pb)
    else:
        paths = sorted(p for g in a.json for p in glob.glob(g))
        if not paths:
            raise SystemExit(f"no files match {a.json}")
        docs = _from_json(a.set, paths, a.last_rows)
    reg = a.registry
    existing = {}
    for p in core.registry_files(reg):
        e, _ = core.load_entry(p, reg, VOCAB)
        existing[(e.n_tokens, e.sha)] = e
    set_dir = os.path.join(reg, a.set)
    os.makedirs(set_dir, exist_ok=True)
    wrote = same = 0
    for doc in docs:
        p = os.path.join(set_dir, f"{doc['window_id']}.json")
        k = (doc["n_tokens"], doc["tokens_sha256"])
        if k in existing and existing[k].path != p:
            raise SystemExit(f"{doc['window_id']}: same tokens already registered as "
                             f"{existing[k].key}")
        if os.path.exists(p):
            old = json.load(open(p))
            if old == doc:
                same += 1
                continue
            if not a.replace:
                raise SystemExit(f"{p} exists with different content; --replace to overwrite")
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f, separators=(",", ":"))
        e, _ = core.load_entry(tmp, reg, VOCAB)      # validate what we wrote
        os.replace(tmp, p)
        wrote += 1
    idx = [{k: d[k] for k in ("window_id", "n_tokens", "tokens_sha256", "rows", "n_rows")}
           for d in docs]
    core.write_json_atomic(os.path.join(set_dir, ".index.json"), idx)
    n_rows = sum(d["n_rows"] for d in docs)
    log(f"set {a.set}: {len(docs)} windows ({wrote} written, {same} unchanged), "
        f"{sum(d['n_tokens'] for d in docs):,} tokens, {n_rows:,} rows, "
        f"dump {n_rows * VOCAB * 4 / 1e9:.1f} GB")


# ================================================================== status

def load_set(reg, set_, keep_tokens=True):
    d = os.path.join(reg, set_)
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        e, t = core.load_entry(p, reg, VOCAB, keep_tokens=keep_tokens)
        out.append((e, t))
    if not out:
        raise SystemExit(f"no registry entries under {d}")
    return out


def cmd_status(a):
    reg = a.registry
    sets = sorted(x for x in os.listdir(reg) if os.path.isdir(os.path.join(reg, x)))
    for s in sets:
        ents = load_set(reg, s, keep_tokens=False)
        rows = sum(int(e.rows.size) for e, _ in ents)
        lens = [e.n_tokens for e, _ in ents]
        print(f"{s:6s} {len(ents):3d} windows  tokens {min(lens)}-{max(lens)} "
              f"(sum {sum(lens):,})  rows {rows:,}  dump {rows * VOCAB * 4 / 1e9:.2f} GB")
    print("registry signature:", core.registry_signature(reg))
    sp = os.path.join(a.out_dir, "staging", "registry-status.json")
    if os.path.exists(sp):
        st = json.load(open(sp))
        print(f"server plugin loaded: {st['n_entries']} entries, signature {st['signature']}, "
              f"{len(st['errors'])} errors, at {time.ctime(st['loaded_at'])}")
        for e in st["errors"]:
            print("  plugin registry error:", e)
    else:
        print(f"no {sp} (plugin has not loaded the registry yet)")


# ================================================================= capture

def http(base, path, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data,
                                 {"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw


def metrics_busy(base):
    txt = http(base, "/metrics", timeout=10).decode()
    run = wait = 0.0
    for line in txt.splitlines():
        if line.startswith("vllm:num_requests_running"):
            run += float(line.rsplit(" ", 1)[1])
        elif line.startswith("vllm:num_requests_waiting"):
            wait += float(line.rsplit(" ", 1)[1])
    return run, wait


def wait_idle(base, limit):
    t0 = time.time()
    while True:
        run, wait = metrics_busy(base)
        if run == 0 and wait == 0:
            return time.time() - t0
        if time.time() - t0 > limit:
            raise SystemExit(f"server not idle after {limit}s (running={run}, waiting={wait}); "
                             "capture needs an otherwise idle server")
        time.sleep(1)


def stage_files(stage_set, wid):
    base = os.path.join(stage_set, wid)
    return [base + s for s in (".safetensors", ".safetensors.partial",
                               ".safetensors.receipt.json", ".steps.jsonl", ".error.jsonl")]


def verify_file(path, entry, sample=8):
    """Offline checks of one dump. Returns list of problems (empty = good)."""
    probs = []
    t, meta = core.read_safetensors(path)
    lp = t.get("logprobs")
    if lp is None or lp.shape != (entry.rows.size, VOCAB):
        return [f"logprobs shape {None if lp is None else lp.shape}"]
    if not np.array_equal(np.asarray(t["rows"]), entry.rows):
        probs.append("rows tensor != registered rows")
    if bytes(np.asarray(t["tokens_sha256"])).hex() != entry.sha or meta.get("tokens_sha256") != entry.sha:
        probs.append("tokens_sha256 mismatch")
    for s in np.unique(np.linspace(0, entry.rows.size - 1, sample).astype(int)):
        row = np.asarray(lp[s], dtype=np.float64)
        if not np.all(np.isfinite(row)):
            probs.append(f"slot {s}: non-finite values")
            continue
        m = row.max()
        lse = m + np.log(np.exp(row - m).sum())
        if abs(lse) > LSE_TOL:
            probs.append(f"slot {s}: logsumexp {lse:.2e} (not a log-softmax row)")
    return probs


def chosen_vs_api(path, entry, tokens, api_plp, n):
    """--verify-chosen: dumped logprob of tokens[r+1] vs API prompt_logprobs[r+1]."""
    t, _ = core.read_safetensors(path)
    lp = t["logprobs"]
    slots = np.unique(np.linspace(0, entry.rows.size - 1, n).astype(int))
    worst, checked = 0.0, []
    for s in slots:
        r = int(entry.rows[s])
        tok = int(tokens[r + 1])
        d = api_plp[r + 1]
        if not d or str(tok) not in d:
            raise SystemExit(f"API prompt_logprobs[{r + 1}] lacks token {tok}: {d}")
        api = float(d[str(tok)]["logprob"])
        ours = float(lp[s, tok])
        worst = max(worst, abs(ours - api))
        checked.append({"row": r, "token": tok, "dump": ours, "api": api})
    return worst, checked


def cmd_capture(a):
    base = a.base_url.rstrip("/")
    ents = load_set(a.registry, a.set)
    if a.only:
        want = set(a.only.split(","))
        ents = [x for x in ents if x[0].window_id in want]
        missing = want - {e.window_id for e, _ in ents}
        if missing:
            raise SystemExit(f"not registered in {a.set}: {sorted(missing)}")
    staging = os.path.join(a.out_dir, "staging")
    stage_set = os.path.join(staging, a.set)
    dest = os.path.join(a.out_dir, "runs", a.run_tag, a.set)
    need = sum(core.data_bytes(int(e.rows.size), VOCAB) for e, _ in ents)
    probe = a.out_dir
    while not os.path.exists(probe):
        probe = os.path.dirname(probe)
    free = shutil.disk_usage(probe).free
    log(f"set {a.set}: {len(ents)} windows, {need / 1e9:.1f} GB to write, "
        f"{free / 1e9:.0f} GB free on {a.out_dir}")
    if need * 1.1 > free:
        raise SystemExit("not enough free disk")
    if a.dry_run:
        for e, t in ents:
            print(f"  {e.window_id:12s} n={e.n_tokens:6d} rows {e.rows[0]}..{e.rows[-1]} "
                  f"({e.rows.size}) sha {e.sha[:12]}")
        return
    os.makedirs(stage_set, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    for d in (staging, stage_set, dest):
        if not os.access(d, os.W_OK):
            raise SystemExit(f"{d} is not writable by this user (created by the container as "
                             "root?); fix ownership before capturing")

    models = json.loads(http(base, "/v1/models"))
    model = a.model or models["data"][0]["id"]
    log(f"server {base} model {model}")

    # Make the plugin (re)load the registry with a 4-token unregistered prompt,
    # then confirm it holds exactly this registry.
    http(base, "/v1/completions", {"model": model, "prompt": [11, 22, 33, 44],
                                   "max_tokens": 1, "temperature": 0, "prompt_logprobs": 0,
                                   "seed": 1}, timeout=600)
    sp = os.path.join(staging, "registry-status.json")
    if not os.path.exists(sp):
        raise SystemExit(f"{sp} missing: the plugin is not armed (check the container log "
                         "for 'glm53_capture: patched')")
    st = json.load(open(sp))
    sig = core.registry_signature(a.registry)
    if st["signature"] != sig:
        raise SystemExit(f"plugin registry signature {st['signature']} != local {sig}")
    for e, _ in ents:
        se = st["entries"].get(e.key)
        if not se or se["tokens_sha256"] != e.sha or se["n_rows"] != e.rows.size:
            raise SystemExit(f"plugin has not loaded {e.key} as registered")
    log(f"plugin registry matches ({st['n_entries']} entries)")

    mpath = os.path.join(dest, "capture-manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {
        "set": a.set, "run_tag": a.run_tag, "base_url": base, "model": model,
        "registry_signature": sig, "windows": {}}
    t_all = time.time()
    for k, (e, toks) in enumerate(ents):
        if e.window_id in manifest["windows"] and manifest["windows"][e.window_id].get("ok"):
            log(f"{e.window_id}: already captured in {dest}; skipping")
            continue
        for f in stage_files(stage_set, e.window_id):
            if os.path.exists(f):
                raise SystemExit(f"stale staging file {f}; move it aside before capturing")
        if os.path.exists(os.path.join(dest, f"{e.window_id}.safetensors")):
            raise SystemExit(f"{dest}/{e.window_id}.safetensors exists but is not in the manifest")
        idle_s = wait_idle(base, a.idle_wait)
        seed = int(hashlib.sha256(f"{a.run_tag}/{a.set}/{e.window_id}".encode()).hexdigest()[:8], 16)
        body = {"model": model, "prompt": [int(x) for x in toks], "max_tokens": 1,
                "temperature": 0, "prompt_logprobs": 0, "seed": seed}
        t0 = time.time()
        try:
            resp = json.loads(http(base, "/v1/completions", body, timeout=a.timeout))
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{e.window_id}: HTTP {exc.code}: {exc.read()[:400]!r}")
        t_resp = time.time() - t0
        rp = os.path.join(stage_set, f"{e.window_id}.safetensors.receipt.json")
        while not os.path.exists(rp) and time.time() - t0 < t_resp + a.dump_wait:
            time.sleep(0.2)
        t_dump = time.time() - t0
        probs = []
        ef = os.path.join(stage_set, f"{e.window_id}.error.jsonl")
        if os.path.exists(ef):
            probs.append("plugin errors: " + open(ef).read()[:800])
        rec = json.load(open(rp)) if os.path.exists(rp) else None
        if rec is None:
            probs.append(f"no receipt after {a.dump_wait}s")
        else:
            if not rec["complete"]:
                probs.append(f"incomplete: {rec['rows_written']}/{rec['n_rows']} rows")
            if rec["tokens_sha256"] != e.sha or rec["n_rows"] != e.rows.size:
                probs.append("receipt sha/rows differ from registry")
            cc = rec.get("chosen_check") or {}
            if cc.get("status") != "ok" or not cc.get("vllm_token_ids_match") \
                    or cc.get("max_abs_diff", 1) > CHOSEN_TOL:
                probs.append(f"in-server chosen-token check: {cc}")
        usage = resp.get("usage") or {}
        if usage.get("prompt_tokens") != e.n_tokens:
            probs.append(f"usage.prompt_tokens {usage.get('prompt_tokens')} != {e.n_tokens}")
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        if cached:
            probs.append(f"{cached} prompt tokens served from prefix cache")
        fpath = os.path.join(stage_set, f"{e.window_id}.safetensors")
        api_check = None
        if not probs:
            probs += verify_file(fpath, e)
        if not probs and a.verify_chosen:
            plp = resp["choices"][0].get("prompt_logprobs")
            if not plp or len(plp) != e.n_tokens:
                probs.append(f"API prompt_logprobs length {None if not plp else len(plp)}")
            else:
                worst, checked = chosen_vs_api(fpath, e, toks, plp, a.verify_chosen)
                api_check = {"max_abs_diff": worst, "points": checked}
                if worst > CHOSEN_TOL:
                    probs.append(f"--verify-chosen: max |dump - API| = {worst:.2e}")
        steps = rec["steps"] if rec else []
        busy = [s for s in steps if s["batch_size"] > 1]
        ent = {"ok": not probs, "problems": probs, "n_tokens": e.n_tokens,
               "n_rows": int(e.rows.size), "tokens_sha256": e.sha, "seed": seed,
               "t_send": t0, "seconds_response": round(t_resp, 3),
               "seconds_to_receipt": round(t_dump, 3), "idle_wait_s": round(idle_s, 1),
               "n_steps": len(steps), "chunk_lens": [s["chunk_len"] for s in steps],
               "steps_with_other_requests": len(busy),
               "chosen_check_server": rec.get("chosen_check") if rec else None,
               "chosen_check_api": api_check, "usage": usage}
        if not probs:
            for f in stage_files(stage_set, e.window_id):
                if os.path.exists(f):
                    os.rename(f, os.path.join(dest, os.path.basename(f)))
            ent["bytes"] = os.path.getsize(os.path.join(dest, f"{e.window_id}.safetensors"))
        manifest["windows"][e.window_id] = ent
        core.write_json_atomic(mpath, manifest)
        cc = (rec or {}).get("chosen_check") or {}
        log(f"[{k + 1}/{len(ents)}] {e.window_id:12s} n={e.n_tokens:6d} rows={e.rows.size:5d} "
            f"{t_resp:6.1f}s steps={len(steps)} busy_steps={len(busy)} "
            f"chosen={cc.get('max_abs_diff', float('nan')):.1e}"
            + (f" api={api_check['max_abs_diff']:.1e}" if api_check else "")
            + ("  OK" if not probs else "  FAIL: " + "; ".join(probs)))
        if probs:
            raise SystemExit(f"{e.window_id}: capture failed; files left in {stage_set}")
    manifest["seconds_total"] = round(time.time() - t_all, 1)
    core.write_json_atomic(mpath, manifest)
    tot = sum(w.get("seconds_response", 0) for w in manifest["windows"].values())
    log(f"done: {len(manifest['windows'])} windows in {dest}; request time {tot:.0f}s, "
        f"wall {manifest['seconds_total']:.0f}s; manifest {mpath}")


def cmd_verify(a):
    dest = os.path.join(a.out_dir, "runs", a.run_tag, a.set)
    bad = 0
    for e, _ in load_set(a.registry, a.set, keep_tokens=False):
        p = os.path.join(dest, f"{e.window_id}.safetensors")
        if not os.path.exists(p):
            print(f"MISSING {e.window_id}")
            bad += 1
            continue
        probs = verify_file(p, e, sample=a.sample)
        rec = json.load(open(p + ".receipt.json"))
        if not rec["complete"]:
            probs.append("receipt incomplete")
        print(("OK      " if not probs else "BAD     ") + e.window_id, "; ".join(probs))
        bad += bool(probs)
    raise SystemExit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--out-dir", default=OUT_DEFAULT,
                    help="host directory mounted as /kld-out (default %(default)s)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register")
    r.add_argument("--set", required=True)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--pa", action="store_true", help=f"P-A: 25 x 2048 from {PA_PANEL}, all rows")
    g.add_argument("--pb", nargs="?", const=PB_WINDOWS, help="P-B windows.json; rows score_from-1..n-2")
    g.add_argument("--json", nargs="+", help="files/globs: {window_id,tokens,rows} or bare id lists")
    r.add_argument("--last-rows", type=int, help="rows = last K prompt rows (bare lists, or entries without rows)")
    r.add_argument("--replace", action="store_true")
    r.set_defaults(fn=cmd_register)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)

    c = sub.add_parser("capture")
    c.add_argument("--set", required=True)
    c.add_argument("--run-tag", required=True, help="e.g. v1-r1; output goes to runs/<tag>/<set>/")
    c.add_argument("--only", help="comma-separated window ids")
    c.add_argument("--base-url", default="http://127.0.0.1:8001")
    c.add_argument("--model", help="default: first id from /v1/models")
    c.add_argument("--verify-chosen", type=int, default=0, metavar="N",
                   help="also compare N dumped rows' chosen-token logprob with the API's")
    c.add_argument("--idle-wait", type=float, default=120)
    c.add_argument("--dump-wait", type=float, default=60)
    c.add_argument("--timeout", type=float, default=3600)
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(fn=cmd_capture)

    v = sub.add_parser("verify")
    v.add_argument("--set", required=True)
    v.add_argument("--run-tag", required=True)
    v.add_argument("--sample", type=int, default=16)
    v.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

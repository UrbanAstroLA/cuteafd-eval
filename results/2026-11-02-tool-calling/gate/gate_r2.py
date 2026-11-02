#!/usr/bin/env python3
"""Gate R2 (live): send the gate-R tool conversations to the server on :8001 with max_tokens 1 and
chat_template_kwargs.clear_thinking=false; record usage.prompt_tokens. Standard library only.
    python3 gate_r2.py <conversations.json> <out.json>
"""
import json, sys, urllib.request
src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src))
model = json.load(urllib.request.urlopen("http://127.0.0.1:8001/v1/models", timeout=30))["data"][0]["id"]
res = {"model": model, "prompt_tokens": {}}
for name, msgs in d["conversations"].items():
    msgs = json.loads(json.dumps(msgs))
    for m in msgs:
        for c in m.get("tool_calls", []):
            c["function"]["arguments"] = json.dumps(c["function"]["arguments"])
    body = {"model": model, "messages": msgs, "tools": d["tools"], "max_tokens": 1, "temperature": 0,
            "chat_template_kwargs": {"clear_thinking": False}}
    req = urllib.request.Request("http://127.0.0.1:8001/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    res["prompt_tokens"][name] = r["usage"]["prompt_tokens"]
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res))

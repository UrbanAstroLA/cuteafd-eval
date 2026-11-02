#!/usr/bin/env python3
"""Gate R (CPU): with chat_template_kwargs.clear_thinking=false, do K4's template and the zai template the vLLM fork
uses render byte-identical text for multi-turn tool conversations shaped like tool-eval-bench's (assistant turns with
reasoning_content and tool_calls, tool results, a follow-up user turn)? Also writes the conversations for gate R2
(live prompt_tokens equality between engines). Host python3, jinja2; environment as in
../../2026-10-27-k4-three-engine-discovery/template/template_diff.py.
"""
import hashlib, json, sys
sys.path.insert(0, "<k4-discovery>/template")
from template_diff import env, K4, ZAI
import glob
K6 = glob.glob("<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K4-Core-K6/snapshots/*/chat_template.jinja")[0]
TOOLS = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
          "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
call = lambda i, city: {"id": f"call_{i}", "type": "function", "function": {"name": "get_weather", "arguments": {"city": city}}}
CONV = {
 "tool-loop": [{"role": "system", "content": "You are a helpful assistant."},
               {"role": "user", "content": "Weather in Paris?"},
               {"role": "assistant", "content": "", "reasoning_content": "Need the tool.", "tool_calls": [call(1, "Paris")]},
               {"role": "tool", "tool_call_id": "call_1", "content": "{\"temp_c\": 14}"}],
 "follow-up": [{"role": "user", "content": "Weather in Paris?"},
               {"role": "assistant", "content": "", "reasoning_content": "Need the tool.", "tool_calls": [call(1, "Paris")]},
               {"role": "tool", "tool_call_id": "call_1", "content": "{\"temp_c\": 14}"},
               {"role": "assistant", "content": "It is 14 C in Paris.", "reasoning_content": "Report it."},
               {"role": "user", "content": "And in Rome?"}],
 "two-calls": [{"role": "user", "content": "Compare Oslo and Lima."},
               {"role": "assistant", "content": "", "reasoning_content": "Two lookups.", "tool_calls": [call(1, "Oslo"), call(2, "Lima")]},
               {"role": "tool", "tool_call_id": "call_1", "content": "{\"temp_c\": 2}"},
               {"role": "tool", "tool_call_id": "call_2", "content": "{\"temp_c\": 19}"}]}
e = env(); out = {"clear_thinking": False, "cases": {}}
for name, msgs in CONV.items():
    r = {}
    for lab, path in (("k4", K4), ("zai", ZAI), ("k6", K6)):
        t = e.from_string(open(path).read())
        s = t.render(messages=msgs, tools=TOOLS, add_generation_prompt=True, enable_thinking=True, clear_thinking=False)
        r[lab] = hashlib.sha256(s.encode()).hexdigest()[:16]
    r["k4_eq_zai"] = r["k4"] == r["zai"]; out["cases"][name] = r
    # default (kwarg absent), to record the difference the kwarg removes
    d = {lab: hashlib.sha256(e.from_string(open(p).read()).render(messages=msgs, tools=TOOLS, add_generation_prompt=True,
         enable_thinking=True).encode()).hexdigest()[:16] for lab, p in (("k4", K4), ("zai", ZAI))}
    r["default_k4_eq_zai"] = d["k4"] == d["zai"]
json.dump({"tools": TOOLS, "conversations": CONV}, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out, indent=1))
sys.exit(0 if all(c["k4_eq_zai"] for c in out["cases"].values()) else 1)

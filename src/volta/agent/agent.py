# agent.py
"""ReAct loop for the dispatch agent. The agent gathers the forecast and battery
state, calls the optimizer, and commits a schedule. The committed schedule is the
last optimizer result it endorsed, so the model never has to echo 24 numbers."""

import json

from volta.agent.prompts import SYSTEM_PROMPT, TOOL_SCHEMAS

MAX_STEPS = 8
HOURS = 24


def run_agent(date_str, tools, client=None, model=None):
    """Plan one day. Returns {date, action, schedule, rationale, trace}.

    tools: dict of name -> callable (from make_tools, or stubs in tests).
    client/model: an OpenAI-compatible client and model name. If client is None,
    one is built from llm.get_client_and_model()."""
    if client is None:
        from volta.agent.llm import get_client_and_model
        client, model = get_client_and_model()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Plan battery dispatch for {date_str}."},
    ]
    last_schedule = None
    trace = []

    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS, temperature=0.2)
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append({
                "role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name,
                                             "arguments": tc.function.arguments}}
                               for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                func = tools.get(tc.function.name)
                result = func(**args) if func else {"error": f"unknown tool {tc.function.name}"}
                if tc.function.name == "run_optimizer" and "schedule" in result:
                    last_schedule = result["schedule"]
                trace.append({"tool": tc.function.name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result)})
            continue

        content = (msg.content or "").strip()
        messages.append({"role": "assistant", "content": content})
        if "FINAL:" in content:
            final = content.split("FINAL:", 1)[1].strip()
            action = "trade" if final.lower().startswith("trade") else "hold"
            if action == "trade" and last_schedule is not None:
                schedule = last_schedule
            else:
                action = "hold"  # nothing to commit means we held, whatever was said
                schedule = [0.0] * HOURS
            return {"date": date_str, "action": action, "schedule": schedule,
                    "rationale": final, "trace": trace}

    # Step cap reached without a decision: hold.
    return {"date": date_str, "action": "hold", "schedule": [0.0] * HOURS,
            "rationale": "step limit reached", "trace": trace}

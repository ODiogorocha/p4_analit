def build_prompt(f):

    return f"""
Detect if this is an ELEPHANT FLOW in a P4 switch.

packets={f.packets}
bytes={f.bytes}
duration={f.age()}
avg_latency={f.latency_sum / max(f.samples,1)}
avg_queue={f.queue_sum / max(f.samples,1)}

Return ONLY JSON:
{{
  "elephant": true/false,
  "confidence": 0.0,
  "reason": ""
}}
"""
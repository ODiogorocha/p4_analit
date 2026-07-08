def build_prompt(f):

    return f"""
Classify if this is an ELEPHANT FLOW.

packets={f['packets']}
bytes={f['bytes']}
duration={f['duration']}
pps={f['pps']}
bps={f['bps']}
latency={f['latency']}
queue={f['queue']}

Return JSON:
{{
  "elephant": true,
  "confidence": 0.0,
  "reason": ""
}}
"""
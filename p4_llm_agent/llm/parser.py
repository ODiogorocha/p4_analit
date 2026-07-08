class Parser:
    def build_prompt(self, flow):
        return f"""
You are a network traffic classifier.

Classify the flow below as:
- ELEPHANT_FLOW
- NORMAL_FLOW

Rules:
- ELEPHANT if bytes > 100MB OR long duration OR high throughput
- otherwise NORMAL

Flow:
{flow}

Return JSON only:
{{
  "classification": "...",
  "confidence": 0.0-1.0,
  "reason": "..."
}}
"""
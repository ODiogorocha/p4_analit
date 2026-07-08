import json
from config import ELEPHANT_BYTES_THRESHOLD
from llm.ollama_client import OllamaClient
from utils.timer import Timer

class Controller:
    def __init__(self):
        self.llm = OllamaClient()

    def analyze_window(self, flows):
        timer = Timer()
        timer.start()

        total_bytes = sum(f["bytes"] for f in flows)
        flow = flows[-1]

        # HARD RULE
        if total_bytes > ELEPHANT_BYTES_THRESHOLD:
            result = {
                "classification": "ELEPHANT_FLOW",
                "confidence": 1.0,
                "reason": "Hard rule threshold exceeded"
            }
            elapsed = timer.stop()
            print("[LLM TIME]", elapsed)
            return result

        # LLM fallback
        prompt = f"""
You are a network analyzer.
Classify traffic as ELEPHANT_FLOW or NORMAL.

Flow:
{json.dumps(flow)}

Return JSON only.
"""

        response = self.llm.ask(prompt)

        elapsed = timer.stop()
        print("[LLM TIME]", elapsed)

        return response
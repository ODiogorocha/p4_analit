import requests
import json
from config import OLLAMA_URL, MODEL

class OllamaClient:
    def ask(self, prompt: str):
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }

        r = requests.post(OLLAMA_URL, json=payload)
        return r.json()["response"]
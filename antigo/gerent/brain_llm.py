import requests

def analyze_flow(bytes_count):
    if bytes_count > 500000:
        return "ELEPHANT"
    return "NORMAL"

def call_phi3(flow_bytes):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "phi3",
            "prompt": f"Flow com {flow_bytes} bytes. Classifique e sugira ação."
        }
    )

    return response.json()
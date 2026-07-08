import requests

url = "http://127.0.0.1:11434/api/generate"

payload = {
    "model": "phi:2.7b",
    "prompt": "What is TCP?",
    "stream": False
}

response = requests.post(url, json=payload, timeout=120)

print(response.status_code)
print(response.text)
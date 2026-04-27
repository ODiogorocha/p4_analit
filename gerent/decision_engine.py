import json

def load_decision():
    try:
        with open("../json/decisions.json") as f:
            return json.load(f)
    except:
        return {}

def apply():
    decision = load_decision()

    print("⚡ Aplicando decisão:", decision)

if __name__ == "__main__":
    apply()
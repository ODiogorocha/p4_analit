from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime
import threading
import time

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
THRESHOLD = 500000

# Define o caminho absoluto para a pasta json
BASE_DIR = "/home/diogo/Documentos/codigos/p4_analit"
JSON_DIR = os.path.join(BASE_DIR, "json")
TELEMETRY_FILE = os.path.join(JSON_DIR, "telemetry.json")
DECISIONS_FILE = os.path.join(JSON_DIR, "decisions.json")

# Garante que a pasta json existe
os.makedirs(JSON_DIR, exist_ok=True)

@app.route("/telemetry", methods=["POST"])
def receive():
    try:
        flows = request.json
        print(f"\n📥 [{datetime.now().strftime('%H:%M:%S')}] Recebidos {len(flows)} flows")
        print(f"   Dados: {json.dumps(flows, indent=2)}")
        
        # Salva os dados recebidos
        with open(TELEMETRY_FILE, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "flows": flows
            }, f, indent=2)
        
        print(f"💾 Telemetria salva em: {TELEMETRY_FILE}")
        
        # Inicia processamento em background
        thread = threading.Thread(target=process_with_ollama, args=(flows,))
        thread.daemon = True
        thread.start()
        
        # Responde imediatamente
        return jsonify({
            "status": "ok",
            "message": f"Dados recebidos. Processando {len(flows)} flows com IA em background."
        })
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

def process_with_ollama(flows):
    """Processa os flows com Ollama em background"""
    try:
        print(f"🤖 Iniciando processamento com Ollama...")
        
        # Filtra elephant flows
        elephants = [f for f in flows if f.get("bytes", 0) > THRESHOLD]
        
        if not elephants:
            print("ℹ️ Nenhum elephant flow detectado")
            # Salva decisão mesmo assim
            decision = {
                "timestamp": datetime.now().isoformat(),
                "status": "no_elephant_flows",
                "message": "Nenhum elephant flow detectado"
            }
            with open(DECISIONS_FILE, "w") as f:
                json.dump(decision, f, indent=2)
            print(f"💾 Decisão salva: {DECISIONS_FILE}")
            return
        
        print(f"🐘 Processando {len(elephants)} elephant flows com Ollama")
        print(f"   Detalhes: {json.dumps(elephants, indent=2)}")
        
        # Prepara prompt para o Ollama
        prompt = f"""
        Você é um sistema de gerenciamento de rede. Analise estes elephant flows:
        
        {json.dumps(elephants, indent=2)}
        
        Responda APENAS com um JSON no formato:
        {{
            "action": "drop" ou "limit" ou "monitor",
            "reason": "breve explicação",
            "priority": "alta" ou "media" ou "baixa"
        }}
        """
        
        # Chama Ollama
        start_time = time.time()
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi3",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 150
                }
            },
            timeout=120
        )
        
        elapsed_time = time.time() - start_time
        print(f"⏱️ Ollama respondeu em {elapsed_time:.2f} segundos")
        
        if response.status_code == 200:
            result = response.json()
            ollama_response = result.get("response", "")
            print(f"📝 Resposta do Ollama: {ollama_response[:200]}")
            
            # Tenta extrair JSON da resposta
            try:
                import re
                json_match = re.search(r'\{.*\}', ollama_response, re.DOTALL)
                if json_match:
                    decision_data = json.loads(json_match.group())
                else:
                    decision_data = {
                        "action": "monitor",
                        "reason": ollama_response[:200],
                        "priority": "media"
                    }
            except:
                decision_data = {
                    "action": "monitor",
                    "reason": ollama_response[:200],
                    "priority": "media"
                }
            
            # Salva decisão completa
            decision = {
                "timestamp": datetime.now().isoformat(),
                "processing_time": elapsed_time,
                "elephant_flows": elephants,
                "ollama_raw_response": ollama_response,
                "decision": decision_data,
                "model": "phi3"
            }
            
            with open(DECISIONS_FILE, "w") as f:
                json.dump(decision, f, indent=2)
            
            print(f"✅ Decisão salva em: {DECISIONS_FILE}")
            print(f"   Ação: {decision_data.get('action', 'unknown')}")
            print(f"   Razão: {decision_data.get('reason', 'N/A')[:100]}")
            
        else:
            print(f"❌ Ollama retornou erro: {response.status_code}")
            save_error_decision(elephants, f"Ollama erro: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout: Ollama demorou mais de 120 segundos")
        save_error_decision(flows, "Timeout no Ollama")
    except Exception as e:
        print(f"❌ Erro no processamento: {e}")
        save_error_decision(flows, str(e))

def save_error_decision(flows, error_msg):
    """Salva decisão de erro"""
    decision = {
        "timestamp": datetime.now().isoformat(),
        "error": error_msg,
        "elephant_flows": flows,
        "decision": {
            "action": "monitor",
            "reason": f"Erro no processamento: {error_msg}",
            "priority": "baixa"
        }
    }
    with open(DECISIONS_FILE, "w") as f:
        json.dump(decision, f, indent=2)
    print(f"💾 Decisão de erro salva em: {DECISIONS_FILE}")

@app.route("/decisions", methods=["GET"])
def get_decisions():
    """Retorna a última decisão"""
    try:
        if os.path.exists(DECISIONS_FILE):
            with open(DECISIONS_FILE, "r") as f:
                decisions = json.load(f)
            return jsonify(decisions)
        else:
            return jsonify({"message": "Nenhuma decisão ainda"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "ollama": check_ollama(),
        "json_dir": JSON_DIR,
        "decisions_file": DECISIONS_FILE
    })

def check_ollama():
    """Verifica se Ollama está rodando"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧠 BRAIN com Ollama - Sistema de Elephant Flow Detection")
    print("=" * 60)
    print(f"📡 API: http://0.0.0.0:5000")
    print(f"📂 Diretório JSON: {JSON_DIR}")
    print(f"📄 Arquivo decisões: {DECISIONS_FILE}")
    print("=" * 60)
    print(f"✅ Ollama status: {'Rodando' if check_ollama() else 'Parado'}")
    print("🚀 Brain pronto para receber dados...\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

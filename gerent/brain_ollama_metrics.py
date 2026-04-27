from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime
import threading
import time
import psutil
from collections import defaultdict

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
THRESHOLD = 500000

# Métricas globais
BASE_DIR = "/home/diogo/Documentos/codigos/p4_analit"
JSON_DIR = os.path.join(BASE_DIR, "json")
TELEMETRY_FILE = os.path.join(JSON_DIR, "telemetry.json")
DECISIONS_FILE = os.path.join(JSON_DIR, "decisions.json")
METRICS_FILE = os.path.join(JSON_DIR, "performance_metrics.json")

os.makedirs(JSON_DIR, exist_ok=True)

# Armazenar métricas de desempenho
performance_metrics = []

@app.route("/telemetry", methods=["POST"])
def receive():
    try:
        data = request.json
        elephant_flows = data.get("elephant_flows", [])
        agent_metrics = data.get("agent_metrics", {})
        
        brain_start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"📥 [{datetime.now().strftime('%H:%M:%S')}] RECEBIDO ELEPHANT FLOW")
        print(f"{'='*60}")
        print(f"   Flows: {len(elephant_flows)}")
        
        for flow in elephant_flows:
            print(f"\n   🐘 Flow detectado:")
            print(f"      Origem: {flow['src_ip']}")
            print(f"      Destino: {flow['dst_ip']}")
            print(f"      Bytes: {flow['bytes']} ({flow['bytes']/1024/1024:.2f} MB)")
            print(f"      Pacotes: {flow['packets']}")
            print(f"      Duração detecção: {flow['detection_time']:.2f}s")
            print(f"      Avg packet: {flow['avg_packet_size']:.0f} bytes")
        
        print(f"\n📊 Métricas do Agent:")
        print(f"   Pacotes capturados: {agent_metrics.get('total_packets_captured', 0)}")
        print(f"   Bytes capturados: {agent_metrics.get('total_bytes_captured', 0)}")
        print(f"   Flows ativos: {agent_metrics.get('active_flows', 0)}")
        
        # Salva os dados recebidos
        with open(TELEMETRY_FILE, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "elephant_flows": elephant_flows,
                "agent_metrics": agent_metrics
            }, f, indent=2)
        
        # Processa com Ollama em background
        thread = threading.Thread(target=process_with_ollama, args=(elephant_flows, agent_metrics, brain_start_time))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "ok",
            "message": f"Processando {len(elephant_flows)} flows com IA",
            "timestamp": time.time()
        })
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

def process_with_ollama(elephant_flows, agent_metrics, brain_start_time):
    """Processa os flows com Ollama e coleta métricas"""
    try:
        ollama_start_time = time.time()
        
        print(f"\n🤖 Iniciando processamento com Ollama...")
        
        if not elephant_flows:
            print("ℹ️ Nenhum elephant flow para processar")
            return
        
        # Prepara prompt
        prompt = f"""
        Analise estes elephant flows de rede:
        
        {json.dumps(elephant_flows, indent=2)}
        
        Escolha UMA ação: "marcar", "encaminhar", "dropar", ou "ignorar"
        
        Responda APENAS com JSON:
        {{
            "action": "marcar/encaminhar/dropar/ignorar",
            "reason": "explicação",
            "priority": "alta/media/baixa"
        }}
        """
        
        # Chama Ollama
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi3",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 150}
            },
            timeout=120
        )
        
        ollama_response_time = time.time() - ollama_start_time
        
        if response.status_code == 200:
            result = response.json()
            ollama_response = result.get("response", "")
            
            # Extrai decisão
            try:
                import re
                json_match = re.search(r'\{.*\}', ollama_response, re.DOTALL)
                if json_match:
                    decision_data = json.loads(json_match.group())
                else:
                    decision_data = {"action": "marcar", "reason": ollama_response[:200], "priority": "media"}
            except:
                decision_data = {"action": "marcar", "reason": ollama_response[:200], "priority": "media"}
            
            total_time = time.time() - brain_start_time
            
            # Coleta métricas completas
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "detection_metrics": {
                    "agent_detection_time": elephant_flows[0].get("detection_time", 0) if elephant_flows else 0,
                    "brain_processing_time": ollama_response_time,
                    "total_time_to_decision": total_time,
                    "ollama_response_time": ollama_response_time,
                    "end_to_end_latency": total_time + elephant_flows[0].get("detection_time", 0) if elephant_flows else total_time
                },
                "traffic_metrics": {
                    "total_bytes": elephant_flows[0]["bytes"] if elephant_flows else 0,
                    "total_packets": elephant_flows[0]["packets"] if elephant_flows else 0,
                    "avg_packet_size": elephant_flows[0]["avg_packet_size"] if elephant_flows else 0,
                    "flow_duration": elephant_flows[0]["duration"] if elephant_flows else 0
                },
                "system_metrics": {
                    "agent_cpu": agent_metrics.get("system_metrics", {}).get("cpu_percent", 0),
                    "agent_memory": agent_metrics.get("system_metrics", {}).get("memory_percent", 0),
                    "brain_cpu": psutil.cpu_percent(interval=0.1),
                    "brain_memory": psutil.virtual_memory().percent
                },
                "decision": decision_data,
                "elephant_flow": elephant_flows[0] if elephant_flows else {}
            }
            
            # Salva decisão
            decision = {
                "timestamp": datetime.now().isoformat(),
                "processing_time": ollama_response_time,
                "total_time": total_time,
                "elephant_flows": elephant_flows,
                "decision": decision_data,
                "metrics": metrics
            }
            
            with open(DECISIONS_FILE, "w") as f:
                json.dump(decision, f, indent=2)
            
            # Salva métricas para pesquisa
            performance_metrics.append(metrics)
            with open(METRICS_FILE, "w") as f:
                json.dump(performance_metrics, f, indent=2)
            
            print(f"\n{'='*60}")
            print(f"✅ DECISÃO DA IA")
            print(f"{'='*60}")
            print(f"   Ação: {decision_data.get('action', 'unknown')}")
            print(f"   Razão: {decision_data.get('reason', 'N/A')[:100]}")
            print(f"   Prioridade: {decision_data.get('priority', 'N/A')}")
            print(f"\n⏱️  MÉTRICAS DE TEMPO:")
            print(f"   Detecção pelo Agent: {metrics['detection_metrics']['agent_detection_time']:.3f}s")
            print(f"   Processamento Ollama: {ollama_response_time:.3f}s")
            print(f"   Tempo total (Brain): {total_time:.3f}s")
            print(f"   End-to-end: {metrics['detection_metrics']['end_to_end_latency']:.3f}s")
            print(f"\n📊 MÉTRICAS DE TRÁFEGO:")
            print(f"   Total bytes: {metrics['traffic_metrics']['total_bytes']} ({metrics['traffic_metrics']['total_bytes']/1024/1024:.2f} MB)")
            print(f"   Total pacotes: {metrics['traffic_metrics']['total_packets']}")
            print(f"   Tamanho médio: {metrics['traffic_metrics']['avg_packet_size']:.0f} bytes")
            print(f"{'='*60}\n")
            
        else:
            print(f"❌ Ollama erro: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        save_error_metrics(elephant_flows, str(e))

def save_error_metrics(flows, error_msg):
    """Salva métricas de erro"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "error": error_msg,
        "elephant_flows": flows
    }
    performance_metrics.append(metrics)
    with open(METRICS_FILE, "w") as f:
        json.dump(performance_metrics, f, indent=2)

@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Retorna todas as métricas coletadas"""
    return jsonify(performance_metrics)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "ollama": check_ollama()})

def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("🧠 BRAIN com Métricas - Elephant Flow Manager")
    print("=" * 70)
    print(f"📡 API: http://0.0.0.0:5000")
    print(f"📂 Métricas salvas em: {METRICS_FILE}")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

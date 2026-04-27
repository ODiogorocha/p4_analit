from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime
import threading
import time
import signal
import sys

app = Flask(__name__)

# Configurações
OLLAMA_URL = "http://localhost:11434/api/generate"
THRESHOLD = 500000

# Diretórios
BASE_DIR = "/home/diogo/Documentos/codigos/p4_analit"
JSON_DIR = os.path.join(BASE_DIR, "json")
METRICS_FILE = os.path.join(JSON_DIR, "research_metrics.json")
DECISIONS_FILE = os.path.join(JSON_DIR, "decisions.json")

os.makedirs(JSON_DIR, exist_ok=True)

# Armazenamento de métricas
session_metrics = {
    "start_time": time.time(),
    "detections": [],
    "total_ollama_calls": 0,
    "total_ollama_time": 0,
    "avg_ollama_time": 0
}

@app.route("/telemetry", methods=["POST"])
def receive():
    try:
        data = request.json
        elephant_flows = data.get("elephant_flows", [])
        agent_metrics = data.get("agent_metrics", {})
        
        # Tempo de início do processamento no Brain
        brain_start_time = time.time()
        
        print(f"\n{'='*70}")
        print(f"📥 [{datetime.now().strftime('%H:%M:%S')}] ELEPHANT FLOW RECEBIDO")
        print(f"{'='*70}")
        
        for flow in elephant_flows:
            print(f"   🐘 {flow['src_ip']} → {flow['dst_ip']}")
            print(f"      Bytes: {flow['bytes']} ({flow['bytes']/1024/1024:.2f} MB)")
            print(f"      Pacotes: {flow['packets']}")
            print(f"      Tempo detecção Agent: {flow.get('detection_time', 0):.3f}s")
        
        # Processa com Ollama e mede tempo
        result = process_with_ollama_timed(elephant_flows, agent_metrics, brain_start_time)
        
        return jsonify({"status": "ok", "processing_time": result.get("ollama_time", 0)})
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

def process_with_ollama_timed(elephant_flows, agent_metrics, brain_start_time):
    """Processa com Ollama e mede o tempo exato"""
    
    detection_record = {
        "detection_id": len(session_metrics["detections"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "unix_timestamp": time.time(),
        "elephant_flow": elephant_flows[0] if elephant_flows else {},
        "agent_metrics": agent_metrics,
        "ollama_timing": {},
        "decision": {}
    }
    
    if not elephant_flows:
        detection_record["error"] = "No elephant flows"
        session_metrics["detections"].append(detection_record)
        save_metrics()
        return {"ollama_time": 0}
    
    print(f"\n🤖 INICIANDO CONSULTA AO OLLAMA...")
    print(f"   Modelo: phi3")
    print(f"   Timeout: 600 segundos (10 minutos)")
    
    # Marca o início da consulta
    ollama_start = time.time()
    detection_record["ollama_timing"]["ollama_call_start"] = ollama_start
    
    prompt = f"""
    Você é um especialista em redes. Analise este elephant flow:
    
    Origem: {elephant_flows[0]['src_ip']}
    Destino: {elephant_flows[0]['dst_ip']}
    Bytes: {elephant_flows[0]['bytes']} ({elephant_flows[0]['bytes']/1024/1024:.2f} MB)
    Pacotes: {elephant_flows[0]['packets']}
    Duração: {elephant_flows[0].get('duration', 0):.2f}s
    
    Responda APENAS com JSON:
    {{
        "action": "marcar",
        "reason": "explicação",
        "priority": "alta"
    }}
    """
    
    try:
        # Chamada ao Ollama com timeout máximo
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi3",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200,
                    "stop": ["</s>"]
                }
            },
            timeout=600  # 10 minutos de timeout
        )
        
        # Tempo que o Ollama levou
        ollama_end = time.time()
        ollama_duration = ollama_end - ollama_start
        
        detection_record["ollama_timing"]["ollama_call_end"] = ollama_end
        detection_record["ollama_timing"]["ollama_duration_seconds"] = ollama_duration
        
        print(f"\n⏱️ OLLAMA RESPONDEU EM: {ollama_duration:.3f} segundos")
        
        if response.status_code == 200:
            result = response.json()
            ollama_response = result.get("response", "")
            
            # Tenta extrair JSON da resposta
            try:
                import re
                json_match = re.search(r'\{.*\}', ollama_response, re.DOTALL)
                if json_match:
                    decision_data = json.loads(json_match.group())
                else:
                    decision_data = {
                        "action": "marcar",
                        "reason": ollama_response[:200],
                        "priority": "media"
                    }
            except:
                decision_data = {
                    "action": "marcar",
                    "reason": ollama_response[:200],
                    "priority": "media"
                }
            
            detection_record["decision"] = decision_data
            detection_record["ollama_raw_response"] = ollama_response
            
            # Tempos totais
            total_brain_time = time.time() - brain_start_time
            end_to_end_time = total_brain_time + elephant_flows[0].get("detection_time", 0)
            
            detection_record["timing_summary"] = {
                "agent_detection_time": elephant_flows[0].get("detection_time", 0),
                "ollama_processing_time": ollama_duration,
                "brain_total_time": total_brain_time,
                "end_to_end_total_time": end_to_end_time
            }
            
            print(f"\n{'='*70}")
            print(f"📊 RESUMO DE TEMPOS - ID: {detection_record['detection_id']}")
            print(f"{'='*70}")
            print(f"   ⏱️  Detecção pelo Agent: {detection_record['timing_summary']['agent_detection_time']:.3f}s")
            print(f"   ⏱️  Processamento Ollama: {ollama_duration:.3f}s")
            print(f"   ⏱️  Processamento Brain: {total_brain_time:.3f}s")
            print(f"   ⏱️  TEMPO TOTAL (End-to-End): {end_to_end_time:.3f}s")
            print(f"{'='*70}\n")
            
            # Atualiza estatísticas globais
            session_metrics["total_ollama_calls"] += 1
            session_metrics["total_ollama_time"] += ollama_duration
            session_metrics["avg_ollama_time"] = session_metrics["total_ollama_time"] / session_metrics["total_ollama_calls"]
            
        else:
            detection_record["error"] = f"Ollama HTTP {response.status_code}"
            print(f"❌ Ollama erro: {response.status_code}")
            
    except requests.exceptions.Timeout:
        ollama_duration = 600  # Timeout máximo
        detection_record["error"] = "Timeout após 600 segundos"
        detection_record["ollama_timing"]["ollama_duration_seconds"] = ollama_duration
        print(f"❌ TIMEOUT! Ollama não respondeu após {ollama_duration} segundos")
        
    except Exception as e:
        detection_record["error"] = str(e)
        print(f"❌ Erro: {e}")
    
    # Salva os dados
    session_metrics["detections"].append(detection_record)
    save_metrics()
    
    # Salva decisão atual
    save_decision(detection_record)
    
    return {"ollama_time": detection_record.get("ollama_timing", {}).get("ollama_duration_seconds", 0)}

def save_metrics():
    """Salva todas as métricas da sessão"""
    session_metrics["current_time"] = time.time()
    session_metrics["session_duration"] = session_metrics["current_time"] - session_metrics["start_time"]
    
    with open(METRICS_FILE, "w") as f:
        json.dump(session_metrics, f, indent=2)
    
    print(f"\n💾 Métricas salvas: {METRICS_FILE}")

def save_decision(record):
    """Salva a decisão mais recente"""
    decision_summary = {
        "timestamp": record["timestamp"],
        "detection_id": record["detection_id"],
        "elephant_flow": record["elephant_flow"],
        "decision": record["decision"],
        "timing": record.get("timing_summary", {}),
        "ollama_time": record.get("ollama_timing", {}).get("ollama_duration_seconds", 0)
    }
    
    with open(DECISIONS_FILE, "w") as f:
        json.dump(decision_summary, f, indent=2)

@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Retorna todas as métricas"""
    return jsonify(session_metrics)

@app.route("/metrics/reset", methods=["POST"])
def reset_metrics():
    """Reseta as métricas"""
    global session_metrics
    session_metrics = {
        "start_time": time.time(),
        "detections": [],
        "total_ollama_calls": 0,
        "total_ollama_time": 0,
        "avg_ollama_time": 0
    }
    return jsonify({"status": "reset"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "detections": len(session_metrics["detections"]),
        "avg_ollama_time": session_metrics["avg_ollama_time"]
    })

def signal_handler(sig, frame):
    print("\n\n" + "="*70)
    print("📊 RELATÓRIO FINAL DA SESSÃO")
    print("="*70)
    print(f"Total de detecções: {len(session_metrics['detections'])}")
    print(f"Total chamadas Ollama: {session_metrics['total_ollama_calls']}")
    print(f"Tempo total Ollama: {session_metrics['total_ollama_time']:.3f}s")
    print(f"Tempo médio Ollama: {session_metrics['avg_ollama_time']:.3f}s")
    print(f"Duração da sessão: {time.time() - session_metrics['start_time']:.3f}s")
    print("="*70)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("="*70)
    print("🧠 BRAIN RESEARCH - Elephant Flow Detection")
    print("="*70)
    print(f"📡 API: http://0.0.0.0:5000")
    print(f"📂 Métricas: {METRICS_FILE}")
    print(f"⏱️  Timeout Ollama: 600 segundos (10 minutos)")
    print("="*70)
    print("\n✅ Brain pronto para pesquisa!\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

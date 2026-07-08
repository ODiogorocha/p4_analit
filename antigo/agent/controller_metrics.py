from scapy.all import sniff, IP
import time
import requests
import json
from collections import defaultdict
import threading
import psutil
import os

# Configuração
BRAIN_URL = "http://10.0.0.101:5000/telemetry"
THRESHOLD = 500000  # 500KB
REPORT_INTERVAL = 10

# Métricas
flows = defaultdict(lambda: {"bytes": 0, "packets": 0, "start_time": time.time()})
reported_flows = set()
start_time = time.time()
total_packets_captured = 0
total_bytes_captured = 0

def get_system_metrics():
    """Coleta métricas do sistema"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "network_bytes_sent": psutil.net_io_counters().bytes_sent,
        "network_bytes_recv": psutil.net_io_counters().bytes_recv
    }

def send_to_brain(elephant_flows, detection_time):
    """Envia elephant flows para o Brain com métricas"""
    try:
        payload = []
        for flow in elephant_flows:
            src, dst = flow
            flow_data = flows[flow]
            payload.append({
                "src_ip": src,
                "dst_ip": dst,
                "bytes": flow_data["bytes"],
                "packets": flow_data["packets"],
                "duration": time.time() - flow_data["start_time"],
                "avg_packet_size": flow_data["bytes"] / flow_data["packets"] if flow_data["packets"] > 0 else 0,
                "detection_time": detection_time,
                "timestamp": time.time()
            })
        
        if payload:
            # Coleta métricas do sistema
            system_metrics = get_system_metrics()
            
            agent_metrics = {
                "agent_start_time": start_time,
                "detection_timestamp": time.time(),
                "total_packets_captured": total_packets_captured,
                "total_bytes_captured": total_bytes_captured,
                "active_flows": len(flows),
                "reported_flows": len(reported_flows),
                "system_metrics": system_metrics
            }
            
            print(f"\n📊 MÉTRICAS DO AGENT:")
            print(f"   Total de pacotes: {total_packets_captured}")
            print(f"   Total de bytes: {total_bytes_captured} ({total_bytes_captured/1024/1024:.2f} MB)")
            print(f"   Flows ativos: {len(flows)}")
            print(f"   CPU: {system_metrics['cpu_percent']}%")
            print(f"   Memória: {system_metrics['memory_percent']}%")
            
            print(f"\n📤 Enviando {len(payload)} elephant flows para o Brain...")
            response = requests.post(
                BRAIN_URL,
                json={
                    "elephant_flows": payload,
                    "agent_metrics": agent_metrics
                },
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✅ Brain respondeu: {response.json()}")
                for flow in elephant_flows:
                    reported_flows.add(flow)
            else:
                print(f"❌ Brain erro: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")

def process_packet(pkt):
    global total_packets_captured, total_bytes_captured
    
    if IP in pkt:
        src = pkt[IP].src
        dst = pkt[IP].dst
        key = (src, dst)
        size = len(pkt)
        
        total_packets_captured += 1
        total_bytes_captured += size
        
        # Atualiza métricas do flow
        flows[key]["bytes"] += size
        flows[key]["packets"] += 1
        
        # Mostra a cada 100 pacotes
        if total_packets_captured % 100 == 0:
            print(f"📊 Status: {total_packets_captured} pacotes | {total_bytes_captured/1024/1024:.2f} MB | {len(flows)} flows")
        
        # Detecta elephant flow
        if flows[key]["bytes"] > THRESHOLD and key not in reported_flows:
            detection_time = time.time() - flows[key]["start_time"]
            print(f"\n{'='*60}")
            print(f"🐘 ELEPHANT FLOW DETECTADO!")
            print(f"   Origem: {src}")
            print(f"   Destino: {dst}")
            print(f"   Bytes: {flows[key]['bytes']} ({flows[key]['bytes']/1024/1024:.2f} MB)")
            print(f"   Pacotes: {flows[key]['packets']}")
            print(f"   Duração: {detection_time:.2f} segundos")
            print(f"   Avg packet: {flows[key]['bytes']/flows[key]['packets']:.0f} bytes")
            print(f"{'='*60}\n")
            
            send_to_brain([key], detection_time)

def run():
    global start_time
    start_time = time.time()
    
    print("=" * 70)
    print("🤖 AGENT - Elephant Flow Detector com Métricas")
    print("=" * 70)
    print(f"📡 Brain URL: {BRAIN_URL}")
    print(f"📊 Threshold: {THRESHOLD} bytes ({THRESHOLD/1024/1024:.1f} MB)")
    print(f"⏰ Início: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\n✅ Agent pronto! Capturando métricas...\n")
    
    try:
        sniff(prn=process_packet, store=0)
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("📊 RELATÓRIO FINAL DO AGENT")
        print("="*70)
        print(f"Tempo total: {time.time() - start_time:.2f} segundos")
        print(f"Total de pacotes: {total_packets_captured}")
        print(f"Total de bytes: {total_bytes_captured} ({total_bytes_captured/1024/1024:.2f} MB)")
        print(f"Flows detectados: {len(flows)}")
        print(f"Elephant flows: {len(reported_flows)}")
        print("="*70)

if __name__ == "__main__":
    run()

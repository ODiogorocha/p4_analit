from scapy.all import sniff, IP, conf
import time
import requests
import json
from collections import defaultdict
import threading
import sys

# Configuração
BRAIN_URL = "http://10.0.0.101:5000/telemetry"
THRESHOLD = 500000
REPORT_INTERVAL = 10

flows = defaultdict(int)
reported_flows = set()

def send_to_brain(elephant_flows):
    """Envia elephant flows para o Brain"""
    try:
        payload = []
        for flow in elephant_flows:
            src, dst = flow
            payload.append({
                "src_ip": src,
                "dst_ip": dst,
                "bytes": flows[flow],
                "timestamp": time.time()
            })
        
        if payload:
            print(f"\n📤 Enviando {len(payload)} elephant flows para o Brain...")
            response = requests.post(
                BRAIN_URL,
                json=payload,
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
    if IP in pkt:
        src = pkt[IP].src
        dst = pkt[IP].dst
        key = (src, dst)
        size = len(pkt)
        
        flows[key] += size
        
        # Mostra cada pacote capturado (para debug)
        print(f"📦 {src} → {dst} | {size} bytes | Total: {flows[key]}")
        
        if flows[key] > THRESHOLD and key not in reported_flows:
            print(f"\n{'='*50}")
            print(f"🐘 ELEPHANT FLOW DETECTADO!")
            print(f"   Origem: {src}")
            print(f"   Destino: {dst}")
            print(f"   Bytes: {flows[key]} ({flows[key]/1024/1024:.2f} MB)")
            print(f"{'='*50}\n")
            send_to_brain([key])

def run():
    print("=" * 60)
    print("🤖 AGENT - Elephant Flow Detector")
    print("=" * 60)
    print(f"📡 Brain URL: {BRAIN_URL}")
    print(f"📊 Threshold: {THRESHOLD} bytes ({THRESHOLD/1024/1024:.1f} MB)")
    print("=" * 60)
    print("\n✅ Agent pronto! Capturando pacotes...\n")
    
    # Lista interfaces
    from scapy.all import get_if_list
    ifaces = get_if_list()
    print(f"📡 Interfaces disponíveis: {ifaces}")
    print("🔍 Capturando em TODAS as interfaces...\n")
    
    # Sniff em todas as interfaces
    sniff(prn=process_packet, store=0)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n👋 Agent finalizado")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Erro: {e}")

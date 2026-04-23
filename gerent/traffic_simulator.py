#!/usr/bin/env python3
"""
Simulador de Tráfego - Funciona sem Mininet para testes
Gera dados fictícios de telemetria que parecem reais
"""

import json
import random
import time
import sys
import os
from datetime import datetime

def generate_fake_traffic():
    """Gera dados fictícios de tráfego para simular sem Mininet"""
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║     🎬 MODO SIMULADO - Gerando tráfego fictício             ║
    ║        (Mininet não disponível, usando dados sintéticos)    ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    telemetry_file = "json/telemetry_storage.json"
    
    # Limpar arquivo anterior
    if os.path.exists(telemetry_file):
        os.remove(telemetry_file)
    
    print("\n" + "="*60)
    print("Gerando 120 segundos de tráfego simulado...")
    print("="*60)
    
    for second in range(120):
        # Simula diferentes fases
        if second < 30:
            # Fase 1: Tráfego leve normal
            num_flows = random.randint(3, 8)
            avg_bytes = random.randint(10000, 50000)
            phase = "NORMAL"
        elif second < 60:
            # Fase 2: Tráfego com elephant
            num_flows = random.randint(4, 12)
            avg_bytes = random.randint(100000, 1000000)
            phase = "ELEPHANT"
        elif second < 90:
            # Fase 3: Tráfego misto
            num_flows = random.randint(8, 20)
            avg_bytes = random.randint(50000, 500000)
            phase = "MULTI"
        else:
            # Fase 4: Apenas elephant
            num_flows = random.randint(2, 6)
            avg_bytes = random.randint(500000, 2000000)
            phase = "ELEPHANT"
        
        # Gerar fluxos
        flows = []
        for i in range(num_flows):
            flow = {
                "idx": i,
                "src_ip": f"10.0.0.{random.randint(1,4)}",
                "dst_ip": f"10.0.0.{random.randint(1,4)}",
                "src_port": random.randint(10000, 60000),
                "dst_port": random.choice([80, 443, 5201, 5555, 53, 22]),
                "proto_name": random.choice(["TCP", "UDP", "ICMP"]),
                "bytes": random.randint(int(avg_bytes*0.5), int(avg_bytes*1.5)),
                "pkts": random.randint(100, 5000)
            }
            flows.append(flow)
        
        # Dados de telemetria
        telemetry = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "flows": flows,
            "total_flows": len(flows),
            "total_bytes": sum(f["bytes"] for f in flows),
            "total_pkts": sum(f["pkts"] for f in flows)
        }
        
        # Salvar
        with open(telemetry_file, 'a') as f:
            f.write(json.dumps(telemetry) + "\n")
        
        # Exibir progresso
        if second % 30 == 0:
            elephant_count = len([f for f in flows if f["bytes"] > 1000000])
            print(f"\n[{second}s] Fase: {phase:8} | Fluxos: {len(flows):2d} | Elefantes: {elephant_count} | Volume: {sum(f['bytes'] for f in flows)/1e6:.1f}MB")
        
        time.sleep(1)
    
    print("\n" + "="*60)
    print("✅ Tráfego simulado completo (120s)!")
    print(f"📊 Total de telemetrias: 120")
    print(f"📁 Arquivo: {telemetry_file}")
    print("="*60)


if __name__ == '__main__':
    try:
        generate_fake_traffic()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupção do usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)

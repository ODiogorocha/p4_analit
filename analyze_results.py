#!/usr/bin/env python3
"""
Analisador de Resultados - Processa dados coletados e gera insights
"""

import json
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path


def analyze_decisions(decisions_file):
    """Analisa padrões de decisões tomadas"""
    
    if not os.path.exists(decisions_file):
        print("⚠️  Arquivo de decisões não encontrado")
        return
    
    print("\n📊 ANÁLISE DE DECISÕES LLM")
    print("─" * 60)
    
    decisions = []
    with open(decisions_file, 'r') as f:
        for line in f:
            try:
                decisions.append(json.loads(line.strip()))
            except:
                pass
    
    if not decisions:
        print("Sem decisões registradas")
        return
    
    # Contadores
    action_count = defaultdict(int)
    latencies = []
    
    for dec in decisions:
        action = dec.get('action', 'UNKNOWN')
        action_count[action] += 1
        latencies.append(dec.get('latency_ms', 0))
    
    # Exibir results
    print(f"\nTotal de decisões: {len(decisions)}")
    print(f"Primeiras: {decisions[0].get('timestamp')}")
    print(f"Últimas: {decisions[-1].get('timestamp')}")
    
    print(f"\nDistribuição de ações:")
    for action in sorted(action_count.keys()):
        count = action_count[action]
        percentage = (count / len(decisions)) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {action:12} {count:3d} ({percentage:5.1f}%) {bar}")
    
    # Latência
    print(f"\nLatência (ms):")
    print(f"  Mínima:  {min(latencies):.1f}")
    print(f"  Máxima:  {max(latencies):.1f}")
    print(f"  Média:   {sum(latencies)/len(latencies):.1f}")


def analyze_traffic(telemetry_file):
    """Analisa padrões de tráfego"""
    
    if not os.path.exists(telemetry_file):
        print("⚠️  Arquivo de telemetria não encontrado")
        return
    
    print("\n📈 ANÁLISE DE TRÁFEGO")
    print("─" * 60)
    
    telemetries = []
    with open(telemetry_file, 'r') as f:
        for line in f:
            try:
                telemetries.append(json.loads(line.strip()))
            except:
                pass
    
    if not telemetries:
        print("Sem telemetrias registradas")
        return
    
    # Estatísticas
    total_bytes_all = 0
    total_packets_all = 0
    flow_counts = []
    elephant_counts = []
    
    for telem in telemetries:
        flows = telem.get('flows', [])
        total_bytes = sum(f.get('bytes', 0) for f in flows)
        total_packets = sum(f.get('pkts', 0) for f in flows)
        elephants = len([f for f in flows if f.get('bytes', 0) > 1000000])
        
        total_bytes_all += total_bytes
        total_packets_all += total_packets
        flow_counts.append(len(flows))
        elephant_counts.append(elephants)
    
    print(f"\nTotal de telemetrias: {len(telemetries)}")
    print(f"Total de bytes transmitidos: {total_bytes_all / 1e9:.3f} GB")
    print(f"Total de pacotes: {total_packets_all}")
    
    print(f"\nFluxos:")
    print(f"  Mínimo: {min(flow_counts)}")
    print(f"  Máximo: {max(flow_counts)}")
    print(f"  Médio:  {sum(flow_counts)/len(flow_counts):.1f}")
    
    print(f"\nFluxos Elefante:")
    print(f"  Eventos com elefante: {sum(1 for x in elephant_counts if x > 0)}")
    print(f"  Máximo em um evento: {max(elephant_counts) if elephant_counts else 0}")
    
    # Protocolos mais comuns
    from collections import Counter
    protocols = []
    for telem in telemetries:
        for flow in telem.get('flows', []):
            protocols.append(flow.get('proto_name', 'UNKNOWN'))
    
    proto_counts = Counter(protocols)
    print(f"\nProtocolos mais comuns:")
    for proto, count in proto_counts.most_common():
        print(f"  {proto}: {count}")


def generate_summary_report(project_root):
    """Gera relatório resumido"""
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║          📋 ANÁLISE DE RESULTADOS DO SISTEMA               ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"\n📁 Projeto: {project_root}")
    print(f"🕐 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "─" * 60)
    
    # Analisar cada arquivo
    analyze_decisions(os.path.join(project_root, "json/decisions.json"))
    analyze_traffic(os.path.join(project_root, "json/telemetry_storage.json"))
    
    # Resumo de arquivos
    print("\n📂 ARQUIVOS GERADOS")
    print("─" * 60)
    
    files_info = {
        "json/telemetry_storage.json": "Telemetrias coletadas",
        "json/decisions.json": "Decisões LLM",
        "rules_applied.json": "Regras aplicadas",
        "metrics_history.json": "Histórico de métricas",
        "analysis_report.json": "Relatório estruturado",
        "orchestrator.log": "Log de execução"
    }
    
    total_size = 0
    for filename, description in files_info.items():
        filepath = os.path.join(project_root, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            total_size += size
            
            # Contar linhas
            try:
                with open(filepath, 'r') as f:
                    lines = len(f.readlines())
                    print(f"✅ {filename:25} ({lines:5d} linhas, {size/1024:8.1f} KB) - {description}")
            except:
                print(f"⚠️  {filename:25} ({size/1024:8.1f} KB) - {description}")
        else:
            print(f"❌ {filename:25} - {description} (NÃO ENCONTRADO)")
    
    print(f"\nTotal em disco: {total_size / 1024 / 1024:.2f} MB")
    
    print("\n" + "─" * 60)
    print("✅ Análise completa!")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analisador de Resultados - Insights sobre análise de tráfego"
    )
    parser.add_argument(
        "--project-root",
        default="/home/diogo/Documentos/codigos/p4_analit",
        help="Caminho raiz do projeto"
    )
    
    args = parser.parse_args()
    
    generate_summary_report(args.project_root)


if __name__ == '__main__':
    main()

import json
import matplotlib.pyplot as plt
import numpy as np

# Carregar métricas
with open('json/performance_metrics.json', 'r') as f:
    metrics = json.load(f)

print("=" * 60)
print("📊 ANÁLISE DE DESEMPENHO - ELEPHANT FLOW DETECTION")
print("=" * 60)

for i, m in enumerate(metrics, 1):
    if 'error' in m:
        continue
    
    print(f"\n📈 Execução {i}:")
    print(f"   Timestamp: {m['timestamp']}")
    print(f"\n   ⏱️  MÉTRICAS DE TEMPO:")
    print(f"      Detecção pelo Agent: {m['detection_metrics']['agent_detection_time']:.3f} segundos")
    print(f"      Processamento Ollama: {m['detection_metrics']['ollama_response_time']:.3f} segundos")
    print(f"      Tempo total Brain: {m['detection_metrics']['total_time_to_decision']:.3f} segundos")
    print(f"      Latência End-to-End: {m['detection_metrics']['end_to_end_latency']:.3f} segundos")
    
    print(f"\n   📊 MÉTRICAS DE TRÁFEGO:")
    print(f"      Total bytes: {m['traffic_metrics']['total_bytes']:,} ({m['traffic_metrics']['total_bytes']/1024/1024:.2f} MB)")
    print(f"      Total pacotes: {m['traffic_metrics']['total_packets']:,}")
    print(f"      Tamanho médio: {m['traffic_metrics']['avg_packet_size']:.0f} bytes")
    print(f"      Duração do flow: {m['traffic_metrics']['flow_duration']:.3f} segundos")
    
    print(f"\n   🖥️  MÉTRICAS DE SISTEMA:")
    print(f"      CPU Agent: {m['system_metrics']['agent_cpu']}%")
    print(f"      Memória Agent: {m['system_metrics']['agent_memory']}%")
    print(f"      CPU Brain: {m['system_metrics']['brain_cpu']}%")
    print(f"      Memória Brain: {m['system_metrics']['brain_memory']}%")
    
    print(f"\n   🎯 DECISÃO DA IA:")
    print(f"      Ação: {m['decision']['action']}")
    print(f"      Razão: {m['decision']['reason'][:100]}...")

# Calcular estatísticas
detection_times = [m['detection_metrics']['agent_detection_time'] for m in metrics if 'error' not in m]
ollama_times = [m['detection_metrics']['ollama_response_time'] for m in metrics if 'error' not in m]
end_to_end = [m['detection_metrics']['end_to_end_latency'] for m in metrics if 'error' not in m]

print("\n" + "=" * 60)
print("📊 ESTATÍSTICAS GERAIS")
print("=" * 60)
print(f"Total de execuções: {len([m for m in metrics if 'error' not in m])}")
print(f"\nTempo médio de detecção: {np.mean(detection_times):.3f} ± {np.std(detection_times):.3f} s")
print(f"Tempo médio Ollama: {np.mean(ollama_times):.3f} ± {np.std(ollama_times):.3f} s")
print(f"Latência média end-to-end: {np.mean(end_to_end):.3f} ± {np.std(end_to_end):.3f} s")
print(f"Throughput médio: {np.mean([m['traffic_metrics']['total_bytes']/1024/1024 for m in metrics if 'error' not in m]):.2f} MB")

# Salvar relatório
report = {
    "statistics": {
        "num_executions": len([m for m in metrics if 'error' not in m]),
        "avg_detection_time": float(np.mean(detection_times)),
        "std_detection_time": float(np.std(detection_times)),
        "avg_ollama_time": float(np.mean(ollama_times)),
        "std_ollama_time": float(np.std(ollama_times)),
        "avg_end_to_end": float(np.mean(end_to_end)),
        "std_end_to_end": float(np.std(end_to_end))
    },
    "all_metrics": metrics
}

with open('json/research_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n✅ Relatório salvo em json/research_report.json")

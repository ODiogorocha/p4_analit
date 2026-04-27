import json
import time
import statistics

def analyze_metrics():
    print("\n" + "="*70)
    print("📊 ANÁLISE DE DESEMPENHO - TEMPOS DE PROCESSAMENTO")
    print("="*70)
    
    try:
        with open('json/research_metrics.json', 'r') as f:
            data = json.load(f)
        
        detections = data.get('detections', [])
        
        if not detections:
            print("❌ Nenhuma detecção encontrada ainda")
            return
        
        print(f"\n📈 Total de detecções: {len(detections)}")
        print(f"⏱️  Tempo médio Ollama: {data.get('avg_ollama_time', 0):.3f}s")
        print(f"⏱️  Tempo total Ollama: {data.get('total_ollama_time', 0):.3f}s")
        
        print("\n📋 DETALHES POR DETECÇÃO:")
        print("-"*70)
        
        agent_times = []
        ollama_times = []
        end_to_end_times = []
        
        for i, det in enumerate(detections, 1):
            timing = det.get('timing_summary', {})
            agent_time = timing.get('agent_detection_time', 0)
            ollama_time = timing.get('ollama_processing_time', 0)
            e2e_time = timing.get('end_to_end_total_time', 0)
            
            agent_times.append(agent_time)
            ollama_times.append(ollama_time)
            end_to_end_times.append(e2e_time)
            
            print(f"\n🔍 Detecção #{i}:")
            print(f"   Timestamp: {det.get('timestamp', 'N/A')}")
            print(f"   Flow: {det.get('elephant_flow', {}).get('src_ip', 'N/A')} → {det.get('elephant_flow', {}).get('dst_ip', 'N/A')}")
            print(f"   📊 Tráfego: {det.get('elephant_flow', {}).get('bytes', 0)} bytes")
            print(f"   ⏱️  Tempo detecção Agent: {agent_time:.3f}s")
            print(f"   ⏱️  Tempo Ollama: {ollama_time:.3f}s")
            print(f"   ⏱️  Tempo total Brain: {timing.get('brain_total_time', 0):.3f}s")
            print(f"   ⏱️  TEMPO TOTAL (End-to-End): {e2e_time:.3f}s")
            
            decision = det.get('decision', {})
            if decision:
                print(f"   🎯 Decisão: {decision.get('action', 'N/A')}")
                print(f"   💬 Razão: {decision.get('reason', 'N/A')[:100]}")
        
        print("\n" + "="*70)
        print("📊 ESTATÍSTICAS GERAIS")
        print("="*70)
        print(f"Tempo médio de detecção (Agent): {statistics.mean(agent_times):.3f} ± {statistics.stdev(agent_times):.3f}s")
        print(f"Tempo médio de processamento (Ollama): {statistics.mean(ollama_times):.3f} ± {statistics.stdev(ollama_times):.3f}s")
        print(f"Tempo médio End-to-End: {statistics.mean(end_to_end_times):.3f} ± {statistics.stdev(end_to_end_times):.3f}s")
        print(f"\nTempo MÍNIMO Ollama: {min(ollama_times):.3f}s")
        print(f"Tempo MÁXIMO Ollama: {max(ollama_times):.3f}s")
        print("="*70)
        
        # Salva relatório
        report = {
            "summary": {
                "total_detections": len(detections),
                "avg_agent_detection": statistics.mean(agent_times),
                "std_agent_detection": statistics.stdev(agent_times) if len(agent_times) > 1 else 0,
                "avg_ollama_time": statistics.mean(ollama_times),
                "std_ollama_time": statistics.stdev(ollama_times) if len(ollama_times) > 1 else 0,
                "avg_end_to_end": statistics.mean(end_to_end_times),
                "std_end_to_end": statistics.stdev(end_to_end_times) if len(end_to_end_times) > 1 else 0,
                "min_ollama_time": min(ollama_times),
                "max_ollama_time": max(ollama_times)
            },
            "detections": detections
        }
        
        with open('json/research_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n✅ Relatório salvo em: json/research_report.json")
        
    except FileNotFoundError:
        print("❌ Arquivo de métricas não encontrado. Aguarde alguma detecção.")
    except Exception as e:
        print(f"❌ Erro na análise: {e}")

if __name__ == "__main__":
    analyze_metrics()

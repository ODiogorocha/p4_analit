#!/usr/bin/env python3
"""
Monitor Simples - Acompanha execução do sistema com TIMINGS
"""

import os
import json
import time
import sys

def format_time(seconds):
    """Formata tempo em formato legível"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}m {secs:.0f}s"

def get_timing_stats():
    """Lê estatísticas de timing"""
    if os.path.exists("timing_stats.json"):
        try:
            with open("timing_stats.json") as f:
                return json.load(f)
        except:
            return None
    return None

def monitor():
    """Monitora em tempo real"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          📊 MONITOR DO SISTEMA - Com Timings                 ║
    ║     (Pressione Ctrl+C para sair)                             ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    iteration = 0
    
    try:
        while True:
            os.system('clear') if os.name == 'posix' else os.system('cls')
            
            print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          📊 MONITOR DO SISTEMA - Com Timings                 ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
            
            iteration += 1
            
            # Contar registros
            telem_count = 0
            decision_count = 0
            rules_count = 0
            
            if os.path.exists("telemetry_storage.json"):
                try:
                    with open("telemetry_storage.json") as f:
                        telem_count = len(f.readlines())
                except:
                    pass
            
            if os.path.exists("../json/decisions.json"):
                try:
                    with open("../json/decisions.json") as f:
                        decision_count = len(f.readlines())
                except:
                    pass
            
            if os.path.exists("rules_applied.json"):
                try:
                    with open("rules_applied.json") as f:
                        rules_count = len(f.readlines())
                except:
                    pass
            
            # Tentar ler última telemetria
            last_flows = 0
            last_bytes = 0
            last_action = "?"
            
            try:
                if telem_count > 0:
                    with open("telemetry_storage.json") as f:
                        lines = f.readlines()
                        last_telem = json.loads(lines[-1])
                        last_flows = len(last_telem.get("flows", []))
                        last_bytes = sum(f.get("bytes", 0) for f in last_telem.get("flows", []))
            except:
                pass
            
            try:
                if decision_count > 0:
                    with open("decisions.json") as f:
                        lines = f.readlines()
                        last_decision = json.loads(lines[-1])
                        last_action = last_decision.get("action", "?")
            except:
                pass
            
            # Exibir informações básicas
            print(f"Iteração: {iteration}")
            print("─" * 60)
            print()
            print(f"📡 TELEMETRIA")
            print(f"   Total coletado: {telem_count}")
            print(f"   Último fluxos: {last_flows}")
            print(f"   Último volume: {last_bytes/1e6:.2f} MB")
            print()
            print(f"🤖 DECISÕES LLM")
            print(f"   Total de decisões: {decision_count}")
            print(f"   Última ação: {last_action}")
            print()
            print(f"⚙️  REGRAS APLICADAS")
            print(f"   Total de regras: {rules_count}")
            print()
            
            # ⏱️ TIMINGS
            timing_stats = get_timing_stats()
            if timing_stats:
                print(f"⏱️  TIMINGS")
                total_elapsed = timing_stats.get("elapsed_seconds", 0)
                print(f"   ⏳ Tempo total: {format_time(total_elapsed)}")
                
                components = timing_stats.get("components", {})
                for comp_name, comp_data in components.items():
                    start_at = comp_data.get("start_at", 0)
                    events_count = comp_data.get("events_count", 0)
                    
                    if comp_name == "system":
                        print(f"   🖥️  Sistema: {format_time(start_at)} (eventos: {events_count})")
                    elif comp_name == "controller":
                        latencies = [e.get("data", {}).get("latency_ms", 0) for e in comp_data.get("events", []) if "latency_ms" in e.get("data", {})]
                        if latencies:
                            avg_latency = sum(latencies) / len(latencies)
                            print(f"   🎮 Controller: {format_time(start_at)} | Avg latência: {avg_latency:.0f}ms")
                        else:
                            print(f"   🎮 Controller: {format_time(start_at)} (eventos: {events_count})")
                    elif comp_name == "brain_llm":
                        latencies = [e.get("data", {}).get("latency_ms", 0) for e in comp_data.get("events", []) if "latency_ms" in e.get("data", {})]
                        if latencies:
                            avg_latency = sum(latencies) / len(latencies)
                            print(f"   🧠 Brain LLM: {format_time(start_at)} | Avg latência: {avg_latency:.0f}ms ({len(latencies)} decisions)")
                        else:
                            print(f"   🧠 Brain LLM: {format_time(start_at)} (eventos: {events_count})")
                    elif comp_name == "traffic":
                        print(f"   🚗 Tráfego: {format_time(start_at)} (eventos: {events_count})")
                
                print()
            
            print("─" * 60)
            
            if telem_count > 0 and decision_count > 0:
                print("✅ Sistema ativo e gerando dados")
            elif telem_count > 0:
                print("⏳ Aguardando análise LLM...")
            else:
                print("⏳ Aguardando primeiro dado...")
            
            print()
            print("Atualizando a cada 5 segundos...")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitor encerrado")
        sys.exit(0)

if __name__ == '__main__':
    monitor()

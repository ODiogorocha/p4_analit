#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime

DECISIONS_FILE = "/home/diogo/Documentos/codigos/p4_analit/json/decisions.json"

def load_decision():
    """Carrega a última decisão"""
    try:
        with open(DECISIONS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar decisão: {e}")
        return None

def apply_action(flow, action, details):
    """Aplica a ação recomendada pela IA"""
    src_ip = flow.get("src_ip")
    dst_ip = flow.get("dst_ip")
    bytes_flow = flow.get("bytes", 0)
    
    print(f"\n   📍 Flow: {src_ip} → {dst_ip} ({bytes_flow/1024/1024:.2f} MB)")
    
    if action == "dropar":
        print(f"   ✋ Ação: DROP - Bloquear tráfego")
        print(f"   💬 Motivo: {details.get('reason', 'N/A')}")
        # Comando iptables para dropar
        cmd = f"sudo iptables -A FORWARD -s {src_ip} -d {dst_ip} -j DROP 2>/dev/null"
        subprocess.run(cmd, shell=True)
        return "dropped"
        
    elif action == "encaminhar":
        suggested_route = details.get("suggested_route", "rota_alternativa")
        print(f"   🔀 Ação: ENCAMINHAR - Redirecionar para {suggested_route}")
        print(f"   💬 Motivo: {details.get('reason', 'N/A')}")
        # Comando para encaminhar (exemplo com ip route)
        cmd = f"sudo ip route add {dst_ip} via 10.0.0.254 dev eth0 2>/dev/null"
        subprocess.run(cmd, shell=True)
        return "forwarded"
        
    elif action == "marcar":
        priority = details.get("priority", "media")
        print(f"   🏷️  Ação: MARCAR - Monitoramento especial (Prioridade: {priority})")
        print(f"   💬 Motivo: {details.get('reason', 'N/A')}")
        # Marcar pacotes com DSCP
        cmd = f"sudo iptables -t mangle -A FORWARD -s {src_ip} -d {dst_ip} -j DSCP --set-dscp 46 2>/dev/null"
        subprocess.run(cmd, shell=True)
        return "marked"
        
    else:  # ignorar
        print(f"   ⏭️  Ação: IGNORAR - Tráfego normal")
        print(f"   💬 Motivo: {details.get('reason', 'N/A')}")
        return "ignored"

def apply_decision():
    """Aplica a decisão do Ollama"""
    print("\n" + "="*70)
    print("🎯 APLICANDO DECISÃO DA IA - Elephant Flow Manager")
    print("="*70)
    
    decision_data = load_decision()
    
    if not decision_data:
        print("❌ Nenhuma decisão encontrada em:", DECISIONS_FILE)
        return
    
    # Verifica se tem erro
    if "error" in decision_data:
        print(f"⚠️ Decisão com erro: {decision_data.get('error')}")
        action = decision_data.get('decision', {}).get('action', 'marcar')
        print(f"🔄 Ação padrão: {action}")
    
    # Extrai informações
    decision = decision_data.get('decision', {})
    action = decision.get('action', 'ignorar')
    reason = decision.get('reason', 'Sem motivo específico')
    priority = decision.get('priority', 'media')
    bandwidth = decision.get('bandwidth_mbps')
    suggested_route = decision.get('suggested_route')
    
    flows = decision_data.get('elephant_flows', [])
    
    print(f"\n📋 DECISÃO DA IA:")
    print(f"   🎯 Ação: {action.upper()}")
    print(f"   💬 Razão: {reason}")
    print(f"   ⚡ Prioridade: {priority}")
    if bandwidth:
        print(f"   📊 Largura de banda: {bandwidth} Mbps")
    if suggested_route:
        print(f"   🗺️  Rota sugerida: {suggested_route}")
    print(f"   🐘 Flows afetados: {len(flows)}")
    print("-"*70)
    
    # Aplica a ação para cada flow
    results = []
    for flow in flows:
        result = apply_action(flow, action, decision)
        results.append(result)
    
    print("\n" + "="*70)
    print(f"✅ Decisão aplicada com sucesso!")
    print(f"   Ação: {action}")
    print(f"   Flows processados: {len(flows)}")
    print(f"   Resultados: {results}")
    print("="*70 + "\n")
    
    # Salva log da aplicação
    log_file = "/home/diogo/Documentos/codigos/p4_analit/json/application_log.json"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "reason": reason,
        "priority": priority,
        "flows": flows,
        "results": results
    }
    
    try:
        existing_logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                existing_logs = json.load(f)
        
        existing_logs.append(log_entry)
        
        with open(log_file, 'w') as f:
            json.dump(existing_logs, f, indent=2)
        
        print(f"📝 Log salvo em: {log_file}")
    except Exception as e:
        print(f"⚠️ Erro ao salvar log: {e}")

if __name__ == "__main__":
    apply_decision()

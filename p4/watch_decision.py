#!/usr/bin/env python3
"""
watch_decisions.py
Monitora /tmp/elephant_decisions.jsonl em tempo real.
Chamado por: make watch
"""
import sys
import json
import time
import os
from datetime import datetime

JSONL = "/tmp/elephant_decisions.jsonl"

ACAO_ICONS = {
    "DROPAR":     "🔴",
    "MARCAR":     "🟡",
    "FRAGMENTAR": "🔵",
    "ENCAMINHAR": "🟢",
}
URG_ICONS = {
    "CRITICA": "🚨",
    "ALTA":    "⚠️ ",
    "MEDIA":   "ℹ️ ",
    "BAIXA":   "✅",
}

def follow(path):
    """Segue o arquivo como tail -f."""
    while not os.path.exists(path):
        print(f"Aguardando {path}... (Ctrl+C para sair)")
        time.sleep(2)

    with open(path, "r") as f:
        # Pula para o final do arquivo
        f.seek(0, 2)
        print(f"Monitorando {path} (Ctrl+C para sair)\n")
        print(f"{'─'*60}")
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            yield line.strip()

def fmt(d):
    ts  = datetime.fromtimestamp(d.get("t_start", 0)).strftime("%H:%M:%S")
    seq = d.get("seq", "?")
    el  = d.get("elephants", 0)
    mi  = d.get("mice", 0)
    llm = d.get("t_llm_s", 0)
    rul = d.get("rules_sent", 0)
    dt  = d.get("delta_prog_ms", 0)

    print(f"\n[{ts}] seq={seq}")
    print(f"  🐘 Elephants: {el}   🐭 Mice: {mi}")
    print(f"  LLM: {llm:.1f}s   Regras: {rul}   Δt prog: {dt:.0f}ms")

    for a in d.get("actions", []):
        idx   = a.get("flow_idx", "?")
        acao  = a.get("acao", "?").upper()
        urg   = a.get("urgencia", "MEDIA").upper()
        icon  = ACAO_ICONS.get(acao, "  ")
        uicon = URG_ICONS.get(urg, "  ")
        print(f"  {icon} flow #{idx:3}  {acao:12}  {uicon} {urg}")

    print(f"{'─'*60}")

def main():
    try:
        for line in follow(JSONL):
            try:
                d = json.loads(line)
                fmt(d)
            except json.JSONDecodeError:
                pass
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")

if __name__ == "__main__":
    main()
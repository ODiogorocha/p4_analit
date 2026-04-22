#!/usr/bin/env python3
"""
Dashboard de Monitoramento - Visualiza análise em tempo real
Mostra métricas, decisões LLM e ações aplicadas
"""

import json
import os
import time
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path


class DashboardMonitor:
    """Dashboard para monitorar sistema de análise de tráfego"""
    
    def __init__(self, project_root="/home/diogo/Documentos/codigos/p4_analit"):
        self.project_root = project_root
        self.telemetry_file = os.path.join(project_root, "json/telemetry_storage.json")
        self.decisions_file = os.path.join(project_root, "json/decisions.json")
        self.rules_file = os.path.join(project_root, "rules_applied.json")
        self.metrics_history_file = os.path.join(project_root, "metrics_history.json")
        
        self.last_telemetry_lines = 0
        self.last_decision_lines = 0
        self.decision_stats = defaultdict(int)
        self.start_time = None
    
    def _count_file_lines(self, filepath):
        """Conta linhas em arquivo"""
        if not os.path.exists(filepath):
            return 0
        try:
            with open(filepath, 'r') as f:
                return len(f.readlines())
        except:
            return 0
    
    def _read_latest_json(self, filepath, count=1):
        """Lê últimos N registros JSON de arquivo"""
        if not os.path.exists(filepath):
            return []
        
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                records = []
                for line in lines[-count:]:
                    try:
                        records.append(json.loads(line.strip()))
                    except:
                        pass
                return records
        except:
            return []
    
    def _format_bytes(self, bytes_val):
        """Formata bytes para formato legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} TB"
    
    def _print_header(self):
        """Imprime cabeçalho do dashboard"""
        os.system('clear') if os.name == 'posix' else os.system('cls')
        
        uptime = time.time() - self.start_time if self.start_time else 0
        
        print("""
        ╔════════════════════════════════════════════════════════════════════╗
        ║                                                                    ║
        ║   📊 DASHBOARD - ANÁLISE INTELIGENTE DE TRÁFEGO COM PHI3 LLM     ║
        ║                                                                    ║
        ╚════════════════════════════════════════════════════════════════════╝
        """)
        
        print(f"⏱️  Tempo de execução: {uptime:.1f}s")
        print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("─" * 72)
    
    def display_metrics(self):
        """Exibe métricas coletadas"""
        print("\n📈 MÉTRICAS DE TRÁFEGO")
        print("─" * 72)
        
        telemetry_records = self._read_latest_json(self.telemetry_file, count=1)
        metrics_records = self._read_latest_json(self.metrics_history_file, count=3)
        
        if not metrics_records:
            print("⏳ Aguardando métricas...")
            return
        
        # Última métrica
        latest = metrics_records[-1]
        
        print(f"  Fluxos totais: {latest.get('flows', 0)}")
        print(f"  Fluxos elefante: {latest.get('elephant_flows', 0)}")
        print(f"  Fluxos TCP: {latest.get('tcp_flows', 0)}")
        print(f"  Fluxos UDP: {latest.get('udp_flows', 0)}")
        print(f"  Total de bytes: {self._format_bytes(latest.get('total_bytes', 0))}")
        print(f"  Total de pacotes: {latest.get('total_packets', 0)}")
        print(f"  Tamanho médio de pacote: {latest.get('avg_packet_size', 0):.0f} bytes")
        
        # Tendência
        if len(metrics_records) > 1:
            prev = metrics_records[-2]
            delta_flows = latest.get('flows', 0) - prev.get('flows', 0)
            delta_bytes = latest.get('total_bytes', 0) - prev.get('total_bytes', 0)
            
            print(f"\n  📊 Variação desde última coleta:")
            print(f"    Fluxos: {delta_flows:+d}")
            print(f"    Bytes: {self._format_bytes(delta_bytes)}")
    
    def display_decisions(self):
        """Exibe decisões do LLM"""
        print("\n🤖 DECISÕES LLM (ÚLTIMAS 5)")
        print("─" * 72)
        
        decision_records = self._read_latest_json(self.decisions_file, count=5)
        
        if not decision_records:
            print("⏳ Aguardando decisões...")
            return
        
        # Contar decisões por tipo
        decision_counts = defaultdict(int)
        
        for record in decision_records:
            action = record.get('action', 'DESCONHECIDO')
            decision_counts[action] += 1
            
            timestamp = record.get('timestamp', 'N/A')
            latency = record.get('latency_ms', 0)
            metrics = record.get('metrics', {})
            
            print(f"\n  ⏰ {timestamp}")
            print(f"    Ação: {action} | Latência: {latency:.1f}ms")
            print(f"    Fluxos: {metrics.get('flows', 0)} | Elefantes: {metrics.get('elephant_flows', 0)}")
        
        print(f"\n  📊 Resumo decisões:")
        for action, count in sorted(decision_counts.items()):
            bar = "█" * count
            print(f"    {action}: {count} {bar}")
    
    def display_rules(self):
        """Exibe regras aplicadas no switch"""
        print("\n⚙️  REGRAS APLICADAS (ÚLTIMAS 5)")
        print("─" * 72)
        
        rule_records = self._read_latest_json(self.rules_file, count=5)
        
        if not rule_records:
            print("⏳ Aguardando regras...")
            return
        
        for record in rule_records:
            action = record.get('action', 'DESCONHECIDO')
            src = record.get('src', 'N/A')
            dst = record.get('dst', 'N/A')
            flow_id = record.get('flow_id', 'N/A')
            bytes_flow = record.get('bytes', 0)
            
            print(f"  Flow #{flow_id}: {src} → {dst}")
            print(f"    Ação: {action} | Bytes: {self._format_bytes(bytes_flow)}")
    
    def display_stats(self):
        """Exibe estatísticas gerais"""
        print("\n📋 ESTATÍSTICAS")
        print("─" * 72)
        
        telemetry_lines = self._count_file_lines(self.telemetry_file)
        decision_lines = self._count_file_lines(self.decisions_file)
        rules_lines = self._count_file_lines(self.rules_file)
        metrics_lines = self._count_file_lines(self.metrics_history_file)
        
        print(f"  Telemetrias coletadas: {telemetry_lines}")
        print(f"  Decisões tomadas: {decision_lines}")
        print(f"  Regras aplicadas: {rules_lines}")
        print(f"  Métricas histórico: {metrics_lines}")
        
        # Espaço utilizado
        total_size = 0
        for f in [self.telemetry_file, self.decisions_file, self.rules_file, self.metrics_history_file]:
            if os.path.exists(f):
                total_size += os.path.getsize(f)
        
        print(f"  Espaço em disco: {self._format_bytes(total_size)}")
    
    def display_footer(self):
        """Exibe rodapé com controles"""
        print("\n" + "─" * 72)
        print("🎮 Controles: [R]efresh | [Q]uit | [C]lear")
        print("─" * 72)
    
    def display(self):
        """Exibe dashboard completo"""
        self.start_time = self.start_time or time.time()
        
        self._print_header()
        self.display_metrics()
        self.display_decisions()
        self.display_rules()
        self.display_stats()
        self.display_footer()
    
    def run_interactive(self, refresh_interval=5):
        """Executa dashboard interativo"""
        print("🎮 Modo interativo iniciado. Digite 'help' para ajuda.")
        
        while True:
            try:
                self.display()
                
                # Aguardar input com timeout
                print("\n⏳ Próxima atualização em", refresh_interval, "s...", end='', flush=True)
                
                import select
                if sys.stdin in select.select([sys.stdin], [], [], refresh_interval)[0]:
                    user_input = input("\n\n> ").strip().lower()
                    
                    if user_input in ['q', 'quit', 'exit']:
                        print("👋 Dashboard encerrado")
                        break
                    elif user_input in ['c', 'clear']:
                        # Limpar arquivos
                        for f in [self.telemetry_file, self.decisions_file, self.rules_file]:
                            if os.path.exists(f):
                                os.remove(f)
                        print("✅ Arquivos limpados")
                    elif user_input in ['h', 'help']:
                        print("""
                        Comandos:
                        - [R/Enter]: Atualizar display
                        - [Q]: Sair
                        - [C]: Limpar arquivos
                        - [H]: Este ajuda
                        """)
                        input("Pressione Enter para continuar...")
                        
            except KeyboardInterrupt:
                print("\n\n👋 Dashboard encerrado pelo usuário")
                break
            except Exception as e:
                print(f"\n❌ Erro: {e}")
                time.sleep(1)
    
    def run_batch(self, refresh_interval=5, duration=None):
        """Executa dashboard em modo batch"""
        print(f"📊 Atualizando a cada {refresh_interval}s. Ctrl+C para sair.")
        
        if duration:
            print(f"⏱️  Duração máxima: {duration}s")
        
        start = time.time()
        
        try:
            while True:
                if duration and (time.time() - start) > duration:
                    print(f"\n✅ Tempo máximo ({duration}s) excedido")
                    break
                
                self.display()
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Dashboard encerrado pelo usuário")


def main():
    """Entrada principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Dashboard - Monitor de análise de tráfego em tempo real"
    )
    parser.add_argument(
        "--project-root",
        default="/home/diogo/Documentos/codigos/p4_analit",
        help="Caminho raiz do projeto"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Intervalo de atualização em segundos (padrão: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duração máxima em segundos (padrão: infinito)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interativo com input do usuário"
    )
    
    args = parser.parse_args()
    
    monitor = DashboardMonitor(args.project_root)
    
    try:
        if args.interactive:
            monitor.run_interactive(args.interval)
        else:
            monitor.run_batch(args.interval, args.duration)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

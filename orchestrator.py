#!/usr/bin/env python3
"""
Orchestrator - Sistema completo de monitoramento de tráfego com LLM Phi3
Coordena: Mininet → Controlador → Brain LLM → Decisões
"""

import subprocess
import time
import os
import signal
import sys
import json
from datetime import datetime
from pathlib import Path
import threading


class TrafficAnalysisOrchestrator:
    
    def __init__(self, project_root="/home/diogo/Documentos/codigos/p4_analit"):
        self.project_root = project_root
        self.processes = {}
        self.log_file = os.path.join(project_root, "orchestrator.log")
        self.timing_file = os.path.join(project_root, "timing_stats.json")
        self.start_time = None
        self.timing_data = {}
        
        self._cleanup_old_files()
    
    def _cleanup_old_files(self):
        files_to_clean = [
            "json/telemetry_storage.json",
            "json/decisions.json",
            "decisions_history.json",
            "rules_applied.json",
            "json/metrics_history.json",
            "json/timing_stats.json"
        ]
        
        for f in files_to_clean:
            fpath = os.path.join(self.project_root, f)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    self.log(f"🗑️  Limpado: {f}")
                except:
                    pass
    
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_msg + "\n")
        except:
            pass
    
    def check_ollama(self):
        self.log("🔍 Verificando Ollama...")
        
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                models = json.loads(result.stdout.decode())
                available_models = [m['name'] for m in models.get('models', [])]
                
                if 'phi3' in str(available_models):
                    self.log("✅ Ollama online com Phi3 disponível")
                    return True
                else:
                    subprocess.run(["ollama", "pull", "phi3"], timeout=120)
                    return True
            else:
                return False
                
        except:
            return False
    
    def start_controller(self):
        self.log("🎮 Iniciando Controlador SDN...")
        
        try:
            controller_path = os.path.join(self.project_root, "controller.py")
            
            proc = subprocess.Popen(
                ["python3", controller_path],
                cwd=self.project_root
            )
            
            self.processes['controller'] = proc
            self.log(f"✅ Controlador iniciado (PID: {proc.pid})")
            time.sleep(2)
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao iniciar controlador: {e}")
            return False
    
    def start_brain_llm(self):
        self.log("🧠 Iniciando Brain LLM (Phi3)...")
        
        try:
            brain_path = os.path.join(self.project_root, "brain_llm.py")
            
            proc = subprocess.Popen(
                ["python3", brain_path],
                cwd=self.project_root
            )
            
            self.processes['brain_llm'] = proc
            self.log(f"✅ Brain LLM iniciado (PID: {proc.pid})")
            time.sleep(2)
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao iniciar Brain LLM: {e}")
            return False
    
    def start_mininet_traffic(self, duration=120):
        try:
            self.log(f"🐘 Tentando iniciar Mininet...")
            traffic_gen_path = os.path.join(self.project_root, "traffic_generator.py")
            
            proc = subprocess.Popen(
                ["sudo", "python3", traffic_gen_path],
                cwd=self.project_root,
                preexec_fn=os.setsid
            )
            
            self.processes['mininet'] = proc
            self.log(f"✅ Mininet iniciado (PID: {proc.pid})")
            
            time.sleep(3)
            if proc.poll() is not None:
                raise RuntimeError("Mininet falhou")
            
            return True
            
        except:
            self.log("🔄 Ativando modo simulado...")
            
            traffic_sim_path = os.path.join(self.project_root, "traffic_simulator.py")
            
            proc = subprocess.Popen(
                ["python3", traffic_sim_path],
                cwd=self.project_root
            )
            
            self.processes['mininet'] = proc
            return True
    
    def monitor_system(self, duration=120):
        self.log(f"📊 Monitorando sistema por {duration}s...")
        
        start = time.time()
        iteration = 0
        
        while (time.time() - start) < duration:
            iteration += 1
            
            running = [n for n, p in self.processes.items() if p.poll() is None]
            
            telem = 0
            decisions = 0
            
            tfile = os.path.join(self.project_root, "json/telemetry_storage.json")
            dfile = os.path.join(self.project_root, "json/decisions.json")
            
            if os.path.exists(tfile):
                telem = len(open(tfile).readlines())
            
            if os.path.exists(dfile):
                decisions = len(open(dfile).readlines())
            
            self.log(f"[{iteration}] Processos: {running} | Telemetrias: {telem} | Decisões: {decisions}")
            
            time.sleep(10)
    
    def cleanup(self):
        self.log("🛑 Encerrando...")
        
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                proc.terminate()
    
    def run(self, duration=120):
        
        print("""
🚀 SISTEMA DE ANÁLISE COM LLM
""")
        
        try:
            if not self.check_ollama():
                self.log("❌ Ollama não disponível")
                return
            
            self.start_controller()
            self.start_brain_llm()
            
            time.sleep(5)
            
            self.start_mininet_traffic(duration)
            
            self.monitor_system(duration)
            
        finally:
            self.cleanup()


def main():
    orchestrator = TrafficAnalysisOrchestrator()
    orchestrator.run()


if __name__ == '__main__':
    main()
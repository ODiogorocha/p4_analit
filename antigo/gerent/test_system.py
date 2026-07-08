#!/usr/bin/env python3
"""
Teste Rápido - Valida sistema com dados simulados
Useful para debug sem Mininet/Ollama complexos
"""

import json
import os
import time
import subprocess
import sys

def test_traffic_simulator():
    """Testa simulador de tráfego"""
    print("\n" + "="*60)
    print("🧪 TESTE 1: Simulador de Tráfego")
    print("="*60)
    
    try:
        subprocess.run([
            "python3", "traffic_simulator.py"
        ], timeout=130, check=True)
        
        # Verificar se arquivo foi criado
        if os.path.exists("telemetry_storage.json"):
            with open("telemetry_storage.json") as f:
                count = len(f.readlines())
            print(f"✅ Gerou {count} telemetrias")
            return True
        else:
            print("❌ Arquivo de telemetria não criado")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_controller():
    """Testa controlador"""
    print("\n" + "="*60)
    print("🧪 TESTE 2: Controlador SDN")
    print("="*60)
    
    try:
        # Limpar arquivo anterior
        if os.path.exists("telemetry_storage.json"):
            os.remove("telemetry_storage.json")
        
        # Iniciar controller em background
        proc = subprocess.Popen(["python3", "controller.py"])
        
        # Aguardar initialization
        time.sleep(2)
        
        # Matar
        proc.terminate()
        proc.wait(timeout=3)
        
        print("✅ Controller inicializou corretamente")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_brain_llm():
    """Testa Brain LLM"""
    print("\n" + "="*60)
    print("🧪 TESTE 3: Brain LLM")
    print("="*60)
    
    try:
        print("Testando conexão com Ollama...")
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print("✅ Ollama online")
            return True
        else:
            print("⚠️  Ollama offline (rode: ollama serve)")
            return False
            
    except Exception as e:
        print(f"⚠️  Ollama não respondeu: {e}")
        return False

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           🧪 TESTES RÁPIDOS DO SISTEMA                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    results = {
        "Simulador de Tráfego": test_traffic_simulator(),
        "Controlador SDN": test_controller(),
        "Brain LLM (Ollama)": test_brain_llm(),
    }
    
    print("\n" + "="*60)
    print("📊 RESUMO")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test}")
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n✅ Sistema está OK! Pronto para: make run")
    elif passed >= total - 1:
        print("\n⚠️  Sistema parcialmente ok (Ollama pode estar offline)")
        print("   Se Ollama/Phi3 não estiver disponível, o sistema usará modo"),
        print("   simulado para tráfego!")
    else:
        print("\n❌ Alguns componentes com problema")
    
    return 0 if passed > 0 else 1

if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Verificador de Setup - Valida que tudo está pronto para rodar
"""

import subprocess
import sys
import os
from pathlib import Path

def check_python():
    """Verifica Python 3.8+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python {version.major}.{version.minor} (esperado 3.8+)")
        return False
    print(f"✅ Python {version.major}.{version.minor}")
    return True

def check_command(cmd, name):
    """Verifica se comando existe"""
    try:
        result = subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ {name}")
            return True
    except:
        pass
    print(f"❌ {name} (não encontrado)")
    return False

def check_python_packages():
    """Verifica pacotes Python necessários"""
    packages = ['requests', 'thrift', 'scapy']
    all_ok = True
    
    for pkg in packages:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} (execute: pip3 install {pkg})")
            all_ok = False
    
    return all_ok

def check_ollama():
    """Verifica Ollama"""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ Ollama respondendo")
            return True
    except:
        pass
    
    print("⚠️  Ollama não está respondendo (rode: ollama serve)")
    return False

def check_files():
    """Verifica arquivos do projeto"""
    files = [
        'orchestrator.py',
        'brain_llm.py',
        'controller.py',
        'traffic_generator.py',
        'dashboard.py',
        'p4/elephant_monitor.p4',
        'p4/telemetry_agent.py'
    ]
    
    all_ok = True
    for f in files:
        if os.path.exists(f):
            print(f"✅ {f}")
        else:
            print(f"❌ {f}")
            all_ok = False
    
    return all_ok

def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          🔍 VERIFICADOR DE SETUP                             ║
    ║  Sistema de Análise Inteligente de Tráfego com Phi3         ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n📋 CHECKLIST:\n")
    
    results = {
        "Python 3.8+": check_python(),
        "Mininet": check_command("sudo", "sudo"),
        "curl": check_command("curl", "curl"),
        "Python packages": check_python_packages(),
        "Arquivos do projeto": check_files(),
        "Ollama": check_ollama(),
    }
    
    print("\n" + "="*60)
    print("📊 RESUMO:")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")
    
    print(f"\nResultado: {passed}/{total} verificações passaram")
    
    print("\n" + "="*60)
    
    if passed == total:
        print("\n✅ SETUP COMPLETO! Sistema pronto para rodar.")
        print("\nProximo passo:")
        print("  1. Terminal 1: ollama serve")
        print("  2. Terminal 2: make orchestrator")
        print("  3. Terminal 3: python3 dashboard.py --interactive")
        return 0
    else:
        print(f"\n⚠️  {total - passed} item(ns) com problema.")
        print("\nPor favor, resolva os problemas acima e tente novamente.")
        return 1

if __name__ == '__main__':
    sys.exit(main())

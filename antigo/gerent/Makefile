.PHONY: run help check setup orchestrator controller brain dashboard clean

run:
	sudo python3 topology.py


help:
	@echo "╔═══════════════════════════════════════════════════════════════╗"
	@echo "║  🐘 Sistema de Análise Inteligente de Tráfego com Phi3       ║"
	@echo "╚═══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📋 Comandos:"
	@echo ""
	@echo "  make run               - 🚀 RODAR TUDO (principal)"
	@echo "  make dashboard         - 📊 Monitor em tempo real (novo terminal)"
	@echo ""
	@echo "  make check             - ✅ Verificar dependências"
	@echo "  make setup             - 📦 Setup inicial"
	@echo "  make clean             - 🗑️  Limpar temporários"
	@echo ""

check:
	@echo "🔍 Verificando dependências..."
	@command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 não instalado"; exit 1; }
	@command -v pip3 >/dev/null 2>&1 || { echo "❌ pip3 não instalado"; exit 1; }
	@echo "✅ Python3 OK"
	@echo "✅ pip3 OK"
	@python3 verify_setup.py

setup:
	@echo "📦 Instalando dependências Python..."
	pip3 install --upgrade pip
	pip3 install requests mininet scapy thrift
	@echo "✅ Setup completo!"

# Pipeline completo orquestrado
orchestrator:
	@echo "🚀 Iniciando pipeline COMPLETO..."
	python3 orchestrator.py --duration 120

# Componentes individuais
controller:
	python3 controller.py

brain:
	python3 brain_llm.py

traffic:
	sudo python3 traffic_generator.py

# Dashboard em novo terminal
dashboard:
	python3 dashboard.py --interactive

# Testes rápidos
test:
	python3 test_system.py

# Limpeza
clean:
	@echo "🗑️  Limpando arquivos temporários..."
	rm -f json/telemetry_storage.json json/decisions.json rules_applied.json json/metrics_history.json
	rm -f *.pyc __pycache__
	rm -f orchestrator.log analysis_report.json
	sudo mn -c 2>/dev/null || true
	@echo "✅ Limpeza concluída!"
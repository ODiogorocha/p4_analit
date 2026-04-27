# Makefile para Elephant Flow Detection
SHELL=/bin/bash

# Configurações
HOST_IP = 10.0.0.101
VM_IP = 10.0.0.108
GERENT_IP = $(HOST_IP)
GERENT_PORT = 5000
THRESHOLD = 500000

# Ambiente - Usando caminhos ABSOLUTOS
VENV = .env
PYTHON_ABS = $(shell pwd)/$(VENV)/bin/python3

.PHONY: help run-gerent run-agent setup test status kill clean

help:
	@echo "Comandos disponíveis:"
	@echo "  make run-gerent  - Roda o Gerente (IA Ollama + Brain)"
	@echo "  make run-agent   - Roda o Agent (Detector de elephant flows)"
	@echo "  make setup       - Instala dependências"
	@echo "  make test        - Testa comunicação"
	@echo "  make status      - Verifica serviços"
	@echo "  make kill        - Mata processos"
	@echo "  make clean       - Limpa arquivos"

run-agent:
	@echo "🤖 Iniciando Agent..."
	@echo "📡 Enviando para: http://$(GERENT_IP):$(GERENT_PORT)/telemetry"
	@cd agent && sudo $(PYTHON_ABS) controller.py

run-gerent:
	@echo "🧠 Iniciando Gerente..."
	@echo "📡 API: http://$(GERENT_IP):$(GERENT_PORT)"
	@echo "📦 Verificando Ollama..."
	@curl -s http://localhost:11434/api/tags > /dev/null 2>&1 || (ollama serve > logs/ollama.log 2>&1 & sleep 3)
	@ollama list | grep -q phi3 || ollama pull phi3
	@$(PYTHON_ABS) agent/brain_llm.py

brain:
	@$(PYTHON_ABS) agent/brain_llm.py

agent:
	@cd agent && sudo $(PYTHON_ABS) controller.py

mininet:
	@sudo python3 topo.py

decision:
	@$(PYTHON_ABS) agent/decision_engine.py

test:
	@echo "🧪 Testando Gerent..."
	@curl -s -X POST http://$(GERENT_IP):$(GERENT_PORT)/telemetry -H "Content-Type: application/json" -d '[{"src_ip":"10.0.0.1","dst_ip":"10.0.0.2","bytes":600000}]' | python3 -m json.tool

status:
	@echo "📊 Status do Sistema"
	@echo "================================"
	@echo -n "Brain API: "
	@curl -s -o /dev/null -w "%{http_code}" http://$(GERENT_IP):$(GERENT_PORT)/telemetry -X POST -d '[]' 2>/dev/null | grep -q "200" && echo "✅ Rodando" || echo "❌ Parado"
	@echo -n "Ollama: "
	@curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "✅ Rodando" || echo "❌ Parado"
	@echo -n "Agent: "
	@pgrep -f "controller.py" > /dev/null && echo "✅ Rodando" || echo "⚠️ Parado"

setup:
	@echo "🔧 Configurando ambiente..."
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install flask requests scapy flask-cors
	mkdir -p json logs
	@if ! command -v ollama > /dev/null; then curl -fsSL https://ollama.com/install.sh | sh; fi
	@ollama pull phi3
	@chmod +x agent/*.py 2>/dev/null || true
	@echo "✅ Setup completo!"

clean:
	@echo "🧹 Limpando..."
	rm -rf __pycache__ agent/__pycache__ json/__pycache__
	rm -f json/decisions.json logs/*.log
	find . -name "*.pyc" -delete

kill:
	@echo "🛑 Matando processos..."
	-sudo pkill -f "controller.py"
	-sudo pkill -f "brain_llm.py"
	-sudo pkill -f "mininet"
	-sudo mn -c 2>/dev/null
	-killall ollama 2>/dev/null

reset: kill clean
	@echo "🔄 Sistema resetado"
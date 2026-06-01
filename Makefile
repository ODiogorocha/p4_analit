# Makefile
SHELL=/bin/bash
PROJECT_DIR=$(shell pwd)

run-agent:
	@echo "🤖 Iniciando Agent..."
	@cd agent && sudo $(PROJECT_DIR)/.env/bin/python3 controller.py

run-gerent:
	@echo "🧠 Iniciando Gerente..."
	@$(PROJECT_DIR)/.env/bin/python3 brain_llm.py

setup:
	python3 -m venv .env
	.env/bin/pip install scapy flask requests
	sudo pip3 install scapy  # Instala global também para o sudo
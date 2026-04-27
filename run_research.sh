#!/bin/bash

echo "========================================="
echo "📊 PESQUISA - Elephant Flow Detection"
echo "========================================="
echo ""
echo "Este script irá:"
echo "1. Iniciar o Agent com métricas"
echo "2. Iniciar o Brain com métricas"
echo "3. Gerar elephant flows"
echo "4. Coletar dados de performance"
echo ""

# Instalar dependências
pip install psutil

# Limpar métricas anteriores
rm -f json/performance_metrics.json

# Iniciar Brain em background
echo "🧠 Iniciando Brain..."
cd /home/diogo/Documentos/codigos/p4_analit
source .env/bin/activate
python3 gerent/brain_ollama_metrics.py &
BRAIN_PID=$!

sleep 5

echo "✅ Brain rodando (PID: $BRAIN_PID)"
echo ""

# Iniciar Agent
echo "🤖 Iniciando Agent..."
cd /home/p4/Documents/p4_analit
sudo /home/p4/Documents/p4_analit/.env/bin/python3 agent/controller_metrics.py

# Quando o Agent parar, mostrar resultados
echo ""
echo "========================================="
echo "📊 RESULTADOS DA PESQUISA"
echo "========================================="
cat json/performance_metrics.json | python3 -m json.tool

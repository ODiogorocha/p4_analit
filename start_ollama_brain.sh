# start_ollama_brain.sh
#!/bin/bash

echo "🚀 Iniciando Ollama e Brain..."
echo "================================"

# Inicia Ollama se não estiver rodando
if ! pgrep -x "ollama" > /dev/null; then
    echo "📦 Iniciando Ollama..."
    ollama serve > logs/ollama.log 2>&1 &
    sleep 3
fi

# Verifica modelo phi3
echo "🤖 Verificando modelo phi3..."
ollama pull phi3

# Inicia o Brain
echo "🧠 Iniciando Brain..."
cd /home/diogo/Documentos/codigos/p4_analit
source .env/bin/activate
python3 gerent/brain_ollama.py
#!/bin/bash

# 🐘 GUIA DE INÍCIO RÁPIDO
# Sistema Inteligente de Análise de Tráfego com Phi3 LLM

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  🚀 SISTEMA DE ANÁLISE INTELIGENTE DE TRÁFEGO - GUIA RÁPIDO      ║"
echo "║                                                                   ║"
echo "║  Pipeline: Mininet → P4 → Controlador → LLM Phi3 → Decisões    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não está instalado"
    exit 1
fi

echo "✅ Python3 encontrado"

# Verificar se está no diretório correto
if [ ! -f "orchestra.py" ]; then
    echo "⚠️  Parece que você não está no diretório do projeto"
    echo "Execute este script dentro de /home/diogo/Documentos/codigos/p4_analit"
    exit 1
fi

echo "✅ Diretório do projeto confirmado"

echo
echo "┌────────────────────────────────────────────────────────────────────┐"
echo "│ 1️⃣  VERIFICAR DEPENDENCIES                                        │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo

make check

echo
echo "┌────────────────────────────────────────────────────────────────────┐"
echo "│ 2️⃣  INSTALAR DEPENDÊNCIAS PYTHON                                 │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo

make setup

echo
echo "┌────────────────────────────────────────────────────────────────────┐"
echo "│ 3️⃣  VERIFICAR/INICIAR OLLAMA COM PHI3                            │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo
echo "📋 Ollama é necessário para o LLM Phi3. Verifique:"
echo "   - Se Ollama está instalado: ollama --version"
echo "   - Se está rodando em outro terminal"
echo "   - Se Phi3 foi puxado: ollama list"
echo
echo "Para iniciar:"
echo "   Terminal 1: ollama serve"
echo "   Terminal 2: ollama pull phi3"
echo

read -p "Pressione ENTER após iniciar Ollama (ou Ctrl+C para sair)..."

echo
echo "✅ Continuando..."

echo
echo "┌────────────────────────────────────────────────────────────────────┐"
echo "│ 4️⃣  EXECUTAR SISTEMA COMPLETO                                    │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo
echo "🚀 Iniciando pipeline completo..."
echo "   - Controlador SDN (analisa telemetria)"
echo "   - Brain LLM (consulta Phi3 para decisões)"
echo "   - Gerador de Tráfego Mininet (tráfego normal + elefante)"
echo "   - Monitoramento por 120 segundos"
echo "   - Geração de relatório"
echo
echo "💡 Este processo pode levar alguns minutos na primeira vez..."
echo

# Executar o orchestrator
python3 orchestrator.py --duration 120

RESULT=$?

echo
echo "┌────────────────────────────────────────────────────────────────────┐"
echo "│ 5️⃣  VISUALIZAR RESULTADOS                                         │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo

if [ $RESULT -eq 0 ]; then
    echo "✅ Execução concluída com sucesso!"
    echo
    echo "📊 Analisando resultados..."
    python3 analyze_results.py --project-root .
    
    echo
    echo "┌────────────────────────────────────────────────────────────────────┐"
    echo "│ 📊 PRÓXIMOS PASSOS                                                │"
    echo "└────────────────────────────────────────────────────────────────────┘"
    echo
    echo "1. Ver dashboard interativo:"
    echo "   python3 dashboard.py --interactive"
    echo
    echo "2. Analisar decisões:"
    echo "   cat decisions.json | python3 -m json.tool"
    echo
    echo "3. Ver telemetrias:"
    echo "   cat json/telemetry_storage.json | python3 -m json.tool | head -50"
    echo
    echo "4. Gerar novo relatório:"
    echo "   python3 analyze_results.py"
    echo
    echo "5. Executar novamente:"
    echo "   make orchestrator"
    echo
else
    echo "❌ Erro na execução"
    echo "📋 Verifique o log:"
    echo "   tail -50 orchestrator.log"
fi

echo
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  ✅ Guia de início rápido concluído!                             ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

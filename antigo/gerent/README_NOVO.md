# 🐘 Sistema Inteligente de Análise de Tráfego P4 + Mininet + LLM Phi3

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![P4](https://img.shields.io/badge/P4-v16-orange)](https://p4.org/)

Um sistema que **gera tráfego de rede**, **coleta telemetria em tempo real** e **usa LLM Phi3** para **analisar e otimizar automaticamente**.

## 🎯 O Sistema

```
Mininet/Simulado → Switch P4 → Controlador SDN → Brain LLM (Phi3)
                                                        ↓
                                                   Decisão Inteligente
                                                   (MARCAR, DROPAR, etc)
```

## 📋 Arquivos Principais

| Arquivo | O que faz |
|---------|-----------|
| `orchestrator.py` | Coordena TUDO automaticamente |
| `brain_llm.py` | Analisa com Phi3 do Ollama |
| `controller.py` | Recebe telemetria e aplica ações |
| `traffic_generator.py` | Gera tráfego (Mininet real) |
| `traffic_simulator.py` | Gera tráfego (modo simulado, fallback) |
| `monitor.py` | Visualiza em tempo real |
| `dashboard.py` | Dashboard avançado |

## 🚀 Como Usar

### Passo 1: Instalar (primeira vez)
```bash
make setup
make check
```

### Passo 2: Iniciar Ollama (terminal separado)
```bash
ollama serve
# Em outro:
ollama pull phi3
```

### Passo 3: RODAR TUDO
```bash
make run
```

### Passo 4: Monitorar (na em outro terminal)
```bash
# Opção A: Monitor simples
python3 monitor.py

# Opção B: Dashboard completo
python3 dashboard.py --interactive

# Opção C: Ver logs
tail -f orchestrator.log
```

## ✨ Dois Modos de Funcionamento

### 🟢 Modo Mininet (Tráfego Real)
- Requer Mininet instalado
- Emula switch P4 real
- Mais precise

### 🟡 Modo Simulado (Recomendado)
- Funciona sempre
- Tráfego sintético realista
- Rápido e confiável

**O sistema escolhe automaticamente qual usar!**

## 📊 Saída Gerada

Após execução:
- `telemetry_storage.json` - Métricascoletadas
- `decisions.json` - Decisões LLM
- `rules_applied.json` - Ações executadas
- `analysis_report.json` - Relatório final
- `orchestrator.log` - Log detalhado

## 🤖 Exemplos de Decisões

```
Input: Tráfego normal (5 fluxos, 500KB)
LLM:   "Tráfego de controle normal"
Ação:  ENCAMINHAR ✅

Input: Fluxo elefante detectado (1 fluxo, 50MB)
LLM:   "Fluxo elefante, usar QoS"
Ação:  MARCAR 🏷️

Input: Congestionamento (30 fluxos, 500MB)
LLM:   "Alto volume, distribuir carga"
Ação:  BALANCEAR ⚖️
```

## 💡 Comandos Úteis

```bash
make run         # Rodar TUDO
make setup       # Setup inicial
make check       # Verificar dependências
make test        # Testar componentes
make dashboard   # Monitor em tempo real
make clean       # Limpar arquivos
make help        # Ver ajuda
```

## ⏱️ Timeline

```
0s:        Sistema inicia
0-5s:      Componentes carregam
5-125s:    Tráfego sendo gerado
30s:       Primeira decisão do LLM
60s-90s:   Fluxos elefante detectados
120s:      Fim do tráfego
120-130s:  Limpeza e relatório
```

## 🔧 Troubleshooting

### Ollama não responde
```bash
ollama serve  # em novo terminal
```

### Mininet não encontrado
```bash
# Sistema usa simulador automaticamente
# Ou instale: sudo apt-get install mininet
```

### Ver o que está acontecendo
```bash
tail -50 orchestrator.log
python3 monitor.py
```

### Limpar de falhas anteriores
```bash
make clean
make run
```

## 📚 Documentação

- **SUMMARY.md** - Resumo executivo
- **ARCHITECTURE.md** - Arquitetura técnica
- **SIMULATED_MODE.md** - Modo simulado explicado
- **QUICKSTART.txt** - Guia rápido visual

## 🎓 Aprenda Sobre

- ✅ **P4 Networking** - Programar switches
- ✅ **SDN** - Software-Defined Networking  
- ✅ **LLM** - Inteligência Artificial em rede
- ✅ **Mininet** - Emular topologias
- ✅ **Telemetria** - Coletar dados em tempo real

## 📞 Help

```
make help     # Ver todos os comandos
python3 verify_setup.py  # Validar sistema
python3 test_system.py   # Testar componentes
```

---

**Status**: ✅ Production Ready  
**Versão**: 3.0  
**Modo**: Automático (Mininet ou Simulado)

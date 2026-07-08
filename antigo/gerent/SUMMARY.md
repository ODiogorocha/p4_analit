# 📌 RESUMO EXECUTIVO DO PROJETO

## O Que É?

Um **sistema inteligente de análise de tráfego de rede** que combina:

1. **Simulação de Rede (Mininet)**
   - Cria 4 hosts conectados a um switch virtual
   - Gera tráfego normal (ping, DNS) e tráfego elefante (fluxos > 1MB com iperf)
   - Simula cenários realistas de congestionamento

2. **Programação de Rede (P4)**
   - Switch que conta bytes/pacotes por fluxo (5-tupla)
   - Extrai telemetria em tempo real
   - Suporta até 1024 fluxos simultâneos

3. **Inteligência Artificial (LLM Phi3)**
   - Analisa métricas de tráfego usando modelo de linguagem
   - Toma decisões: ENCAMINHAR, MARCAR, DROPAR, FRAGMENTAR, BALANCEAR
   - Explica suas razões para cada decisão

4. ** Controle em Tempo Real**
   - Aplica decisões da IA ao switch
   - Otimiza roteamento baseado em análise

## Por Que Usar?

✅ **Estudo e Pesquisa**: Entender cómo redes inteligentes funcionam  
✅ **Prototipação**: Testar algoritmos de otimização  
✅ **Educação**: Aprender P4, SDN e integração com IA  
✅ **Demonstração**: Mostrar capabilidade de IA em networking  

## Como Funciona?

```
┌─────────────┐
│  Mininet    │  Gera tráfego
│ (Topologia) │  normal + elefante
└──────┬──────┘
       │
       ↓
┌─────────────────────────┐
│  Switch P4 (BMv2)       │  Coleta
│  elephant_monitor.p4    │  telemetria
└──────┬──────────────────┘
       │
       ↓ UDP:9999
┌──────────────────────────┐
│  Controlador SDN         │  Recebe e
│  controller.py           │  armazena
└──────┬───────────────────┘
       │
       ├──────────────┐
       ↓              ↓ lê JSON
┌──────────────┐  ┌────────────────────┐
│ Dashboard    │  │ Brain LLM (Phi3)   │
│ (Monitor)    │  │ brain_llm.py       │
└──────────────┘  │ Consulta Ollama    │
                  └──────┬─────────────┘
                         │
                         ↓ HTTP:11434
                     ┌────────┐
                     │ Ollama  │  LLM
                     │  /Phi3  │
                     └────────┘
```

## Componentes

| Arquivo | Responsabilidade | Linguagem |
|---------|-----------------|-----------|
| `orchestrator.py` | Orquestra tudo | Python 3 |
| `traffic_generator.py` | Cria hosts e tráfego | Python 3 (Mininet) |
| `elephant_monitor.p4` | Coleta telemetria | P4 |
| `controller.py` | Recebe e coordena | Python 3 |
| `brain_llm.py` | Analisa com IA | Python 3 |
| `dashboard.py` | Visualiza resultados | Python 3 |
| `analyze_results.py` | Processa dados | Python 3 |

## Saída do Sistema

Após execução, você obtém:

📊 **telemetry_storage.json** - Todas as métricas coletadas  
🤖 **decisions.json** - Cada decisão do LLM (ação + latência)  
⚙️ **rules_applied.json** - Regras instaladas no switch  
📈 **metrics_history.json** - Histórico de métricas  
📋 **analysis_report.json** - Relatório consolidado  
📝 **orchestrator.log** - Logs da execução completa  

## Exemplos de Decisões

### Tráfego Normal
**Entrada**: 5 fluxos, 512 KB, tamanho médio 100 bytes  
**Phi3 responde**: "ENCAMINHAR"  
**Razão**: "Tráfego de controle normal, sem anomalias"  
**Ação**: Fluxo passa normalmente

### Elephant Flow Detectado
**Entrada**: 12 fluxos, 52 MB, 2 elefantes (>1MB)  
**Phi3 responde**: "MARCAR"  
**Razão**: "Fluxo elefante detectado, necessário QoS para priorização"  
**Ação**: Marca pacotes com DSCP alta prioridade

### Congestionamento  
**Entrada**: 85 fluxos, 500 MB, muito volume  
**Phi3 responde**: "BALANCEAR"  
**Razão**: "Alto volume de tráfego, distribuir entre múltiplos caminhos"  
**Ação**: Ativa ECMP (Equal-Cost Multipath)

## Requisitos

### Hardware
- CPU: 4+ cores (para Mininet + Ollama)
- RAM: 8+ GB recomendado
- Disco: 5+ GB livres

### Software
- **OS**: Linux (Ubuntu 18.04+)
- **Python**: 3.8+
- **Mininet**: 2.2.0+
- **P4 Compiler**: p4c-bm2-ss
- **BMv2**: simple_switch
- **Ollama**: Latest (com Phi3)
- **Docker** (opcional, para Ollama)

### Dependências Python
```bash
pip3 install requests scapy thrift colorama tabulate
```

## Início Rápido (5 minutos)

```bash
# 1. Setup (primeira vez)
make setup
make check

# 2. Iniciar Ollama (outro terminal)
ollama serve
ollama pull phi3

# 3. RODAR TUDO
make run

# 4. Monitorar (outro terminal)
python3 dashboard.py --interactive
```

## Timeframe Esperado

| Fase | Duração | O que acontece |
|------|---------|---------------|
| Initialização | 5-10s | Carrega componentes |
| Fase 1: Normal | 30s | Tráfego base (ping, DNS) |
| Fase 2: Elefante | 30s | Adiciona fluxo grande (iperf) |
| Fase 3: Multi | 30s | Múltiplos tipos de tráfego |
| Fase 4: Elefante | 30s | Apenas tráfego grande |
| **Total** | **~2 minutos** | Análise + Decisões |

## Métricas Captadas

- **Fluxos**: Total identificados
- **Fluxos Elefante**: > 1MB
- **Total de Bytes**: Volume transmitido
- **Total de Pacotes**: Contagem de packets
- **Tamanho Médio**: bytes/pacotes
- **Protocolos**: TCP, UDP, ICMP
- **Latência LLM**: Tempo de decisão (ms)

## Casos de Uso

### 📚 Educacional
Studentos aprenderem sobre:
- P4 e SDN
- Inteligência Artificial em Networking
- Análise de tráfego

### 🔬 Pesquisa
Testar algoritmos para:
- Otimização de roteamento
- Detecção de anomalias
- Alocação de recursos

### 🏢 Corporativo
Demonstrar:
- Eficiência de redes inteligentes
- Potencial de IA em networking
- ROI de automação de rede

## Limitações Conhecidas

⚠️ **Ambientes Virtualizados**: Mininet funciona melhor em Linux nativo  
⚠️ **Escalabilidade**: Máximo 1024 fluxos simultâneos (limites do vetor P4)  
⚠️ **Latência LLM**: Primeira query de Phi3 pode ser lenta (warm-up)  
⚠️ **CPU Heavy**: Mininet + BMv2 + Ollama consomem recursos  

## Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| "Ollama não respondendo" | `ollama serve` em novo terminal |
| "Phi3 não encontrado" | `ollama pull phi3` |
| "Porta 9999 em uso" | `pkill -f controller.py` |
| "Permissão negada Mininet" | Execute com `sudo` ou adicione usuário ao grupo docker |
| "Sem telemetria" | Verifique se P4 compilou: `ls *.json` |

## Próximos Passos

1. **Customizações**: Modificar tráfego, decisões, prompts
2. **Integração**: Conectar seu próprio scheduler/controller
3. **Escalabilidade**: Aumentar número de fluxos
4. **Modelos**: Trocar Phi3 por outro LLM (GPT, Claude, etc)

## Documentação Completa

- `README.md` - Guia completo
- `ARCHITECTURE.md` - Detalhes técnicos
- `quickstart.sh` - Início rápido automatizado
- Logs em `orchestrator.log` - Debug detalhado

## Support

- 📧 Issues: Verifique `orchestrator.log`
- 📚 Conceitos: Veja links em `README.md`
- 🔗 Community: P4.org, Mininet groups online

---

**Versão**: 3.0  
**Data**: Abril 2026  
**Status**: ✅ Production Ready  
**Autor**: Diogo  

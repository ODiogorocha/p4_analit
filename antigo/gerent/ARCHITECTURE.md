# 📐 ARQUITETURA TÉCNICA DO SISTEMA

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                   CAMADA DE APLICAÇÃO                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Orchestrator.py                                          │  │
│  │ (Orquestra todos os componentes em sequência)           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ↓                    ↓                    ↓
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  CONTROLADOR     │ │   BRAIN LLM      │ │  TRAFFIC GEN     │
│  controller.py   │ │  brain_llm.py    │ │ traffic_gen.py   │
└──────────────────┘ └──────────────────┘ └──────────────────┘
        ↑                    ↑                    ↓
        │                    │                    │
   UDP:9999              JSON files          Mininet/Iperf
   Telemetry             Decisions            Geração
                                              de Tráfego
        ↓                    ↓                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                   CAMADA DE REDE                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Switch P4 (BMv2) → elephant_monitor.p4                  │  │
│  │ - Contadores de bytes/pacotes por fluxo                │  │
│  │ - Extração de 5-tupla (proto, src/dst IP, src/dst port)│  │
│  │ - Env: 1024 registros, overflow handling               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           ↑
           │
    Thrift 9090
    (telemetry_agent.py)
```

## Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. GERAÇÃO DE TRÁFEGO                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  traffic_generator.py (via Mininet)                               │
│  ├─ Cria topologia: 4 hosts + 1 switch                            │
│  ├─ Fase 1 (0-30s): Tráfego normal (ping, UDP_small)             │
│  ├─ Fase 2 (30-60s): Tráfego normal + Elephant (iperf > 40Mbps)  │
│  ├─ Fase 3 (60-90s): Adiciona tráfego aleatório + DNS            │
│  └─ Fase 4 (90-120s): Apenas tráfego elefante                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 2. COLETA DE TELEMETRIA                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  elephant_monitor.p4 (P4 dataplane program)                        │
│  ├─ Parser: Ethernet → IPv4 → TCP/UDP                             │
│  ├─ Conta bytes e pacotes por índice (0..1023)                    │
│  ├─ Hash 5-tupla para índice:                                     │
│  │  hash(src_ip + dst_ip + src_port + dst_port + proto) mod 1024  │
│  └─ Registra IP src/dst e portas                                  │
│                                                                     │
│  telemetry_agent.py (Ponte entre P4 e Controller)                │
│  ├─ Lê registers via Thrift a cada 1 segundo                     │
│  ├─ Calcula delta (atual - anterior)                             │
│  ├─ Trata overflow (valores > 2^64)                              │
│  ├─ Envia para controller via UDP:9999                           │
│  └─ Heartbeat a cada 5s (keepalive)                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 3. ANÁLISE DE TRÁFEGO                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  controller.py (Recebe telemetria)                                 │
│  ├─ Escuta UDP:9999 em thread separada                           │
│  ├─ Salva em telemetry_storage.json                              │
│  └─ Aguarda decisões do Brain LLM                                │
│                                                                     │
│  brain_llm.py (Análise com LLM)                                   │
│  ├─ A cada 5s, lê última telemetria                              │
│  ├─ Extrai métricas (fluxos, elefantes, bytes, etc)             │
│  ├─ Constrói prompt contextualizado para Phi3                    │
│  ├─ Consulta Ollama na porta 11434                               │
│  ├─ Parseia resposta e extrai ação                               │
│  └─ Salva decisão em decisions.json                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 4. APLICAÇÃO DE DECISÕES                                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  controller.py (Aplica ações)                                      │
│  ├─ Lê última decisão de decisions.json                           │
│  ├─ Mapeia para ação de rede:                                      │
│  │  • ENCAMINHAR  → forward_flow (normal)                         │
│  │  • MARCAR      → mark_flow (QoS/DSCP)                         │
│  │  • DROPAR      → drop_flow (bloqueia)                         │
│  │  • FRAGMENTAR  → fragment_flow (reduz MTU)                    │
│  │  • BALANCEAR   → balance_flow (ECMP)                          │
│  │                                                                 │
│  └─ Registra em rules_applied.json                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 5. MONITORAMENTO E VISUALIZAÇÃO                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  dashboard.py (Visualização em tempo real)                        │
│  ├─ Lê: telemetry_storage.json (a cada refresh)                 │
│  ├─ Lê: decisions.json                                           │
│  ├─ Lê: rules_applied.json                                       │
│  └─ Exibe: Métricas, Decisões, Regras, Estatísticas            │
│                                                                     │
│  analysis_report.json (Relatório final)                          │
│  └─ Consolidação de todos os dados                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Comunicação Inter-Processos

| Origem | Destino | Protocolo | Porta | Formato |
|--------|---------|-----------|-------|---------|
| Mininet | P4 Switch | Ethernet | N/A | Pacotes IP |
| P4 Switch | telemetry_agent | Thrift | 9090 | Registros binários |
| telemetry_agent | controller | UDP | 9999 | JSON + CRC32 |
| controller | files | File I/O | N/A | JSON (JSONL) |
| brain_llm | files | File I/O | N/A | JSON (JSONL) |
| brain_llm | Ollama | HTTP | 11434 | JSON (prompt/response) |
| dashboard | files | File I/O | N/A | JSON (read-only) |

## Estrutura de Dados

### telemetry_storage.json (JSON Lines)
```json
{"flows": [{"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "src_port": 12345, "dst_port": 5555, "proto_name": "TCP", "bytes": 5242880, "pkts": 5120}, ...]}
```

### decisions.json (JSON Lines)
```json
{"timestamp": "2026-04-12T14:30:45", "action": "MARCAR", "latency_ms": 245.3, "metrics": {"flows": 15, "elephant_flows": 2, ...}}
```

### metrics_history.json (JSON Lines)
```json
{"timestamp": "2026-04-12T14:30:45", "flows": 15, "elephant_flows": 2, "total_bytes": 52428800, "avg_packet_size": 1024, ...}
```

### rules_applied.json (JSON Lines)
```json
{"timestamp": "2026-04-12T14:30:46", "flow_id": 5, "src": "10.0.0.1", "dst": "10.0.0.2", "action": "MARCAR", "command": "mark_flow 5 priority=high"}
```

## Temporizações

```
T=0s:     Orchestrator inicia
T+0-2s:   Controlador SDN ligado
T+2-4s:   Brain LLM ligado
T+4-5s:   Aguarda estabilização
T+5s:     Mininet inicia geração de tráfego

T+5-35s:   Fase 1: Tráfego normal
T+35-65s:  Fase 2: Normal + Elefante
T+65-95s:  Fase 3: Normal + Elefante + Aleatório
T+95-125s: Fase 4: Apenas Elefante

T+125s:   Fim da geração
T+125-130s: Limpeza e geração de relatório
T+130s:   Encerramento
```

## Pontos de Falha e Tratamento

| Componente | Ponto de Falha | Tratamento |
|-----------|----------------|-----------|
| Mininet | Host não conecta | Retry de topologia |
| P4 Switch | Overflow de contador | Cálculo delta com wrap-around |
| Telemetry Agent | Conexão Thrift | Retry a cada 1s |
| Controller | UDP packet loss | CRC32 validation, retry |
| Brain LLM | Ollama timeout | Fallback: ENCAMINHAR |
| Dashboard | Arquivo não existe | Skip, aguardar próxima atualização |

## Escalabilidade

- **Máximo de fluxos rastreados**: 1024 (registros P4)
- **Tamanho máximo de pacote**: 1514 bytes (MTU padrão)
- **Frequência de telemetria**: 1 segundo (configurável)
- **Frequência de análise LLM**: 5 segundos (configurável)
- **Histórico armazenado**: Ilimitado (baseado em disco)

## Dependências Externas

| Componente | Requisito | Versão |
|-----------|----------|---------|
| Python | Interpretador | 3.8+ |
| Mininet | Emulador de rede | 2.2.0+ |
| P4 Compiler | p4c-bm2-ss | 1.1.0+ |
| BMv2 | Simple Switch | 1.0.0+ |
| Thrift | RPC framework | 0.11.0+ |
| Ollama | LLM Runtime | Latest |
| Phi3 | LLM Model | Latest |
| Python Packages | Requisitos | Veja requirements.txt |

---

**Última atualização**: Abril 2026  
**Versão da arquitetura**: 3.0

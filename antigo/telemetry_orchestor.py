#!/usr/bin/env python3
"""
python/telemetry_orchestrator.py
==================================
Orquestrador central que integra os três modos de coleta de
telemetria no projeto BMv2/P4.

Conecta-se ao:
  - INTCollector     (in-band)
  - PostcardCollector (postcard)
  - QSTCollector     (fila/pilha/árvore)

Fornece API unificada para gerent/orchestrator.py e dashboard.py.
Também gera alertas quando limiares são ultrapassados.
"""

import threading
import time
import json
import logging
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass

# Importa coletores do mesmo pacote
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from collector.int_inband_collector   import INTCollector
from collector.postcard_collector     import PostcardCollector
from collector.queue_stack_tree_collector import QSTCollector

log = logging.getLogger("telem_orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCH] %(levelname)s %(message)s"
)

# ── Alertas ──────────────────────────────────────────────────────────────────

@dataclass
class TelemAlert:
    level:      str    # "WARNING" | "CRITICAL"
    source:     str    # "INT" | "POSTCARD" | "QST_QUEUE" | "QST_STACK" | "QST_TREE"
    switch_id:  Optional[int]
    message:    str
    value:      float
    threshold:  float
    timestamp:  float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "level":     self.level,
            "source":    self.source,
            "switch_id": self.switch_id,
            "message":   self.message,
            "value":     self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
        }


# ── Configuração de limiares ──────────────────────────────────────────────────

class ThresholdConfig:
    def __init__(self):
        # INT In-Band
        self.int_latency_warn_us:    int = 500
        self.int_latency_crit_us:    int = 2000
        self.int_queue_warn_bytes:   int = 50_000
        self.int_queue_crit_bytes:   int = 200_000

        # Postcard
        self.pc_drop_warn:           int = 10
        self.pc_drop_crit:           int = 100
        self.pc_sojourn_warn_us:     int = 1000
        self.pc_sojourn_crit_us:     int = 5000

        # QST Fila
        self.q_depth_warn_bytes:     int = 100_000
        self.q_depth_crit_bytes:     int = 500_000
        self.q_lat_bucket_warn:      int = 8   # bucket 8 = 800µs+

        # QST Pilha
        self.stack_severity_warn:    int = 100
        self.stack_severity_crit:    int = 200

        # QST Árvore
        self.tree_lat_warn_us:       int = 300
        self.tree_lat_crit_us:       int = 1000


# ── Orquestrador ──────────────────────────────────────────────────────────────

class TelemetryOrchestrator:
    """
    Inicia, coordena e exporta dados de todos os coletores.

    Exemplo de uso no gerent/orchestrator.py:
        orch = TelemetryOrchestrator(
            int_iface="eth0",
            postcard_port=9556,
            qst_iface="eth0",
        )
        orch.start()
        snapshot = orch.snapshot()
        orch.export_json("json/controller_stats.json")
    """

    def __init__(
        self,
        int_iface:      str = "any",
        postcard_host:  str = "0.0.0.0",
        postcard_port:  int = 9556,
        qst_iface:      str = "any",
        thresholds:     Optional[ThresholdConfig] = None,
        alert_handlers: Optional[List[Callable]] = None,
    ):
        self.thresh = thresholds or ThresholdConfig()
        self._alert_handlers = alert_handlers or []
        self._running = False
        self._alerts: List[TelemAlert] = []
        self._lock   = threading.Lock()

        # Instancia coletores
        self.int_col = INTCollector(iface=int_iface)
        self.pc_col  = PostcardCollector(host=postcard_host, port=postcard_port)
        self.qst_col = QSTCollector(iface=qst_iface)

        # Registra callback de alerta no postcard
        self.pc_col.register_callback(self._pc_alert_callback)

    # ── Ciclo de vida ────────────────────────────────────────────────────
    def start(self):
        self.int_col.start()
        self.pc_col.start()
        self.qst_col.start()
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()
        log.info("TelemetryOrchestrator iniciado (INT + Postcard + QST)")

    def stop(self):
        self._running = False
        self.int_col.stop()
        self.pc_col.stop()
        self.qst_col.stop()
        log.info("TelemetryOrchestrator parado")

    # ── Monitor periódico ─────────────────────────────────────────────────
    def _monitor_loop(self):
        while self._running:
            time.sleep(2)
            self._check_int_alerts()
            self._check_qst_alerts()

    def _check_int_alerts(self):
        sm = self.int_col.get_switch_metrics()
        for sw_id_str, m in sm.items():
            sw_id = int(sw_id_str)
            q = m.get("avg_queue", 0)
            if q >= self.thresh.int_queue_crit_bytes:
                self._raise_alert(TelemAlert(
                    level="CRITICAL", source="INT", switch_id=sw_id,
                    message=f"Fila crítica SW{sw_id}: {q}B",
                    value=q, threshold=self.thresh.int_queue_crit_bytes
                ))
            elif q >= self.thresh.int_queue_warn_bytes:
                self._raise_alert(TelemAlert(
                    level="WARNING", source="INT", switch_id=sw_id,
                    message=f"Fila elevada SW{sw_id}: {q}B",
                    value=q, threshold=self.thresh.int_queue_warn_bytes
                ))

    def _check_qst_alerts(self):
        # Verifica profundidade de fila
        depths = self.qst_col.get_all_queue_depths()
        for port_str, depth in depths.items():
            if depth >= self.thresh.q_depth_crit_bytes:
                self._raise_alert(TelemAlert(
                    level="CRITICAL", source="QST_QUEUE", switch_id=None,
                    message=f"Fila crítica porta {port_str}: {depth:.0f}B",
                    value=depth, threshold=self.thresh.q_depth_crit_bytes
                ))

        # Verifica eventos de congestionamento
        evts = self.qst_col.get_congestion_events(
            n=10, severity_min=self.thresh.stack_severity_crit
        )
        for evt in evts:
            self._raise_alert(TelemAlert(
                level="CRITICAL", source="QST_STACK",
                switch_id=evt["switch_id"],
                message=f"Congestionamento crítico SW{evt['switch_id']}: {evt['event_name']}",
                value=evt["severity"],
                threshold=self.thresh.stack_severity_crit,
                timestamp=evt.get("recv_time", time.time()),
            ))

        # Verifica latência na árvore
        for sw_str, m in self.qst_col.get_tree_paths().items():
            lat = m["avg_lat_us"]
            if lat >= self.thresh.tree_lat_crit_us:
                self._raise_alert(TelemAlert(
                    level="CRITICAL", source="QST_TREE",
                    switch_id=int(sw_str),
                    message=f"Latência crítica nó SW{sw_str}: {lat}µs",
                    value=lat, threshold=self.thresh.tree_lat_crit_us
                ))

    def _pc_alert_callback(self, pc):
        """Chamado pelo PostcardCollector a cada postcard recebido."""
        if pc.drop_count >= self.thresh.pc_drop_crit:
            self._raise_alert(TelemAlert(
                level="CRITICAL", source="POSTCARD",
                switch_id=pc.switch_id,
                message=f"Drops críticos SW{pc.switch_id}: {pc.drop_count}",
                value=pc.drop_count,
                threshold=self.thresh.pc_drop_crit,
            ))

    def _raise_alert(self, alert: TelemAlert):
        with self._lock:
            # Evita duplicatas recentes (mesmo switch+nível nos últimos 10s)
            now = time.time()
            for a in self._alerts[-20:]:
                if (a.switch_id == alert.switch_id and
                        a.level == alert.level and
                        a.source == alert.source and
                        now - a.timestamp < 10):
                    return
            self._alerts.append(alert)
            # Mantém apenas os 200 mais recentes
            if len(self._alerts) > 200:
                self._alerts = self._alerts[-200:]

        log.warning(f"[{alert.level}] {alert.message}")
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as exc:
                log.warning(f"Alert handler falhou: {exc}")

    # ── API unificada ─────────────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """Retorna snapshot completo de todas as telemetrias."""
        return {
            "timestamp": time.time(),
            "int": {
                "recent_packets": self.int_col.get_latest(20),
                "path_stats":     self.int_col.get_path_stats(),
                "switch_metrics": self.int_col.get_switch_metrics(),
            },
            "postcard": {
                "flow_stats":   self.pc_col.get_flow_stats(),
                "switch_stats": self.pc_col.get_switch_stats(),
                "elephants":    self.pc_col.get_elephant_flows(),
            },
            "qst": {
                "queue":  {
                    "histograms": self.qst_col.get_queue_histogram(),
                    "avg_depths": self.qst_col.get_all_queue_depths(),
                },
                "stack":  {
                    "recent_events": self.qst_col.get_congestion_events(30),
                    "summary":       self.qst_col.get_congestion_summary(),
                },
                "tree":   {
                    "nodes":        self.qst_col.get_tree_paths(),
                    "unique_paths": self.qst_col.get_unique_paths(),
                },
            },
            "alerts": [a.to_dict() for a in self._alerts[-50:]],
        }

    def get_alerts(self, level: Optional[str] = None,
                   n: int = 50) -> List[dict]:
        with self._lock:
            alerts = list(self._alerts)
        if level:
            alerts = [a for a in alerts if a.level == level]
        return [a.to_dict() for a in alerts[-n:]]

    def export_json(self, path: str = "json/controller_stats.json"):
        snap = self.snapshot()
        with open(path, "w") as f:
            json.dump(snap, f, indent=2, default=list)
        log.info(f"Snapshot exportado → {path}")

    def register_alert_handler(self, fn: Callable):
        """Adiciona handler externo de alertas (ex.: brain_llm.py)."""
        self._alert_handlers.append(fn)


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--int-iface",     default="any")
    ap.add_argument("--pc-host",       default="0.0.0.0")
    ap.add_argument("--pc-port",       type=int, default=9556)
    ap.add_argument("--qst-iface",     default="any")
    ap.add_argument("--export",        default="json/controller_stats.json")
    ap.add_argument("--interval",      type=int, default=5)
    args = ap.parse_args()

    def print_alert(alert: TelemAlert):
        print(f"\n🚨 [{alert.level}] {alert.source}: {alert.message}")

    orch = TelemetryOrchestrator(
        int_iface=args.int_iface,
        postcard_host=args.pc_host,
        postcard_port=args.pc_port,
        qst_iface=args.qst_iface,
        alert_handlers=[print_alert],
    )
    orch.start()

    try:
        while True:
            time.sleep(args.interval)
            orch.export_json(args.export)
            snap = orch.snapshot()

            # Resumo rápido
            paths = snap["int"]["path_stats"]
            print(f"\n[INT] {len(paths)} caminhos observados")
            flows = snap["postcard"]["flow_stats"]
            print(f"[PC ] {len(flows)} fluxos monitorados")
            depths = snap["qst"]["queue"]["avg_depths"]
            print(f"[QST] {len(depths)} portas com fila medida")
            alerts = snap["alerts"]
            print(f"[🔔 ] {len(alerts)} alertas ativos")

    except KeyboardInterrupt:
        orch.stop()
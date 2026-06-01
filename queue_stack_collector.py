#!/usr/bin/env python3
"""
collector/queue_stack_tree_collector.py
=========================================
Coletor unificado para os três modos de telemetria estruturada:
  - FILA   (modo 1): latência e profundidade por porta, histograma
  - PILHA  (modo 2): eventos de congestionamento em LIFO
  - ÁRVORE (modo 3): métricas por nó da topologia em árvore + PathID

Integração com o projeto:
    gerent/orchestrator.py  →  QSTCollector
    gerent/brain_llm.py     →  get_congestion_events(), get_tree_paths()
    gerent/dashboard.py     →  get_queue_histogram()
"""

import socket
import struct
import threading
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Deque
from collections import defaultdict, deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [QST] %(levelname)s %(message)s"
)
log = logging.getLogger("qst_collector")

# ── Tamanhos de cabeçalho (devem bater com o P4) ─────────────────────────────
ETH_LEN        = 14
IP_LEN         = 20
UDP_LEN        = 8
TCP_LEN        = 20
TELEM_CTRL_LEN = 16   # mode(1)+hop_cnt(1)+flags(2)+path_id(4)+stack_depth(4)+pad(4)
QUEUE_REC_LEN  = 20   # port_id(2)+enq_ts(4)+deq_ts(4)+depth(4)+sojourn(4)+drop_prob(2)+pad(2)
STACK_EVT_LEN  = 24   # sw_id(4)+ts(4)+port(2)+type(2)+depth(4)+burst(4)+sev(1)+pad(3)
TREE_NODE_LEN  = 40   # sw_id(4)+level(1)+child(1)+pad(2)+path_bit(4)+in_p(4)+eg_p(4)+lat(4)+bw(4)+ts(4)+pad(8)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class QueueRecord:
    port_id:       int
    enqueue_ts:    int    # µs
    dequeue_ts:    int    # µs
    queue_depth:   int    # bytes
    sojourn_time:  int    # ns
    drop_prob:     int    # 0–65535

    @property
    def sojourn_us(self) -> float:
        return self.sojourn_time / 1000.0

    def latency_bucket(self, bucket_us: int = 100) -> int:
        """Retorna bucket de histograma (0..15) para sojourn."""
        return min(15, self.sojourn_us // bucket_us)


@dataclass
class StackEvent:
    switch_id:   int
    timestamp:   int      # µs
    port_id:     int
    event_type:  int      # 1=fila cheia, 2=ECN, 3=drop, 4=burst
    queue_depth: int
    burst_size:  int
    severity:    int      # 0–255

    EVENT_NAMES = {1: "FILA_CHEIA", 2: "ECN", 3: "DROP", 4: "BURST"}

    @property
    def event_name(self) -> str:
        return self.EVENT_NAMES.get(self.event_type, "DESCONHECIDO")


@dataclass
class TreeNode:
    switch_id:      int
    tree_level:     int   # 0=raiz, 1=inter, 2=folha
    child_index:    int
    path_bit:       int
    ingress_port:   int
    egress_port:    int
    link_latency:   int   # µs
    bandwidth_used: int   # Kbps
    timestamp:      int

    LEVEL_NAMES = {0: "RAIZ", 1: "INTERMEDIÁRIO", 2: "FOLHA"}

    @property
    def level_name(self) -> str:
        return self.LEVEL_NAMES.get(self.tree_level, "?")


@dataclass
class TelemPacket:
    mode:        int      # 1=FILA, 2=PILHA, 3=ÁRVORE
    hop_count:   int
    path_id:     int
    stack_depth: int
    src_ip:      str
    dst_ip:      str
    recv_time:   float    = field(default_factory=time.time)
    queue_recs:  List[QueueRecord] = field(default_factory=list)
    stack_evts:  List[StackEvent]  = field(default_factory=list)
    tree_nodes:  List[TreeNode]    = field(default_factory=list)

    MODE_NAMES = {1: "FILA", 2: "PILHA", 3: "ÁRVORE"}

    @property
    def mode_name(self) -> str:
        return self.MODE_NAMES.get(self.mode, "?")

    def path_signature(self) -> str:
        """Descrição textual do caminho para modo ÁRVORE."""
        if self.mode == 3:
            parts = [
                f"SW{n.switch_id}(L{n.tree_level}C{n.child_index})"
                for n in self.tree_nodes
            ]
            return "→".join(parts)
        return f"path_id={self.path_id:#010x}"


# ── Parser de pacotes capturados ──────────────────────────────────────────────

class QSTParser:
    """
    Parseia pacotes com cabeçalho de telemetria estruturada.
    O modo é detectado pelo campo diffserv[2:0] do IP.
    """

    @staticmethod
    def _parse_ip(raw: bytes, off: int) -> dict:
        iph = struct.unpack_from("!BBHHHBBH4s4s", raw, off)
        return {
            "ihl":      (iph[0] & 0xF) * 4,
            "diffserv": iph[1],
            "proto":    iph[6],
            "src":      socket.inet_ntoa(iph[8]),
            "dst":      socket.inet_ntoa(iph[9]),
        }

    @staticmethod
    def _parse_telem_ctrl(raw: bytes, off: int) -> dict:
        mode, hop_cnt, flags, _, path_id, stack_depth, _ = \
            struct.unpack_from("!BBHiIIi", raw, off)
        return {
            "mode":        mode,
            "hop_count":   hop_cnt,
            "flags":       flags,
            "path_id":     path_id,
            "stack_depth": stack_depth,
        }

    @staticmethod
    def _parse_queue_rec(raw: bytes, off: int) -> QueueRecord:
        port_id, enq, deq, depth, sojourn, drop, _ = \
            struct.unpack_from("!HIIIIH H", raw, off)
        return QueueRecord(
            port_id=port_id, enqueue_ts=enq, dequeue_ts=deq,
            queue_depth=depth, sojourn_time=sojourn, drop_prob=drop
        )

    @staticmethod
    def _parse_stack_evt(raw: bytes, off: int) -> StackEvent:
        sw_id, ts, port, ev_type, depth, burst, sev, _, _ = \
            struct.unpack_from("!IIHHIIBBH", raw, off)
        return StackEvent(
            switch_id=sw_id, timestamp=ts, port_id=port,
            event_type=ev_type, queue_depth=depth,
            burst_size=burst, severity=sev
        )

    @staticmethod
    def _parse_tree_node(raw: bytes, off: int) -> TreeNode:
        sw_id, level, child, _, path_bit, in_p, eg_p, lat, bw, ts, _ = \
            struct.unpack_from("!IBBhIIIIIIQ", raw, off)
        return TreeNode(
            switch_id=sw_id, tree_level=level, child_index=child,
            path_bit=path_bit, ingress_port=in_p, egress_port=eg_p,
            link_latency=lat, bandwidth_used=bw, timestamp=ts
        )

    def parse(self, raw: bytes) -> Optional[TelemPacket]:
        try:
            off = ETH_LEN
            ip  = self._parse_ip(raw, off)
            if ip["proto"] not in (6, 17):   # TCP ou UDP
                return None

            mode = ip["diffserv"] & 0x03
            if mode == 0:
                return None

            off += ip["ihl"]
            off += UDP_LEN if ip["proto"] == 17 else TCP_LEN

            ctrl = self._parse_telem_ctrl(raw, off)
            off += TELEM_CTRL_LEN

            pkt = TelemPacket(
                mode=mode,
                hop_count=ctrl["hop_count"],
                path_id=ctrl["path_id"],
                stack_depth=ctrl["stack_depth"],
                src_ip=ip["src"],
                dst_ip=ip["dst"],
            )

            if mode == 1:   # FILA
                for _ in range(ctrl["hop_count"]):
                    if off + QUEUE_REC_LEN > len(raw):
                        break
                    pkt.queue_recs.append(self._parse_queue_rec(raw, off))
                    off += QUEUE_REC_LEN

            elif mode == 2:  # PILHA
                for _ in range(ctrl["stack_depth"]):
                    if off + STACK_EVT_LEN > len(raw):
                        break
                    pkt.stack_evts.append(self._parse_stack_evt(raw, off))
                    off += STACK_EVT_LEN

            elif mode == 3:  # ÁRVORE
                for _ in range(ctrl["hop_count"]):
                    if off + TREE_NODE_LEN > len(raw):
                        break
                    pkt.tree_nodes.append(self._parse_tree_node(raw, off))
                    off += TREE_NODE_LEN

            return pkt

        except (struct.error, IndexError):
            return None


# ── Coletor principal ─────────────────────────────────────────────────────────

class QSTCollector:
    """
    Captura pacotes com telemetria de Fila, Pilha e Árvore.

    Uso:
        col = QSTCollector(iface="eth0")
        col.start()
        hist = col.get_queue_histogram(port=1)
        evts = col.get_congestion_events(severity_min=100)
        tree = col.get_tree_paths()
    """

    def __init__(self, iface: str = "any", history_size: int = 1000):
        self.iface    = iface
        self.parser   = QSTParser()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock    = threading.Lock()

        self._history: Deque[TelemPacket] = deque(maxlen=history_size)

        # FILA: histograma de latência [porta][bucket] → contagem
        self._q_histogram: Dict[int, List[int]] = defaultdict(lambda: [0] * 16)
        # FILA: EWMA de profundidade por porta
        self._q_avg_depth: Dict[int, float] = defaultdict(float)

        # PILHA: eventos recentes
        self._stack_events: Deque[dict] = deque(maxlen=500)

        # ÁRVORE: métricas por switch_id
        self._tree_switch: Dict[int, dict] = defaultdict(lambda: {
            "pkt_count": 0,
            "avg_lat":   0.0,
            "avg_bw":    0.0,
            "path_ids":  set(),
        })

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        log.info(f"QSTCollector iniciado na interface {self.iface!r}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("QSTCollector parado")

    def _capture_loop(self):
        try:
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                 socket.htons(0x0800))
            if self.iface != "any":
                sock.bind((self.iface, 0))
            sock.settimeout(1.0)
        except PermissionError:
            log.error("Permissão negada — execute como root")
            return

        while self._running:
            try:
                raw, _ = sock.recvfrom(65535)
                pkt = self.parser.parse(raw)
                if pkt:
                    self._process(pkt)
            except socket.timeout:
                continue
        sock.close()

    def _process(self, pkt: TelemPacket):
        with self._lock:
            self._history.append(pkt)

            if pkt.mode == 1:        # ── FILA ──
                for rec in pkt.queue_recs:
                    bucket = rec.latency_bucket()
                    self._q_histogram[rec.port_id][bucket] += 1
                    prev = self._q_avg_depth[rec.port_id]
                    self._q_avg_depth[rec.port_id] = prev * 0.9 + rec.queue_depth * 0.1

            elif pkt.mode == 2:      # ── PILHA ──
                for evt in pkt.stack_evts:
                    self._stack_events.appendleft({
                        "switch_id":  evt.switch_id,
                        "timestamp":  evt.timestamp,
                        "port_id":    evt.port_id,
                        "event_name": evt.event_name,
                        "queue_depth":evt.queue_depth,
                        "severity":   evt.severity,
                        "recv_time":  pkt.recv_time,
                    })

            elif pkt.mode == 3:      # ── ÁRVORE ──
                for node in pkt.tree_nodes:
                    sm = self._tree_switch[node.switch_id]
                    n  = sm["pkt_count"] + 1
                    sm["pkt_count"] = n
                    sm["avg_lat"]   = sm["avg_lat"] * 0.9 + node.link_latency * 0.1
                    sm["avg_bw"]    = sm["avg_bw"]  * 0.9 + node.bandwidth_used * 0.1
                    sm["path_ids"].add(pkt.path_id)

        log.debug(
            f"[{pkt.mode_name}] {pkt.src_ip}→{pkt.dst_ip} "
            f"hops={pkt.hop_count} sig={pkt.path_signature()}"
        )

    # ── API FILA ──────────────────────────────────────────────────────────
    def get_queue_histogram(self, port: Optional[int] = None) -> dict:
        """Retorna histograma de latência de fila (buckets de 100µs)."""
        with self._lock:
            if port is not None:
                h = self._q_histogram[port]
                return {
                    "port": port,
                    "buckets_100us": list(h),
                    "avg_depth": round(self._q_avg_depth[port], 2),
                }
            return {
                str(p): {
                    "buckets_100us": list(h),
                    "avg_depth": round(self._q_avg_depth[p], 2),
                }
                for p, h in self._q_histogram.items()
            }

    def get_all_queue_depths(self) -> Dict[str, float]:
        with self._lock:
            return {str(p): round(v, 2) for p, v in self._q_avg_depth.items()}

    # ── API PILHA ─────────────────────────────────────────────────────────
    def get_congestion_events(self, n: int = 50,
                              severity_min: int = 0) -> List[dict]:
        """Retorna os eventos mais recentes do topo da pilha."""
        with self._lock:
            evts = list(self._stack_events)
        return [e for e in evts if e["severity"] >= severity_min][:n]

    def get_congestion_summary(self) -> dict:
        """Sumário de eventos por tipo e switch."""
        with self._lock:
            by_type:   Dict[str, int] = defaultdict(int)
            by_switch: Dict[str, int] = defaultdict(int)
            for e in self._stack_events:
                by_type[e["event_name"]] += 1
                by_switch[str(e["switch_id"])] += 1
        return {
            "total_events": len(self._stack_events),
            "by_event_type": dict(by_type),
            "by_switch": dict(by_switch),
        }

    # ── API ÁRVORE ────────────────────────────────────────────────────────
    def get_tree_paths(self) -> dict:
        """Retorna métricas de cada nó da árvore."""
        with self._lock:
            result = {}
            for sw_id, m in self._tree_switch.items():
                result[str(sw_id)] = {
                    "pkt_count":  m["pkt_count"],
                    "avg_lat_us": round(m["avg_lat"], 2),
                    "avg_bw_kbps":round(m["avg_bw"], 2),
                    "path_ids":   [f"{p:#010x}" for p in m["path_ids"]],
                }
        return result

    def get_unique_paths(self) -> List[str]:
        """Lista todos os path_ids únicos observados."""
        with self._lock:
            all_paths: set = set()
            for m in self._tree_switch.values():
                all_paths |= m["path_ids"]
        return [f"{p:#010x}" for p in sorted(all_paths)]

    # ── API genérica ──────────────────────────────────────────────────────
    def get_recent(self, n: int = 50, mode: Optional[int] = None) -> List[dict]:
        with self._lock:
            hist = list(self._history)[-n * 3:]

        result = []
        for pkt in reversed(hist):
            if mode and pkt.mode != mode:
                continue
            d = {
                "mode":           pkt.mode_name,
                "hop_count":      pkt.hop_count,
                "path_signature": pkt.path_signature(),
                "src_ip":         pkt.src_ip,
                "dst_ip":         pkt.dst_ip,
                "recv_time":      pkt.recv_time,
            }
            result.append(d)
            if len(result) >= n:
                break
        return result

    def export_json(self, path: str = "qst_telemetry.json"):
        data = {
            "timestamp":    time.time(),
            "queue":  {
                "histograms":  self.get_queue_histogram(),
                "avg_depths":  self.get_all_queue_depths(),
            },
            "stack":  {
                "recent_events": self.get_congestion_events(50),
                "summary":       self.get_congestion_summary(),
            },
            "tree":   {
                "nodes":        self.get_tree_paths(),
                "unique_paths": self.get_unique_paths(),
            },
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=list)
        log.info(f"Exportado → {path}")


# ── Modo standalone ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Queue/Stack/Tree Telemetry Collector")
    ap.add_argument("--iface",    default="any")
    ap.add_argument("--interval", type=int, default=5)
    ap.add_argument("--export",   default="qst_telemetry.json")
    args = ap.parse_args()

    col = QSTCollector(iface=args.iface)
    col.start()

    try:
        while True:
            time.sleep(args.interval)

            print("\n╔══ FILA ══════════════════════════════════════")
            for port, depth in col.get_all_queue_depths().items():
                hist = col.get_queue_histogram(int(port))
                print(f"  Porta {port}: avg_depth={depth}B "
                      f"hist={hist['buckets_100us'][:8]}…")

            print("╠══ PILHA ═════════════════════════════════════")
            summ = col.get_congestion_summary()
            print(f"  Total eventos: {summ['total_events']}")
            for etype, cnt in summ.get("by_event_type", {}).items():
                print(f"    {etype}: {cnt}")

            print("╠══ ÁRVORE ════════════════════════════════════")
            for sw, m in col.get_tree_paths().items():
                print(f"  SW{sw}: lat={m['avg_lat_us']}µs "
                      f"bw={m['avg_bw_kbps']}Kbps "
                      f"paths={m['path_ids'][:3]}")
            print("╚══════════════════════════════════════════════")

            col.export_json(args.export)
    except KeyboardInterrupt:
        col.stop()
#!/usr/bin/env python3
"""
collector/postcard_collector.py
================================
Coletor para Postcard Telemetria (BMv2).
Recebe pequenos relatórios UDP enviados pelo switch (os "postcards")
sem modificar o pacote original de dados.

Integração:
    gerent/orchestrator.py  →  PostcardCollector
    gerent/dashboard.py     →  get_flow_stats(), get_switch_stats()
"""

import socket
import struct
import threading
import time
import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List
from collections import defaultdict, deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [POSTCARD] %(levelname)s %(message)s"
)
log = logging.getLogger("postcard")

# ── Protocolo ────────────────────────────────────────────────────────────────
COLLECTOR_PORT = 9556   # deve bater com COLLECTOR_PORT no P4

# Formato do postcard (big-endian):
# switch_id(4) seq_num(4) flow_src_ip(4) flow_dst_ip(4)
# flow_src_port(2) flow_dst_port(2) flow_protocol(1) rsvd(1)
# ingress_port(2) egress_port(2) ingress_tstamp(4) egress_tstamp(4)
# queue_depth(4) queue_latency(4) pkt_length(4) drop_count(4)
POSTCARD_FMT  = "!IIII HH BB HH II II II"
POSTCARD_SIZE = struct.calcsize(POSTCARD_FMT)  # 52 bytes


@dataclass
class Postcard:
    switch_id:       int
    seq_num:         int
    flow_src_ip:     str
    flow_dst_ip:     str
    flow_src_port:   int
    flow_dst_port:   int
    flow_protocol:   int
    ingress_port:    int
    egress_port:     int
    ingress_tstamp:  int   # µs
    egress_tstamp:   int   # µs
    queue_depth:     int   # pacotes
    queue_latency:   int   # ns
    pkt_length:      int   # bytes
    drop_count:      int
    recv_time:       float = 0.0

    @property
    def flow_key(self) -> str:
        return (f"{self.flow_src_ip}:{self.flow_src_port}"
                f"→{self.flow_dst_ip}:{self.flow_dst_port}"
                f"/{self.flow_protocol}")

    @property
    def sojourn_us(self) -> int:
        return self.egress_tstamp - self.ingress_tstamp

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flow_key"]   = self.flow_key
        d["sojourn_us"] = self.sojourn_us
        return d


def parse_postcard(data: bytes, src_addr: str) -> Optional[Postcard]:
    if len(data) < POSTCARD_SIZE:
        return None
    try:
        f = struct.unpack(POSTCARD_FMT, data[:POSTCARD_SIZE])
    except struct.error:
        return None

    return Postcard(
        switch_id      = f[0],
        seq_num        = f[1],
        flow_src_ip    = socket.inet_ntoa(struct.pack("!I", f[2])),
        flow_dst_ip    = socket.inet_ntoa(struct.pack("!I", f[3])),
        flow_src_port  = f[4],
        flow_dst_port  = f[5],
        flow_protocol  = f[6],
        # f[7] = rsvd
        ingress_port   = f[8],
        egress_port    = f[9],
        ingress_tstamp = f[10],
        egress_tstamp  = f[11],
        queue_depth    = f[12],
        queue_latency  = f[13],
        pkt_length     = f[14],
        drop_count     = f[15],
        recv_time      = time.time(),
    )


# ── Estatísticas de fluxo ────────────────────────────────────────────────────

class FlowStats:
    def __init__(self):
        self.pkt_count:        int = 0
        self.byte_count:       int = 0
        self.drop_total:       int = 0
        self.last_drop:        int = 0
        self.sojourn_sum:      int = 0
        self.sojourn_max:      int = 0
        self.queue_depth_sum:  int = 0
        self.queue_depth_max:  int = 0
        self.last_seq:         int = 0
        self.seq_gaps:         int = 0  # postcards perdidos

    def update(self, pc: Postcard):
        self.pkt_count       += 1
        self.byte_count      += pc.pkt_length
        self.drop_total       = pc.drop_count
        self.sojourn_sum     += pc.sojourn_us
        self.sojourn_max      = max(self.sojourn_max, pc.sojourn_us)
        self.queue_depth_sum += pc.queue_depth
        self.queue_depth_max  = max(self.queue_depth_max, pc.queue_depth)

        if self.last_seq > 0 and pc.seq_num > self.last_seq + 1:
            self.seq_gaps += pc.seq_num - self.last_seq - 1
        self.last_seq = pc.seq_num

    @property
    def avg_sojourn_us(self) -> float:
        return self.sojourn_sum / max(1, self.pkt_count)

    @property
    def avg_queue_depth(self) -> float:
        return self.queue_depth_sum / max(1, self.pkt_count)

    def to_dict(self) -> dict:
        return {
            "pkt_count":       self.pkt_count,
            "byte_count":      self.byte_count,
            "drop_total":      self.drop_total,
            "avg_sojourn_us":  round(self.avg_sojourn_us, 2),
            "max_sojourn_us":  self.sojourn_max,
            "avg_queue_depth": round(self.avg_queue_depth, 2),
            "max_queue_depth": self.queue_depth_max,
            "seq_gaps":        self.seq_gaps,
        }


# ── Coletor principal ─────────────────────────────────────────────────────────

class PostcardCollector:
    """
    Recebe postcards UDP na porta COLLECTOR_PORT e mantém
    estatísticas por fluxo e por switch.

    Uso:
        pc = PostcardCollector(port=9556)
        pc.start()
        stats = pc.get_flow_stats()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = COLLECTOR_PORT,
                 history_size: int = 2000):
        self.host          = host
        self.port          = port
        self._running      = False
        self._thread:      Optional[threading.Thread] = None
        self._lock         = threading.Lock()
        self._history:     deque[Postcard] = deque(maxlen=history_size)

        # Estatísticas por chave de fluxo
        self._flow_stats:   Dict[str, FlowStats] = defaultdict(FlowStats)
        # Latência média por switch (EWMA α=0.1)
        self._switch_lat:   Dict[int, float] = defaultdict(float)
        # Profundidade de fila por switch
        self._switch_queue: Dict[int, float] = defaultdict(float)
        # Drops acumulados por switch
        self._switch_drops: Dict[int, int]   = defaultdict(int)

        # Callbacks externos (ex.: orquestrador)
        self._callbacks: List = []

    def register_callback(self, fn):
        """Registra função chamada a cada postcard recebido."""
        self._callbacks.append(fn)

    # ── Controle ──────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"PostcardCollector ouvindo em {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("PostcardCollector parado")

    # ── Loop de recepção ──────────────────────────────────────────────────
    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.settimeout(1.0)
        log.info(f"Socket UDP aberto em {self.host}:{self.port}")

        while self._running:
            try:
                data, addr = sock.recvfrom(256)
                pc = parse_postcard(data, addr[0])
                if pc:
                    self._process(pc)
            except socket.timeout:
                continue
            except Exception as exc:
                log.warning(f"Erro ao receber postcard: {exc}")

        sock.close()

    # ── Processamento ─────────────────────────────────────────────────────
    def _process(self, pc: Postcard):
        with self._lock:
            self._history.append(pc)
            self._flow_stats[pc.flow_key].update(pc)

            α = 0.1
            prev_lat   = self._switch_lat.get(pc.switch_id, 0)
            prev_queue = self._switch_queue.get(pc.switch_id, 0)
            self._switch_lat[pc.switch_id]   = prev_lat   * (1 - α) + pc.sojourn_us  * α
            self._switch_queue[pc.switch_id] = prev_queue * (1 - α) + pc.queue_depth * α
            self._switch_drops[pc.switch_id] = pc.drop_count

        log.debug(
            f"[PC] SW{pc.switch_id} seq={pc.seq_num} "
            f"{pc.flow_key} q={pc.queue_depth} lat={pc.sojourn_us}µs"
        )

        for cb in self._callbacks:
            try:
                cb(pc)
            except Exception as exc:
                log.warning(f"Callback falhou: {exc}")

    # ── API pública ───────────────────────────────────────────────────────
    def get_flow_stats(self) -> Dict[str, dict]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._flow_stats.items()}

    def get_switch_stats(self) -> Dict[str, dict]:
        with self._lock:
            result = {}
            for sw_id in set(list(self._switch_lat) +
                             list(self._switch_queue)):
                result[str(sw_id)] = {
                    "avg_sojourn_us":   round(self._switch_lat.get(sw_id, 0), 2),
                    "avg_queue_depth":  round(self._switch_queue.get(sw_id, 0), 2),
                    "drop_count":       self._switch_drops.get(sw_id, 0),
                }
        return result

    def get_recent(self, n: int = 50) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in list(self._history)[-n:]]

    def get_elephant_flows(self, byte_threshold: int = 1_000_000) -> Dict[str, dict]:
        """Retorna fluxos com mais de byte_threshold bytes (elephants)."""
        with self._lock:
            return {
                k: v.to_dict()
                for k, v in self._flow_stats.items()
                if v.byte_count >= byte_threshold
            }

    def export_json(self, path: str = "postcard_telemetry.json"):
        data = {
            "timestamp":    time.time(),
            "flow_stats":   self.get_flow_stats(),
            "switch_stats": self.get_switch_stats(),
            "elephants":    self.get_elephant_flows(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info(f"Exportado → {path}")


# ── Modo standalone ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Postcard Telemetry Collector")
    ap.add_argument("--host",     default="0.0.0.0")
    ap.add_argument("--port",     type=int, default=COLLECTOR_PORT)
    ap.add_argument("--interval", type=int, default=5)
    ap.add_argument("--export",   default="postcard_telemetry.json")
    args = ap.parse_args()

    collector = PostcardCollector(host=args.host, port=args.port)
    collector.start()

    try:
        while True:
            time.sleep(args.interval)
            print("\n── Fluxos ──────────────────────────────")
            for flow, stats in collector.get_flow_stats().items():
                print(f"  {flow}")
                print(f"    pkts={stats['pkt_count']} "
                      f"bytes={stats['byte_count']} "
                      f"drops={stats['drop_total']}")
                print(f"    avg_sojourn={stats['avg_sojourn_us']}µs "
                      f"avg_q={stats['avg_queue_depth']:.1f}")
            print("── Switches ────────────────────────────")
            for sw, s in collector.get_switch_stats().items():
                print(f"  SW{sw}: sojourn={s['avg_sojourn_us']}µs "
                      f"queue={s['avg_queue_depth']:.1f} "
                      f"drops={s['drop_count']}")
            collector.export_json(args.export)
    except KeyboardInterrupt:
        collector.stop()
#!/usr/bin/env python3

import socket
import json
import time
import argparse
import threading
import struct

from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from bm_runtime.standard import Standard

THRIFT_PORT = 9090


# =========================
# UTILS
# =========================
def int_to_ip(value):
    return ".".join(map(str, value.to_bytes(4, byteorder="big")))


def proto_to_str(proto):
    return {
        6: "TCP",
        17: "UDP",
        1: "ICMP"
    }.get(proto, str(proto))


# =========================
# THRIFT
# =========================
def connect_thrift():
    transport = TSocket.TSocket("127.0.0.1", THRIFT_PORT)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = Standard.Client(protocol)
    transport.open()
    print("[AGENT] Conectado ao BMv2")
    return client


def read_register(client, name, size=1024):
    values = []
    for i in range(size):
        try:
            v = client.bm_register_read(0, name, i)
        except:
            v = 0
        values.append(v)
    return values


# =========================
# BUILD FLOWS REAIS
# =========================
def build_flows(bytes_reg, pkts_reg, ip_src, ip_dst, port_src, port_dst, proto):
    flows = []

    for i in range(len(bytes_reg)):
        if bytes_reg[i] == 0 and pkts_reg[i] == 0:
            continue

        flows.append({
            "idx": i,
            "src_ip": int_to_ip(ip_src[i]),
            "dst_ip": int_to_ip(ip_dst[i]),
            "src_port": port_src[i],
            "dst_port": port_dst[i],
            "proto_name": proto_to_str(proto[i]),
            "bytes": bytes_reg[i],
            "pkts": pkts_reg[i]
        })

    return flows


# =========================
# TELEMETRIA
# =========================
def telemetry_loop(client, controller_ip, controller_port, interval):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    prev_bytes = [0]*1024
    prev_pkts  = [0]*1024
    prev_time  = time.time()

    seq = 0

    while True:
        now = time.time()
        dt = now - prev_time

        bytes_reg = read_register(client, "reg_bytes")
        pkts_reg  = read_register(client, "reg_pkts")

        ip_src    = read_register(client, "reg_ip_src")
        ip_dst    = read_register(client, "reg_ip_dst")
        port_src  = read_register(client, "reg_port_src")
        port_dst  = read_register(client, "reg_port_dst")
        proto     = read_register(client, "reg_proto")

        flows = []

        for i in range(len(bytes_reg)):
            dbytes = bytes_reg[i] - prev_bytes[i]
            dpkts  = pkts_reg[i]  - prev_pkts[i]

            if dbytes <= 0 and dpkts <= 0:
                continue

            flows.append({
                "idx": i,
                "src_ip": int_to_ip(ip_src[i]),
                "dst_ip": int_to_ip(ip_dst[i]),
                "src_port": port_src[i],
                "dst_port": port_dst[i],
                "proto_name": proto_to_str(proto[i]),

                # 🔥 métricas reais
                "bytes": dbytes,
                "pkts": dpkts,
                "bps": dbytes / dt,
                "pps": dpkts / dt,
                "dt": dt
            })

        report = {
            "seq": seq,
            "timestamp": now,
            "dt": dt,
            "flow_count": len(flows),
            "flows": flows
        }

        sock.sendto(json.dumps(report).encode(),
                    (controller_ip, controller_port))

        print(f"[AGENT] seq={seq} flows={len(flows)} dt={dt:.2f}s")

        prev_bytes = bytes_reg
        prev_pkts  = pkts_reg
        prev_time  = now

        seq += 1
        time.sleep(interval)

# =========================
# RECEBER COMANDOS
# =========================
def command_listener(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))

    print(f"[AGENT] Escutando comandos em {port}")

    while True:
        data, _ = sock.recvfrom(65535)
        cmd = json.loads(data.decode())

        print(f"[AGENT] CMD: {cmd}")

        # Aqui você pode evoluir:
        # - instalar regra no switch
        # - alterar DSCP
        # - ECMP


# =========================
# MAIN
# =========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--cmd-port", type=int, default=9998)
    args = parser.parse_args()

    client = connect_thrift()

    threading.Thread(
        target=telemetry_loop,
        args=(client, args.controller, args.port, args.interval),
        daemon=True
    ).start()

    threading.Thread(
        target=command_listener,
        args=(args.cmd_port,),
        daemon=True
    ).start()

    while True:
        time.sleep(10)


if __name__ == "__main__":
    main()
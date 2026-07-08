import socket
import json

from config import COLLECTOR_IP, COLLECTOR_PORT


class Collector:

    def __init__(self, flow_table):

        self.flow_table = flow_table

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((COLLECTOR_IP, COLLECTOR_PORT))
        self.sock.settimeout(1.0)

        print("[Collector] listening on", COLLECTOR_IP, COLLECTOR_PORT)

    def receive(self):

        while True:

            try:

                data, _ = self.sock.recvfrom(4096)

                t = json.loads(data.decode())

                print("[Collector] packet:", t)

                self.flow_table.add_packet(t)

            except socket.timeout:
                continue

            except Exception as e:
                print("[Collector ERROR]", e)
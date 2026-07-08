import socket
import json


class BMv2Collector:

    def __init__(self, flow_table, decoder):

        self.flow_table = flow_table
        self.decoder = decoder

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 5000))

        print("[BMv2 Collector] listening UDP 5000")

    def run(self):

        while True:

            data, addr = self.sock.recvfrom(8192)

            try:

                msg = json.loads(data.decode())

                flow = self.decoder.decode(msg)

                print("[BMv2] packet:", flow)

                self.flow_table.update(flow)

            except Exception as e:
                print("[BMv2 ERROR]", e)
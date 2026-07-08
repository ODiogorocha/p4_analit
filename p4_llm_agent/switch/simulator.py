import json
import socket
import time

from config import COLLECTOR_IP
from config import COLLECTOR_PORT


socket_client = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

while True:

    flow = {

        "src_ip": "10.0.0.1",

        "dst_ip": "10.0.0.2",

        "src_port": 54123,

        "dst_port": 443,

        "protocol": "TCP",

        "packets": 4300,

        "bytes": 240000000,

        "duration": 75,

        "latency": 3.8,

        "queue_depth": 7

    }

    socket_client.sendto(

        json.dumps(flow).encode(),

        (
            COLLECTOR_IP,
            COLLECTOR_PORT
        )

    )

    print("Fluxo enviado")

    time.sleep(5)
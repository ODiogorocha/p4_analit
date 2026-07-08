import subprocess
import time
import re

class SwitchReader:
    def __init__(self, thrift_port=9090):
        self.thrift_port = thrift_port

    def read_tables(self):
        cmd = [
            "simple_switch_CLI",
            "--thrift-port",
            str(self.thrift_port)
        ]

        # comandos enviados para CLI
        cli_commands = """
table_dump ipv4_lpm
counter_read flow_counter
"""

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        out, err = process.communicate(cli_commands)

        if err:
            print("[SWITCH ERROR]", err)

        return out

    def parse_flows(self, cli_output: str):
        flows = []

        # exemplo simples de parsing
        blocks = cli_output.split("entry")

        for b in blocks:
            if "ipv4" in b:
                match_ip = re.findall(r"(\d+\.\d+\.\d+\.\d+)", b)
                if len(match_ip) >= 2:
                    flows.append({
                        "src_ip": match_ip[0],
                        "dst_ip": match_ip[1],
                        "raw": b
                    })

        return flows

    def get_flows(self):
        output = self.read_tables()
        return self.parse_flows(output)
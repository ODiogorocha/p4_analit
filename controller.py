import time
import threading
import requests
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI
from scapy.all import sniff, get_if_list

THRESHOLD_BYTES = 500000  # elephant threshold

class Controller:

    def __init__(self):
        self.sw = SimpleSwitchThriftAPI(9090)

    # 🔥 leitura REAL do switch
    def monitor_registers(self):
        print("📡 Lendo registradores do switch...\n")

        while True:
            for i in range(10):
                bytes_count = self.sw.register_read("byte_cnt", i)

                if bytes_count > 0:
                    print(f"[FLOW {i}] {bytes_count} bytes")

                if bytes_count > THRESHOLD_BYTES:
                    print(f"\n🐘 ELEPHANT FLOW DETECTADO: {i}")

                    decision = self.call_llm(bytes_count)
                    print(f"🧠 Decisão LLM: {decision}\n")

            time.sleep(2)

    # 🔥 chamada ao Phi3
    def call_llm(self, bytes_count):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "phi3",
                    "prompt": f"Flow com {bytes_count} bytes. Isso é um elephant flow? O que fazer?"
                }
            )
            return response.json().get("response", "")
        except:
            return "Erro ao chamar LLM"

    # 🔍 sniff opcional (debug)
    def sniff_traffic(self):
        iface = next((i for i in get_if_list() if "h1-eth0" in i), None)

        if iface:
            print(f"👀 Sniffando em {iface}")
            sniff(iface=iface, prn=lambda x: print("Pacote capturado"), store=0)
        else:
            print("Interface não encontrada para sniff")

    def run(self):
        t = threading.Thread(target=self.monitor_registers)
        t.start()

        # opcional (debug)
        self.sniff_traffic()


if __name__ == "__main__":
    Controller().run()
from mininet.net import Mininet
import time

def run():
    net = Mininet()
    net.start()

    h1, h2 = net.hosts

    print("🔥 Gerando tráfego ELEPHANT...")
    h2.cmd("iperf -s &")

    time.sleep(1)

    # fluxo grande (elephant)
    h1.cmd("iperf -c 10.0.0.2 -t 20")

    net.stop()

if __name__ == "__main__":
    run()
    
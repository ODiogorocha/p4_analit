from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.link import TCLink

def run():
    net = Mininet(controller=RemoteController, link=TCLink)

    c0 = net.addController('c0')

    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.1.1')

    s1 = net.addSwitch('s1')

    net.addLink(h1, s1)
    net.addLink(h2, s1)

    net.start()

    print("🔥 Gerando tráfego...")
    h2.cmd("iperf -s &")
    h1.cmd("iperf -c 10.0.1.1 -t 60 &")

    CLI(net)
    net.stop()

if __name__ == "__main__":
    run()
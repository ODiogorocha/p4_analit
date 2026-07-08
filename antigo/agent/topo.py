# topo.py - Rede Mininet com envio de métricas
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
import time
import subprocess

def run():
    # Cria rede sem controller (OVS em modo standalone)
    net = Mininet(controller=None, switch=OVSSwitch)
    
    # Hosts na mesma rede
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    s1 = net.addSwitch('s1')
    
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    
    net.start()
    
    # Configura switches
    s1.cmd('ovs-vsctl set bridge s1 protocols=OpenFlow13')
    
    print("\n" + "="*50)
    print("🌐 Rede Mininet criada!")
    print(f"h1: 10.0.0.1")
    print(f"h2: 10.0.0.2")
    print("="*50 + "\n")
    
    # Testa conectividade
    print("🔄 Testando conectividade...")
    result = h1.cmd('ping -c 1 10.0.0.2')
    if '1 received' in result:
        print("✅ Conectividade OK!")
    
    # Gera tráfego de fundo (opcional)
    print("\n🔥 Iniciando geradores de tráfego...")
    
    # iperf servidor no h2
    h2.cmd('iperf -s -u &')  # UDP server
    h2.cmd('iperf -s &')      # TCP server
    
    # Gera tráfego constante do h1 para h2
    h1.cmd('iperf -c 10.0.0.2 -t 3600 -b 10M &')  # 10 Mbps constante
    
    print("📊 Tráfego gerado: 10 Mbps constante de h1→h2")
    print("🐘 Para gerar elephant flow, rode no Mininet CLI:\n")
    print("  h1 iperf -c 10.0.0.2 -t 60 -b 100M  # 100 Mbps por 60s\n")
    
    # Abre CLI para interação
    CLI(net)
    
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
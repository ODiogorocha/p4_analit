
#!/bin/bash

echo "========================================="
echo "🐘 GERANDO ELEPHANT FLOW DE TESTE"
echo "========================================="

# Criar topologia Mininet temporária
sudo python3 - << 'PYTHON_EOF'
from mininet.net import Mininet
from mininet.node import OVSSwitch
import time

print("🌐 Criando rede Mininet...")
net = Mininet(controller=None, switch=OVSSwitch)

h1 = net.addHost('h1', ip='10.0.0.1/24')
h2 = net.addHost('h2', ip='10.0.0.2/24')
s1 = net.addSwitch('s1')

net.addLink(h1, s1)
net.addLink(h2, s1)

net.start()

print("📡 Iniciando servidor iperf no h2...")
h2.cmd('iperf -s &')

time.sleep(2)

print("🔥 Gerando elephant flow: 100Mbps por 30 segundos...")
print("   (Isso deve ser detectado pelo Agent)")

h1.cmd('iperf -c 10.0.0.2 -t 30 -b 100M')

print("\n✅ Teste concluído!")
net.stop()
PYTHON_EOF

echo ""
echo "📊 Verifique as decisões no Host:"
echo "   cat /home/diogo/Documentos/codigos/p4_analit/json/decisions.json"
PYTHON_EOF

#!/bin/bash

echo "=== TESTE BMv2 ==="

# Limpa tudo
sudo pkill -9 simple_switch
sudo pkill -9 mn
sudo mn -c
sleep 2

# Compila P4
p4c-bm2-ss --p4v 16 --p4runtime-files p4info.txt -o elephant_monitor.json p4/elephant_monitor.p4

# Inicia Mininet
sudo mn --topo single,2 --controller none --mac --switch ovs &
sleep 5

# Inicia BMv2
sudo simple_switch --thrift-port 9090 -i 1@s1-eth1 -i 2@s1-eth2 elephant_monitor.json &
sleep 5

# Configura IPs
sudo ip netns exec h1 ifconfig h1-eth0 10.0.0.1/24 up
sudo ip netns exec h2 ifconfig h2-eth0 10.0.0.2/24 up

# Configura rotas
simple_switch_CLI --thrift-port 9090 <<< "table_add ipv4_forward forward 10.0.0.1 => 1"
simple_switch_CLI --thrift-port 9090 <<< "table_add ipv4_forward forward 10.0.0.2 => 2"

# Testa ping
echo "Testando ping..."
sudo ip netns exec h1 ping -c 2 10.0.0.2

# Gera tráfego
echo "Gerando tráfego..."
sudo ip netns exec h2 iperf -s &
sleep 2
sudo ip netns exec h1 iperf -c 10.0.0.2 -t 10 -b 10M &

# Aguarda tráfego
sleep 5

# Lê registradores
echo "Registradores:"
simple_switch_CLI --thrift-port 9090 <<< "register_read reg_bytes 0"
simple_switch_CLI --thrift-port 9090 <<< "register_read reg_pkts 0"

echo "=== FIM ==="

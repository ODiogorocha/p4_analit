import os

print("🔥 Gerando elephant flow...")

# 100MB de tráfego
os.system("iperf -s &")
os.system("iperf -c 10.0.1.1 -t 10 -i 1")
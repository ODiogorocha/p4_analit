from switch_reader import SwitchReader
from window.flow_window import FlowWindow
from controller.controller import Controller

class Collector:
    def __init__(self):
        self.switch = SwitchReader(9090)
        self.window = FlowWindow(10)
        self.controller = Controller()

    def poll_switch(self):
        flows = self.switch.get_flows()

        for f in flows:
            print("[SWITCH FLOW]", f)
            self.window.add(f)

        if self.window.is_full():
            batch = self.window.flush()
            result = self.controller.analyze_window(batch)

            print("\n[LLM RESULT]")
            print(result)

    def start(self):
        import time

        print("[Collector] polling switch...")

        while True:
            self.poll_switch()
            time.sleep(2)
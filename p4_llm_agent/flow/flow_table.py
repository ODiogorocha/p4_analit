import time
from flow.flow import Flow


class FlowTable:

    def __init__(self):

        self.flows = {}

    def key(self, f):

        return (
            f["src_ip"],
            f["dst_ip"],
            f["src_port"],
            f["dst_port"],
            f["protocol"]
        )

    def update(self, f):

        k = self.key(f)

        if k not in self.flows:
            self.flows[k] = Flow(k)

        self.flows[k].update(f)

        print("[FLOW] updated:", k)

    def expire(self, window):

        now = time.time()

        expired = []

        for k, f in list(self.flows.items()):

            if now - f.last_seen >= window:

                expired.append(f)
                del self.flows[k]

        return expired
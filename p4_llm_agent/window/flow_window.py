class FlowWindow:
    def __init__(self, size):
        self.size = size
        self.flows = []

    def add(self, flow):
        self.flows.append(flow)

    def is_full(self):
        return len(self.flows) >= self.size

    def flush(self):
        data = self.flows.copy()
        self.flows.clear()
        return data
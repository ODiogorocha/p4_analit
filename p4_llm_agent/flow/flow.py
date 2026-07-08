import time


class Flow:

    def __init__(self, key):

        self.key = key

        self.packets = 0
        self.bytes = 0

        self.latency_sum = 0
        self.queue_sum = 0
        self.samples = 0

        self.first_seen = time.time()
        self.last_seen = time.time()

    def update(self, f):

        self.packets += f["packets"]
        self.bytes += f["bytes"]

        self.latency_sum += f["latency"]
        self.queue_sum += f["queue_depth"]

        self.samples += 1
        self.last_seen = time.time()

    def age(self):

        return time.time() - self.first_seen
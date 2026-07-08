import time


class Metrics:

    def start(self):
        return time.time()

    def end(self, t):
        return time.time() - t
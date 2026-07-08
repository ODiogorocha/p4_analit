class FeatureExtractor:

    def extract(self, f):

        d = f.duration()

        return {

            "protocol": f.key[4],
            "src_port": f.key[2],
            "dst_port": f.key[3],

            "packets": f.packets,
            "bytes": f.bytes,

            "duration": d,

            "pps": f.packets / d if d > 0 else 0,
            "bps": f.bytes / d if d > 0 else 0,

            "latency": f.latency_sum / max(f.samples, 1),
            "queue": f.queue_sum / max(f.samples, 1)
        }
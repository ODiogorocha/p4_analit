class Decoder:

    def decode(self, msg):

        return {

            "src_ip": msg.get("src_ip"),
            "dst_ip": msg.get("dst_ip"),
            "src_port": msg.get("src_port"),
            "dst_port": msg.get("dst_port"),
            "protocol": msg.get("protocol", "TCP"),

            "packets": msg.get("packets", 1),
            "bytes": msg.get("bytes", 0),

            "duration": msg.get("duration", 1),
            "latency": msg.get("latency", 0),
            "queue_depth": msg.get("queue_depth", 0)
        }
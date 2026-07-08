from models.flow import Flow


class FlowTable:

    def __init__(self):

        self.flows = {}

    def _create_key(self, telemetry):

        return (
            telemetry["src_ip"],
            telemetry["dst_ip"],
            telemetry["src_port"],
            telemetry["dst_port"],
            telemetry["protocol"]
        )

    def add_packet(self, telemetry):

        key = self._create_key(telemetry)

        if key not in self.flows:

            self.flows[key] = Flow(
                telemetry["src_ip"],
                telemetry["dst_ip"],
                telemetry["src_port"],
                telemetry["dst_port"],
                telemetry["protocol"]
            )

        self.flows[key].update(
            packets=telemetry["packets"],
            bytes_count=telemetry["bytes"],
            latency=telemetry["latency"],
            queue_depth=telemetry["queue_depth"]
        )

    def get_expired_flows(self, window_time):

        expired = []

        keys_to_remove = []

        for key, flow in self.flows.items():

            if flow.duration >= window_time:

                expired.append(flow)

                keys_to_remove.append(key)

        for key in keys_to_remove:

            del self.flows[key]

        return expired

    def total_flows(self):

        return len(self.flows)
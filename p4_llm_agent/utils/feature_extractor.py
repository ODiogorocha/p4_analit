def extract_features(flow):

    duration = max(flow["duration"], 1)

    return {
        "protocol": flow["protocol"],
        "destination_port": flow["dst_port"],
        "packets": flow["packets"],
        "bytes": flow["bytes"],
        "duration": duration,
        "packets_per_second": flow["packets"] / duration,
        "bytes_per_second": flow["bytes"] / duration,
        "average_packet_size": flow["bytes"] / flow["packets"],
        "latency": flow["latency"],
        "queue_depth": flow["queue_depth"]
    }
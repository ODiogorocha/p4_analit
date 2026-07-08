from dataclasses import dataclass

@dataclass
class Flow:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str

    packets: int = 0
    bytes: int = 0
    duration: float = 0.0
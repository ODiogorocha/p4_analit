#include <core.p4>
#include <v1model.p4>

/* ── Headers ── */
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

struct metadata { }

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

/* ── Registradores ── */
register<bit<64>>(1024) byte_cnt;
register<bit<64>>(1024) pkt_cnt;

/* ── Parser ── */
parser MyParser(packet_in pkt, out headers hdr,
                inout metadata meta, inout standard_metadata_t std_meta) {
    state start {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;
            default: accept;
        }
    }
    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition accept;
    }
}

/* ── Ingress ── */
control MyIngress(inout headers hdr, inout metadata meta,
                  inout standard_metadata_t std_meta) {

    action forward(bit<9> port) {
        std_meta.egress_spec = port;
    }

    apply {
        if (hdr.ipv4.isValid()) {

            bit<10> index = (bit<10>)hdr.ipv4.srcAddr;

            bit<64> tmp_bytes;
            bit<64> tmp_pkts;

            byte_cnt.read(tmp_bytes, (bit<32>)index);
            pkt_cnt.read(tmp_pkts,  (bit<32>)index);

            byte_cnt.write((bit<32>)index, tmp_bytes + (bit<64>)hdr.ipv4.totalLen);
            pkt_cnt.write((bit<32>)index,  tmp_pkts + 1);

            // 🔥 forwarding simples (essencial)
            if (std_meta.ingress_port == 1) {
                forward(2);
            } else {
                forward(1);
            }
        }
    }
}

/* ── Deparser ── */
control MyDeparser(packet_out pkt, in headers hdr) {
    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.ipv4);
    }
}

V1Switch(MyParser(), NoAction(), MyIngress(),
         NoAction(), NoAction(), MyDeparser()) main;
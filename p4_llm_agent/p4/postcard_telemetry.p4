#include <core.p4>
#include <v1model.p4>

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header telemetry_t {
    bit<32> src_ip;
    bit<32> dst_ip;
    bit<16> src_port;
    bit<16> dst_port;
    bit<32> packets;
    bit<32> bytes;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t ipv4;
    telemetry_t telemetry;
}

struct metadata { }

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t sm) {

    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t sm) {

    action send_telemetry() {

        hdr.telemetry.setValid();

        hdr.telemetry.src_ip = hdr.ipv4.srcAddr;
        hdr.telemetry.dst_ip = hdr.ipv4.dstAddr;

        hdr.telemetry.src_port = (bit<16>) sm.ingress_port;
        hdr.telemetry.dst_port = (bit<16>) sm.egress_spec;

        hdr.telemetry.packets = 1;
        hdr.telemetry.bytes = sm.packet_length;
    }

    table telemetry_table {
        actions = {
            send_telemetry;
            NoAction;
        }
        size = 1;
        default_action = send_telemetry();
    }

    apply {
        telemetry_table.apply();
    }
}

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t sm) {
    apply { }
}

control MyDeparser(packet_out packet,
                   in headers hdr) {

    apply {
        packet.emit(hdr.ethernet);

        if (hdr.telemetry.isValid()) {
            packet.emit(hdr.telemetry);
        }
    }
}

V1Switch(
    MyParser(),
    MyIngress(),
    MyEgress(),
    MyDeparser()
) main;
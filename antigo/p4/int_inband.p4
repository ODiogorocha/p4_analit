/* ============================================================
 * INT In-Band Telemetria — BMv2 / P4_16
 * Cada switch injeta metadados no próprio pacote.
 * O pacote cresce a cada hop; o coletor lê o stack no destino.
 * ============================================================ */

#include <core.p4>
#include <v1model.p4>

/* ── Constantes ────────────────────────────────────────────── */
const bit<16> TYPE_IPV4    = 0x0800;
const bit<8>  PROTO_UDP    = 0x11;
const bit<16> INT_SHIM_DST = 9555;   // porta UDP que marca pacotes INT
const bit<8>  INT_MAX_HOP  = 8;

/* ── Cabeçalhos ─────────────────────────────────────────────── */
header ethernet_t {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> total_len;
    bit<16> identification;
    bit<3>  flags;
    bit<13> frag_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdr_checksum;
    bit<32> src_addr;
    bit<32> dst_addr;
}

header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length;
    bit<16> checksum;
}

/* Shim INT — inserido logo após UDP */
header int_shim_t {
    bit<8>  int_type;       // 1 = hop-by-hop
    bit<8>  rsvd;
    bit<8>  length;         // comprimento do bloco INT em palavras de 4B
    bit<8>  next_proto;     // protocolo original após INT
}

/* Cabeçalho de controle INT */
header int_header_t {
    bit<4>  ver;
    bit<4>  rep;
    bit<1>  c;              // copy bit
    bit<1>  e;              // max hop exceeded
    bit<1>  m;              // MTU exceeded
    bit<5>  rsvd1;
    bit<3>  rsvd2;
    bit<5>  hop_metadata_len; // palavras de 4B por hop
    bit<8>  remaining_hop_cnt;
    bit<16> instruction_mask; // quais campos coletar
    bit<16> domain_specific;
}

/* Metadados de um único hop — cada switch empilha um destes */
header int_hop_info_t {
    bit<32> switch_id;
    bit<32> ingress_port;
    bit<32> egress_port;
    bit<32> ingress_tstamp;   // µs
    bit<32> egress_tstamp;    // µs
    bit<32> queue_occupancy;  // bytes na fila
    bit<32> queue_congestion; // marcação ECN
    bit<32> egress_port_tx_utilization;
}

/* Stack de até INT_MAX_HOP hops */
#define INT_HOP_STACK \
    header int_hop_info_t int_hop_0; \
    header int_hop_info_t int_hop_1; \
    header int_hop_info_t int_hop_2; \
    header int_hop_info_t int_hop_3; \
    header int_hop_info_t int_hop_4; \
    header int_hop_info_t int_hop_5; \
    header int_hop_info_t int_hop_6; \
    header int_hop_info_t int_hop_7;

struct headers {
    ethernet_t    ethernet;
    ipv4_t        ipv4;
    udp_t         udp;
    int_shim_t    int_shim;
    int_header_t  int_header;
    INT_HOP_STACK
}

struct metadata {
    bit<1>  is_int;
    bit<32> switch_id;
    bit<8>  hop_count;
    bit<32> ingress_tstamp;
    bit<32> queue_depth;
}

/* ── Parser ─────────────────────────────────────────────────── */
parser MyParser(packet_in pkt,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t std_meta) {

    state start { transition parse_ethernet; }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            TYPE_IPV4: parse_ipv4;
            default:   accept;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            PROTO_UDP: parse_udp;
            default:   accept;
        }
    }

    state parse_udp {
        pkt.extract(hdr.udp);
        transition select(hdr.udp.dst_port) {
            INT_SHIM_DST: parse_int_shim;
            default:      accept;
        }
    }

    state parse_int_shim {
        pkt.extract(hdr.int_shim);
        pkt.extract(hdr.int_header);
        meta.is_int    = 1;
        meta.hop_count = INT_MAX_HOP - hdr.int_header.remaining_hop_cnt;
        transition parse_int_hops;
    }

    /* Parseia hops já presentes no pacote */
    state parse_int_hops {
        transition select(meta.hop_count) {
            0:       accept;
            default: parse_hop_0;
        }
    }
    state parse_hop_0 { pkt.extract(hdr.int_hop_0); transition select(meta.hop_count) { 1: accept; default: parse_hop_1; } }
    state parse_hop_1 { pkt.extract(hdr.int_hop_1); transition select(meta.hop_count) { 2: accept; default: parse_hop_2; } }
    state parse_hop_2 { pkt.extract(hdr.int_hop_2); transition select(meta.hop_count) { 3: accept; default: parse_hop_3; } }
    state parse_hop_3 { pkt.extract(hdr.int_hop_3); transition select(meta.hop_count) { 4: accept; default: parse_hop_4; } }
    state parse_hop_4 { pkt.extract(hdr.int_hop_4); transition select(meta.hop_count) { 5: accept; default: parse_hop_5; } }
    state parse_hop_5 { pkt.extract(hdr.int_hop_5); transition select(meta.hop_count) { 6: accept; default: parse_hop_6; } }
    state parse_hop_6 { pkt.extract(hdr.int_hop_6); transition select(meta.hop_count) { 7: accept; default: parse_hop_7; } }
    state parse_hop_7 { pkt.extract(hdr.int_hop_7); transition accept; }
}

/* ── Checksum Verification ──────────────────────────────────── */
control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {}
}

/* ── Ingress ────────────────────────────────────────────────── */
control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t std_meta) {

    action drop() { mark_to_drop(std_meta); }

    action ipv4_forward(bit<9> port) {
        std_meta.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* Inicializa cabeçalhos INT se o pacote ainda não tiver */
    action int_source_init(bit<32> sw_id) {
        meta.switch_id = sw_id;
        hdr.int_shim.setValid();
        hdr.int_shim.int_type    = 1;
        hdr.int_shim.length      = 3;   // shim(1) + ctrl(2) palavras
        hdr.int_shim.next_proto  = hdr.udp.dst_port[7:0];

        hdr.int_header.setValid();
        hdr.int_header.ver              = 0;
        hdr.int_header.rep              = 0;
        hdr.int_header.c                = 0;
        hdr.int_header.e                = 0;
        hdr.int_header.m                = 0;
        hdr.int_header.hop_metadata_len = 8; // 8 palavras de 4B por hop
        hdr.int_header.remaining_hop_cnt = INT_MAX_HOP;
        hdr.int_header.instruction_mask = 0xFF00; // todos os campos
        meta.is_int = 1;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 12;
        hdr.udp.length     = hdr.udp.length + 12;
    }

    action int_transit(bit<32> sw_id) {
        meta.switch_id = sw_id;
    }

    table ipv4_lpm {
        key   = { hdr.ipv4.dst_addr: lpm; }
        actions = { ipv4_forward; drop; NoAction; }
        default_action = drop();
    }

    table int_source {
        key   = { hdr.udp.dst_port: exact; }
        actions = { int_source_init; NoAction; }
        default_action = NoAction();
    }

    table int_transit_config {
        key   = { std_meta.ingress_port: exact; }
        actions = { int_transit; NoAction; }
        default_action = int_transit(1);
    }

    apply {
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
        }
        if (hdr.udp.isValid()) {
            int_source.apply();
        }
        if (meta.is_int == 1) {
            int_transit_config.apply();
            meta.ingress_tstamp = (bit<32>)std_meta.ingress_global_timestamp;
            meta.queue_depth    = (bit<32>)std_meta.deq_qdepth;
        }
    }
}

/* ── Egress ─────────────────────────────────────────────────── */
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t std_meta) {

    /* Empilha metadados do hop atual no slot correto */
    action add_hop_metadata() {
        hdr.int_header.remaining_hop_cnt = hdr.int_header.remaining_hop_cnt - 1;
        hdr.int_shim.length = hdr.int_shim.length + 8; // +8 palavras (32B)

        /* Seleciona slot pelo número de hops já registrados */
        bit<8> used = INT_MAX_HOP - hdr.int_header.remaining_hop_cnt - 1;

        // Escreve no slot correspondente
        // (BMv2 não suporta arrays de headers; usamos cascata)
        if (used == 0) {
            hdr.int_hop_0.setValid();
            hdr.int_hop_0.switch_id    = meta.switch_id;
            hdr.int_hop_0.ingress_port = (bit<32>)std_meta.ingress_port;
            hdr.int_hop_0.egress_port  = (bit<32>)std_meta.egress_port;
            hdr.int_hop_0.ingress_tstamp = meta.ingress_tstamp;
            hdr.int_hop_0.egress_tstamp  = (bit<32>)std_meta.egress_global_timestamp;
            hdr.int_hop_0.queue_occupancy = (bit<32>)std_meta.deq_qdepth;
            hdr.int_hop_0.queue_congestion = 0;
            hdr.int_hop_0.egress_port_tx_utilization = 0;
        } else if (used == 1) {
            hdr.int_hop_1.setValid();
            hdr.int_hop_1.switch_id    = meta.switch_id;
            hdr.int_hop_1.ingress_port = (bit<32>)std_meta.ingress_port;
            hdr.int_hop_1.egress_port  = (bit<32>)std_meta.egress_port;
            hdr.int_hop_1.ingress_tstamp = meta.ingress_tstamp;
            hdr.int_hop_1.egress_tstamp  = (bit<32>)std_meta.egress_global_timestamp;
            hdr.int_hop_1.queue_occupancy = (bit<32>)std_meta.deq_qdepth;
            hdr.int_hop_1.queue_congestion = 0;
            hdr.int_hop_1.egress_port_tx_utilization = 0;
        } else if (used == 2) {
            hdr.int_hop_2.setValid();
            hdr.int_hop_2.switch_id    = meta.switch_id;
            hdr.int_hop_2.ingress_port = (bit<32>)std_meta.ingress_port;
            hdr.int_hop_2.egress_port  = (bit<32>)std_meta.egress_port;
            hdr.int_hop_2.ingress_tstamp = meta.ingress_tstamp;
            hdr.int_hop_2.egress_tstamp  = (bit<32>)std_meta.egress_global_timestamp;
            hdr.int_hop_2.queue_occupancy = (bit<32>)std_meta.deq_qdepth;
            hdr.int_hop_2.queue_congestion = 0;
            hdr.int_hop_2.egress_port_tx_utilization = 0;
        }
        // ... adicione mais slots conforme INT_MAX_HOP

        hdr.ipv4.total_len = hdr.ipv4.total_len + 32;
        hdr.udp.length     = hdr.udp.length + 32;
    }

    apply {
        if (meta.is_int == 1 && hdr.int_header.remaining_hop_cnt > 0) {
            add_hop_metadata();
        }
    }
}

/* ── Checksum Update ────────────────────────────────────────── */
control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.total_len, hdr.ipv4.identification, hdr.ipv4.flags,
              hdr.ipv4.frag_offset, hdr.ipv4.ttl, hdr.ipv4.protocol,
              hdr.ipv4.src_addr, hdr.ipv4.dst_addr },
            hdr.ipv4.hdr_checksum, HashAlgorithm.csum16);
    }
}

/* ── Deparser ───────────────────────────────────────────────── */
control MyDeparser(packet_out pkt, in headers hdr) {
    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.ipv4);
        pkt.emit(hdr.udp);
        pkt.emit(hdr.int_shim);
        pkt.emit(hdr.int_header);
        pkt.emit(hdr.int_hop_0);
        pkt.emit(hdr.int_hop_1);
        pkt.emit(hdr.int_hop_2);
        pkt.emit(hdr.int_hop_3);
        pkt.emit(hdr.int_hop_4);
        pkt.emit(hdr.int_hop_5);
        pkt.emit(hdr.int_hop_6);
        pkt.emit(hdr.int_hop_7);
    }
}

/* ── Pipeline ───────────────────────────────────────────────── */
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
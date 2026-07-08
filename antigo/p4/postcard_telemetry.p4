/* ============================================================
 * Postcard Telemetria — BMv2 / P4_16
 * O switch NÃO modifica o pacote original.
 * Ele cria um "postcard" (pequeno relatório UDP) e envia
 * ao coletor de telemetria em paralelo.
 * ============================================================ */

#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4       = 0x0800;
const bit<8>  PROTO_UDP       = 0x11;
const bit<8>  PROTO_TCP       = 0x06;
const bit<32> COLLECTOR_IP    = 0x0a000101; // 10.0.1.1 — ajuste
const bit<16> COLLECTOR_PORT  = 9556;
const bit<9>  COLLECTOR_EGRESS = 1;         // porta local para o coletor

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

header tcp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<32> seq_no;
    bit<32> ack_no;
    bit<4>  data_offset;
    bit<4>  res;
    bit<8>  flags;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgent_ptr;
}

/* Postcard: payload do pacote de relatório enviado ao coletor */
header postcard_t {
    bit<32> switch_id;
    bit<32> seq_num;          // número de sequência do postcard
    bit<32> flow_src_ip;      // IP de origem do fluxo monitorado
    bit<32> flow_dst_ip;
    bit<16> flow_src_port;
    bit<16> flow_dst_port;
    bit<8>  flow_protocol;
    bit<8>  rsvd;
    bit<16> ingress_port;
    bit<16> egress_port;
    bit<32> ingress_tstamp;   // µs
    bit<32> egress_tstamp;
    bit<32> queue_depth;      // pacotes na fila de egresso
    bit<32> queue_latency;    // tempo na fila (ns)
    bit<32> pkt_length;
    bit<32> drop_count;       // drops acumulados nesta porta
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    udp_t      udp;
    tcp_t      tcp;
    /* Cabeçalhos do postcard clonado */
    ethernet_t postcard_eth;
    ipv4_t     postcard_ip;
    udp_t      postcard_udp;
    postcard_t postcard;
}

struct metadata {
    bit<1>  do_postcard;
    bit<32> flow_src_ip;
    bit<32> flow_dst_ip;
    bit<16> flow_src_port;
    bit<16> flow_dst_port;
    bit<8>  flow_proto;
    bit<32> switch_id;
    bit<32> ingress_tstamp;
    bit<32> queue_depth;
    bit<32> queue_latency;
    bit<32> seq_num;
}

/* ── Registradores ──────────────────────────────────────────── */
// Contador de sequência por porta de egresso
register<bit<32>>(512) postcard_seq_counter;
// Contagem de drops por porta
register<bit<32>>(512) drop_counter;

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
            PROTO_TCP: parse_tcp;
            default:   accept;
        }
    }

    state parse_udp {
        pkt.extract(hdr.udp);
        transition accept;
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) { apply {} }

/* ── Ingress ────────────────────────────────────────────────── */
control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t std_meta) {

    action drop() { mark_to_drop(std_meta); }

    action ipv4_forward(bit<9> port) {
        std_meta.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* Marca o fluxo para gerar postcard */
    action enable_postcard(bit<32> sw_id) {
        meta.do_postcard  = 1;
        meta.switch_id    = sw_id;
        meta.flow_src_ip  = hdr.ipv4.src_addr;
        meta.flow_dst_ip  = hdr.ipv4.dst_addr;
        meta.flow_proto   = hdr.ipv4.protocol;
        meta.ingress_tstamp = (bit<32>)std_meta.ingress_global_timestamp;

        if (hdr.udp.isValid()) {
            meta.flow_src_port = hdr.udp.src_port;
            meta.flow_dst_port = hdr.udp.dst_port;
        } else if (hdr.tcp.isValid()) {
            meta.flow_src_port = hdr.tcp.src_port;
            meta.flow_dst_port = hdr.tcp.dst_port;
        }
    }

    table ipv4_lpm {
        key   = { hdr.ipv4.dst_addr: lpm; }
        actions = { ipv4_forward; drop; NoAction; }
        default_action = drop();
    }

    /* Tabela que define quais fluxos monitorar (5-tupla) */
    table postcard_policy {
        key = {
            hdr.ipv4.src_addr:   ternary;
            hdr.ipv4.dst_addr:   ternary;
            hdr.ipv4.protocol:   ternary;
        }
        actions = { enable_postcard; NoAction; }
        default_action = NoAction();
        size = 256;
    }

    apply {
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
            postcard_policy.apply();
        }
    }
}

/* ── Egress ─────────────────────────────────────────────────── */
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t std_meta) {

    action build_and_send_postcard() {
        /* Lê e incrementa sequência */
        bit<32> seq;
        postcard_seq_counter.read(seq, (bit<32>)std_meta.egress_port);
        seq = seq + 1;
        postcard_seq_counter.write((bit<32>)std_meta.egress_port, seq);
        meta.seq_num = seq;

        /* Clona pacote para porta do coletor (PRE) */
        // Na prática: clone3(CloneType.E2E, 100, meta);
        // Aqui construímos o postcard no pacote clonado via multicast/clone
        // Veja collector/postcard_collector.py para recepção

        /* Captura métricas de fila */
        meta.queue_depth   = (bit<32>)std_meta.deq_qdepth;
        meta.queue_latency = (bit<32>)std_meta.deq_timedelta; // ns
    }

    apply {
        if (meta.do_postcard == 1) {
            build_and_send_postcard();
            // clone3 seria chamado aqui; em BMv2 usa-se primitiva clone_egress_pkt_to_egress
        }
    }
}

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

control MyDeparser(packet_out pkt, in headers hdr) {
    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.ipv4);
        pkt.emit(hdr.udp);
        pkt.emit(hdr.tcp);
    }
}

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
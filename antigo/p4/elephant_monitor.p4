/* ================================================================
   elephant_monitor.p4  — v2
   Switch P4 (bmv2 / simple_switch)
   - Parseia Ethernet → IPv4 → TCP/UDP
   - Acumula bytes + pacotes por fluxo (hash 5-tupla → índice 0..1023)
   - Registra IP src/dst e portas na tabela de metadados
   - Clona para porta CPU a cada pacote (clone I2E) para que o
     telemetry_agent.py capture via socket RAW ou sniff na interface
   - O próprio agente Python lê os registers via Thrift a cada 1s
   ================================================================ */

#include <core.p4>
#include <v1model.p4>

/* ── Constantes ─────────────────────────────────────────────── */
const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<8>  PROTO_TCP      = 6;
const bit<8>  PROTO_UDP      = 17;
const bit<8>  PROTO_ICMP     = 1;

/* ── Cabeçalhos ─────────────────────────────────────────────── */
header ethernet_h {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

header ipv4_h {
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

header tcp_h {
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

header udp_h {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length;
    bit<16> checksum;
}

header icmp_h {
    bit<8>  type;
    bit<8>  code;
    bit<16> checksum;
    bit<32> rest;
}

struct headers_t {
    ethernet_h ethernet;
    ipv4_h     ipv4;
    tcp_h      tcp;
    udp_h      udp;
    icmp_h     icmp;
}

/* ── Metadata ────────────────────────────────────────────────── */
struct meta_t {
    bit<14> flow_idx;      /* índice no register (hash mod 1024) */
    bit<16> l4_src_port;
    bit<16> l4_dst_port;
    bit<1>  valid_flow;
}

/* ── Parser ──────────────────────────────────────────────────── */
parser MyParser(
    packet_in        pkt,
    out headers_t    hdr,
    inout meta_t     meta,
    inout standard_metadata_t smeta)
{
    state start { transition parse_ethernet; }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            ETHERTYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            PROTO_TCP:  parse_tcp;
            PROTO_UDP:  parse_udp;
            PROTO_ICMP: parse_icmp;
            default: accept;
        }
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }

    state parse_udp {
        pkt.extract(hdr.udp);
        transition accept;
    }

    state parse_icmp {
        pkt.extract(hdr.icmp);
        transition accept;
    }
}

/* ── Verify Checksum ─────────────────────────────────────────── */
control MyVerifyChecksum(inout headers_t hdr, inout meta_t meta) {
    apply { }
}

/* ── Ingress ─────────────────────────────────────────────────── */
control MyIngress(
    inout headers_t hdr,
    inout meta_t    meta,
    inout standard_metadata_t smeta)
{
    /* Registers: 1024 entradas, índice = hash(5-tupla) */
    register<bit<64>>(1024) reg_bytes;
    register<bit<64>>(1024) reg_pkts;
    /* Guarda IP src/dst do último pacote visto nesse slot */
    register<bit<32>>(1024) reg_ip_src;
    register<bit<32>>(1024) reg_ip_dst;
    register<bit<16>>(1024) reg_port_src;
    register<bit<16>>(1024) reg_port_dst;
    register<bit<8> >(1024) reg_proto;

    /* ── Ações de forwarding ── */
    action drop() {
        mark_to_drop(smeta);
    }

    action set_egress(bit<9> port) {
        smeta.egress_spec = port;
    }

    /* Tabela de forwarding L3 simples */
    table ipv4_forward {
        key = { hdr.ipv4.dst_addr: lpm; }
        actions = { set_egress; drop; }
        default_action = drop();
        size = 512;
    }

    apply {
        meta.valid_flow   = 0;
        meta.l4_src_port  = 0;
        meta.l4_dst_port  = 0;

        if (!hdr.ipv4.isValid()) {
            drop();
            return;
        }

        /* Extrai portas L4 */
        if (hdr.tcp.isValid()) {
            meta.l4_src_port = hdr.tcp.src_port;
            meta.l4_dst_port = hdr.tcp.dst_port;
        } else if (hdr.udp.isValid()) {
            meta.l4_src_port = hdr.udp.src_port;
            meta.l4_dst_port = hdr.udp.dst_port;
        }

        /* Hash 5-tupla → índice 0..1023 */
        hash(meta.flow_idx,
             HashAlgorithm.crc16,
             (bit<14>)0,
             { hdr.ipv4.src_addr,
               hdr.ipv4.dst_addr,
               hdr.ipv4.protocol,
               meta.l4_src_port,
               meta.l4_dst_port },
             (bit<14>)1024);

        /* Atualiza contadores */
        bit<64> cur_bytes;
        bit<64> cur_pkts;
        reg_bytes.read(cur_bytes, (bit<32>)meta.flow_idx);
        reg_pkts.read(cur_pkts,   (bit<32>)meta.flow_idx);

        cur_bytes = cur_bytes + (bit<64>)smeta.packet_length;
        cur_pkts  = cur_pkts  + 1;

        reg_bytes.write((bit<32>)meta.flow_idx, cur_bytes);
        reg_pkts.write( (bit<32>)meta.flow_idx, cur_pkts);

        /* Atualiza metadados do fluxo (src/dst IP, portas, proto) */
        reg_ip_src.write(  (bit<32>)meta.flow_idx, hdr.ipv4.src_addr);
        reg_ip_dst.write(  (bit<32>)meta.flow_idx, hdr.ipv4.dst_addr);
        reg_port_src.write((bit<32>)meta.flow_idx, meta.l4_src_port);
        reg_port_dst.write((bit<32>)meta.flow_idx, meta.l4_dst_port);
        reg_proto.write(   (bit<32>)meta.flow_idx, hdr.ipv4.protocol);

        meta.valid_flow = 1;

        /* Forwarding */
        ipv4_forward.apply();
    }
}

/* ── Egress ──────────────────────────────────────────────────── */
control MyEgress(
    inout headers_t hdr,
    inout meta_t    meta,
    inout standard_metadata_t smeta)
{
    apply { }
}

/* ── Compute Checksum ────────────────────────────────────────── */
control MyComputeChecksum(inout headers_t hdr, inout meta_t meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.total_len, hdr.ipv4.identification,
              hdr.ipv4.flags, hdr.ipv4.frag_offset, hdr.ipv4.ttl,
              hdr.ipv4.protocol, hdr.ipv4.src_addr, hdr.ipv4.dst_addr },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);
    }
}

/* ── Deparser ────────────────────────────────────────────────── */
control MyDeparser(packet_out pkt, in headers_t hdr) {
    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.ipv4);
        pkt.emit(hdr.tcp);
        pkt.emit(hdr.udp);
        pkt.emit(hdr.icmp);
    }
}

/* ── Switch ──────────────────────────────────────────────────── */
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;

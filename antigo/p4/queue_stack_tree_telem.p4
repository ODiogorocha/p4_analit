/* ============================================================
 * Telemetria com Estruturas de Dados — BMv2 / P4_16
 *
 * Demonstra três modelos de coleta:
 *   1. FILA   — medição FIFO de latência por porta
 *   2. PILHA  — stack de eventos de congestionamento
 *   3. ÁRVORE — bitmap de caminho (PathID) + métricas por nó
 * ============================================================ */

#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4  = 0x0800;
const bit<8>  PROTO_UDP  = 0x11;
const bit<8>  PROTO_TCP  = 0x06;

/* ── Parâmetros da topologia em árvore ──────────────────────── */
// Cada switch recebe um ID de nível (0 = raiz, 1 = intermediário, 2 = folha)
// O PathID é construído hop-a-hop como um bitmap de 32 bits.

/* ── Cabeçalhos base ────────────────────────────────────────── */
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

/* ── Cabeçalho de controle de telemetria ────────────────────── */
// Modo: 1=FILA, 2=PILHA, 3=ÁRVORE
header telem_ctrl_t {
    bit<8>  mode;
    bit<8>  hop_count;
    bit<16> flags;
    bit<32> path_id;      // usado no modo ÁRVORE
    bit<32> stack_depth;  // usado no modo PILHA
}

/* ── 1. FILA: cabeçalho de medição por fila ─────────────────── */
// Um registro por porta monitorada, carregado no pacote
header queue_record_t {
    bit<16> port_id;
    bit<32> enqueue_ts;    // timestamp de entrada na fila (µs)
    bit<32> dequeue_ts;    // timestamp de saída da fila
    bit<32> queue_depth;   // profundidade no momento do enqueue
    bit<32> sojourn_time;  // tempo de permanência calculado (ns)
    bit<16> drop_prob;     // probabilidade de drop AQM (0-65535)
    bit<16> rsvd;
}

/* ── 2. PILHA: evento de congestionamento ────────────────────── */
// LIFO — o switch empilha no TOPO quando detecta congestionamento
header stack_event_t {
    bit<32> switch_id;
    bit<32> timestamp;     // quando o evento ocorreu
    bit<16> port_id;
    bit<16> event_type;    // 1=fila cheia, 2=ECN, 3=drop, 4=burst
    bit<32> queue_depth;   // profundidade no evento
    bit<32> burst_size;    // tamanho do burst detectado (bytes)
    bit<8>  severity;      // 0-255
    bit<8>  rsvd;
    bit<16> rsvd2;
}

/* ── 3. ÁRVORE: nó de caminho ────────────────────────────────── */
// Cada switch (nó da árvore) adiciona um registro com posição na árvore
header tree_node_t {
    bit<32> switch_id;
    bit<8>  tree_level;    // 0=raiz, 1=intermediário, 2=folha
    bit<8>  child_index;   // índice do filho neste nível
    bit<16> rsvd;
    bit<32> path_bit;      // bit contribuído ao PathID global
    bit<32> ingress_port;
    bit<32> egress_port;
    bit<32> link_latency;  // latência estimada do enlace (µs)
    bit<32> bandwidth_used;// bw utilizado (Kbps)
    bit<32> timestamp;
}

/* Pilha de até 4 eventos e 4 nós de árvore */
struct headers {
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    udp_t        udp;
    tcp_t        tcp;
    telem_ctrl_t telem_ctrl;
    /* FILA */
    queue_record_t queue_rec_0;
    queue_record_t queue_rec_1;
    queue_record_t queue_rec_2;
    queue_record_t queue_rec_3;
    /* PILHA */
    stack_event_t  stack_top;
    stack_event_t  stack_1;
    stack_event_t  stack_2;
    stack_event_t  stack_3;
    /* ÁRVORE */
    tree_node_t    tree_node_0;
    tree_node_t    tree_node_1;
    tree_node_t    tree_node_2;
    tree_node_t    tree_node_3;
}

struct metadata {
    bit<8>  telem_mode;
    bit<32> switch_id;
    bit<8>  tree_level;
    bit<8>  child_index;
    bit<32> ingress_tstamp;
    bit<32> queue_depth;
    bit<32> queue_latency;
    bit<1>  congestion_detected;
    bit<16> event_type;
    bit<32> burst_bytes;
}

/* ── Registradores ──────────────────────────────────────────── */
// Histograma de latência de fila por porta (16 buckets de 100µs)
register<bit<32>>(16 * 512) queue_latency_histogram;
// Profundidade média de fila por porta (EWMA)
register<bit<32>>(512)      avg_queue_depth;
// Pilha global de eventos (circular, 1024 slots)
register<bit<32>>(1024)     event_stack_sw_id;
register<bit<32>>(1024)     event_stack_ts;
register<bit<32>>(1024)     event_stack_type;
register<bit<32>>(1)        event_stack_ptr;   // ponteiro de topo
// PathID acumulado na árvore
register<bit<32>>(1024)     path_id_table;     // chave = hash do fluxo

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
        transition try_telem;
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition try_telem;
    }

    state try_telem {
        transition select(hdr.ipv4.diffserv[2:0]) {
            1:       parse_telem_queue;
            2:       parse_telem_stack;
            3:       parse_telem_tree;
            default: accept;
        }
    }

    /* Parseia registros de fila existentes */
    state parse_telem_queue {
        pkt.extract(hdr.telem_ctrl);
        meta.telem_mode = 1;
        transition select(hdr.telem_ctrl.hop_count) {
            0:       accept;
            default: parse_queue_0;
        }
    }
    state parse_queue_0 { pkt.extract(hdr.queue_rec_0); transition select(hdr.telem_ctrl.hop_count) { 1: accept; default: parse_queue_1; } }
    state parse_queue_1 { pkt.extract(hdr.queue_rec_1); transition select(hdr.telem_ctrl.hop_count) { 2: accept; default: parse_queue_2; } }
    state parse_queue_2 { pkt.extract(hdr.queue_rec_2); transition select(hdr.telem_ctrl.hop_count) { 3: accept; default: parse_queue_3; } }
    state parse_queue_3 { pkt.extract(hdr.queue_rec_3); transition accept; }

    /* Parseia pilha de eventos */
    state parse_telem_stack {
        pkt.extract(hdr.telem_ctrl);
        meta.telem_mode = 2;
        transition select(hdr.telem_ctrl.stack_depth) {
            0:       accept;
            default: parse_stack_top;
        }
    }
    state parse_stack_top { pkt.extract(hdr.stack_top); transition select(hdr.telem_ctrl.stack_depth) { 1: accept; default: parse_stack_1; } }
    state parse_stack_1   { pkt.extract(hdr.stack_1);   transition select(hdr.telem_ctrl.stack_depth) { 2: accept; default: parse_stack_2; } }
    state parse_stack_2   { pkt.extract(hdr.stack_2);   transition select(hdr.telem_ctrl.stack_depth) { 3: accept; default: parse_stack_3; } }
    state parse_stack_3   { pkt.extract(hdr.stack_3);   transition accept; }

    /* Parseia nós de árvore */
    state parse_telem_tree {
        pkt.extract(hdr.telem_ctrl);
        meta.telem_mode = 3;
        transition select(hdr.telem_ctrl.hop_count) {
            0:       accept;
            default: parse_tree_0;
        }
    }
    state parse_tree_0 { pkt.extract(hdr.tree_node_0); transition select(hdr.telem_ctrl.hop_count) { 1: accept; default: parse_tree_1; } }
    state parse_tree_1 { pkt.extract(hdr.tree_node_1); transition select(hdr.telem_ctrl.hop_count) { 2: accept; default: parse_tree_2; } }
    state parse_tree_2 { pkt.extract(hdr.tree_node_2); transition select(hdr.telem_ctrl.hop_count) { 3: accept; default: parse_tree_3; } }
    state parse_tree_3 { pkt.extract(hdr.tree_node_3); transition accept; }
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

    action set_switch_config(bit<32> sw_id, bit<8> level, bit<8> child_idx) {
        meta.switch_id    = sw_id;
        meta.tree_level   = level;
        meta.child_index  = child_idx;
    }

    action init_queue_telem() {
        hdr.telem_ctrl.setValid();
        hdr.telem_ctrl.mode      = 1;
        hdr.telem_ctrl.hop_count = 0;
        hdr.telem_ctrl.flags     = 0;
        hdr.telem_ctrl.path_id   = 0;
        hdr.telem_ctrl.stack_depth = 0;
        meta.telem_mode = 1;
        hdr.ipv4.diffserv = hdr.ipv4.diffserv | 0x01;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 16;
    }

    action init_stack_telem() {
        hdr.telem_ctrl.setValid();
        hdr.telem_ctrl.mode        = 2;
        hdr.telem_ctrl.hop_count   = 0;
        hdr.telem_ctrl.stack_depth = 0;
        hdr.telem_ctrl.flags       = 0;
        hdr.telem_ctrl.path_id     = 0;
        meta.telem_mode = 2;
        hdr.ipv4.diffserv = hdr.ipv4.diffserv | 0x02;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 16;
    }

    action init_tree_telem() {
        hdr.telem_ctrl.setValid();
        hdr.telem_ctrl.mode      = 3;
        hdr.telem_ctrl.hop_count = 0;
        hdr.telem_ctrl.path_id   = 0;
        hdr.telem_ctrl.flags     = 0;
        hdr.telem_ctrl.stack_depth = 0;
        meta.telem_mode = 3;
        hdr.ipv4.diffserv = hdr.ipv4.diffserv | 0x03;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 16;
    }

    table ipv4_lpm {
        key   = { hdr.ipv4.dst_addr: lpm; }
        actions = { ipv4_forward; drop; NoAction; }
        default_action = drop();
    }

    table switch_config {
        key   = { std_meta.ingress_port: exact; }
        actions = { set_switch_config; NoAction; }
        default_action = set_switch_config(1, 0, 0);
    }

    table telem_init_policy {
        key = {
            hdr.ipv4.src_addr: ternary;
            hdr.ipv4.dst_addr: ternary;
        }
        actions = {
            init_queue_telem;
            init_stack_telem;
            init_tree_telem;
            NoAction;
        }
        default_action = NoAction();
        size = 64;
    }

    apply {
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
            switch_config.apply();
            if (!hdr.telem_ctrl.isValid()) {
                telem_init_policy.apply();
            }
            meta.ingress_tstamp = (bit<32>)std_meta.ingress_global_timestamp;
        }
    }
}

/* ── Egress ─────────────────────────────────────────────────── */
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t std_meta) {

    /* ── MODO FILA ────────────────────────────────────────────── */
    action add_queue_record() {
        bit<32> avg;
        bit<32> port32 = (bit<32>)std_meta.egress_port;

        /* Atualiza EWMA: avg = avg*7/8 + depth/8 */
        avg_queue_depth.read(avg, port32);
        avg = (avg >> 1) + (avg >> 2) + (avg >> 3) +
              ((bit<32>)std_meta.deq_qdepth >> 3);
        avg_queue_depth.write(port32, avg);

        /* Atualiza histograma de latência (bucket de 100µs) */
        bit<32> lat_bucket = (bit<32>)std_meta.deq_timedelta >> 17; // /100000ns≈100µs
        if (lat_bucket > 15) { lat_bucket = 15; }
        bit<32> hist_idx = port32 * 16 + lat_bucket;
        bit<32> hist_val;
        queue_latency_histogram.read(hist_val, hist_idx);
        queue_latency_histogram.write(hist_idx, hist_val + 1);

        /* Empilha registro no slot correto */
        bit<8> slot = hdr.telem_ctrl.hop_count;
        if (slot == 0) {
            hdr.queue_rec_0.setValid();
            hdr.queue_rec_0.port_id      = (bit<16>)std_meta.egress_port;
            hdr.queue_rec_0.enqueue_ts   = meta.ingress_tstamp;
            hdr.queue_rec_0.dequeue_ts   = (bit<32>)std_meta.egress_global_timestamp;
            hdr.queue_rec_0.queue_depth  = (bit<32>)std_meta.deq_qdepth;
            hdr.queue_rec_0.sojourn_time = (bit<32>)std_meta.deq_timedelta;
            hdr.queue_rec_0.drop_prob    = 0;
        } else if (slot == 1) {
            hdr.queue_rec_1.setValid();
            hdr.queue_rec_1.port_id      = (bit<16>)std_meta.egress_port;
            hdr.queue_rec_1.enqueue_ts   = meta.ingress_tstamp;
            hdr.queue_rec_1.dequeue_ts   = (bit<32>)std_meta.egress_global_timestamp;
            hdr.queue_rec_1.queue_depth  = (bit<32>)std_meta.deq_qdepth;
            hdr.queue_rec_1.sojourn_time = (bit<32>)std_meta.deq_timedelta;
            hdr.queue_rec_1.drop_prob    = 0;
        } else if (slot == 2) {
            hdr.queue_rec_2.setValid();
            hdr.queue_rec_2.port_id      = (bit<16>)std_meta.egress_port;
            hdr.queue_rec_2.enqueue_ts   = meta.ingress_tstamp;
            hdr.queue_rec_2.dequeue_ts   = (bit<32>)std_meta.egress_global_timestamp;
            hdr.queue_rec_2.queue_depth  = (bit<32>)std_meta.deq_qdepth;
            hdr.queue_rec_2.sojourn_time = (bit<32>)std_meta.deq_timedelta;
            hdr.queue_rec_2.drop_prob    = 0;
        } else if (slot == 3) {
            hdr.queue_rec_3.setValid();
            hdr.queue_rec_3.port_id      = (bit<16>)std_meta.egress_port;
            hdr.queue_rec_3.enqueue_ts   = meta.ingress_tstamp;
            hdr.queue_rec_3.dequeue_ts   = (bit<32>)std_meta.egress_global_timestamp;
            hdr.queue_rec_3.queue_depth  = (bit<32>)std_meta.deq_qdepth;
            hdr.queue_rec_3.sojourn_time = (bit<32>)std_meta.deq_timedelta;
            hdr.queue_rec_3.drop_prob    = 0;
        }
        hdr.telem_ctrl.hop_count = hdr.telem_ctrl.hop_count + 1;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 20;
    }

    /* ── MODO PILHA ───────────────────────────────────────────── */
    action push_congestion_event(bit<16> ev_type) {
        /* Empurra evento no topo da pilha in-packet */
        // Desloca eventos existentes para baixo
        if (hdr.stack_3.isValid()) { hdr.stack_3.setInvalid(); }
        if (hdr.stack_2.isValid()) {
            hdr.stack_3 = hdr.stack_2;
            hdr.stack_3.setValid();
        }
        if (hdr.stack_1.isValid()) {
            hdr.stack_2 = hdr.stack_1;
            hdr.stack_2.setValid();
        }
        if (hdr.stack_top.isValid()) {
            hdr.stack_1 = hdr.stack_top;
            hdr.stack_1.setValid();
        }

        /* Novo topo */
        hdr.stack_top.setValid();
        hdr.stack_top.switch_id   = meta.switch_id;
        hdr.stack_top.timestamp   = (bit<32>)std_meta.egress_global_timestamp;
        hdr.stack_top.port_id     = (bit<16>)std_meta.egress_port;
        hdr.stack_top.event_type  = ev_type;
        hdr.stack_top.queue_depth = (bit<32>)std_meta.deq_qdepth;
        hdr.stack_top.burst_size  = 0;
        hdr.stack_top.severity    = (bit<8>)(std_meta.deq_qdepth >> 4);

        if (hdr.telem_ctrl.stack_depth < 4) {
            hdr.telem_ctrl.stack_depth = hdr.telem_ctrl.stack_depth + 1;
            hdr.ipv4.total_len = hdr.ipv4.total_len + 24;
        }

        /* Também grava no registrador global */
        bit<32> ptr;
        event_stack_ptr.read(ptr, 0);
        event_stack_sw_id.write(ptr, meta.switch_id);
        event_stack_ts.write(ptr, (bit<32>)std_meta.egress_global_timestamp);
        event_stack_type.write(ptr, (bit<32>)ev_type);
        ptr = (ptr + 1) % 1024;
        event_stack_ptr.write(0, ptr);
    }

    /* ── MODO ÁRVORE ──────────────────────────────────────────── */
    action add_tree_node() {
        bit<8> slot = hdr.telem_ctrl.hop_count;

        /* PathID acumulado: OR com bit do nó atual */
        bit<32> node_bit = (bit<32>)1 << (bit<32>)meta.child_index;
        bit<32> shifted   = node_bit << ((bit<32>)meta.tree_level * 4);
        hdr.telem_ctrl.path_id = hdr.telem_ctrl.path_id | shifted;

        if (slot == 0) {
            hdr.tree_node_0.setValid();
            hdr.tree_node_0.switch_id      = meta.switch_id;
            hdr.tree_node_0.tree_level     = meta.tree_level;
            hdr.tree_node_0.child_index    = meta.child_index;
            hdr.tree_node_0.path_bit       = shifted;
            hdr.tree_node_0.ingress_port   = (bit<32>)std_meta.ingress_port;
            hdr.tree_node_0.egress_port    = (bit<32>)std_meta.egress_port;
            hdr.tree_node_0.link_latency   = (bit<32>)std_meta.deq_timedelta / 1000;
            hdr.tree_node_0.bandwidth_used = (bit<32>)std_meta.deq_qdepth * 1500 / 1024;
            hdr.tree_node_0.timestamp      = (bit<32>)std_meta.egress_global_timestamp;
        } else if (slot == 1) {
            hdr.tree_node_1.setValid();
            hdr.tree_node_1.switch_id      = meta.switch_id;
            hdr.tree_node_1.tree_level     = meta.tree_level;
            hdr.tree_node_1.child_index    = meta.child_index;
            hdr.tree_node_1.path_bit       = shifted;
            hdr.tree_node_1.ingress_port   = (bit<32>)std_meta.ingress_port;
            hdr.tree_node_1.egress_port    = (bit<32>)std_meta.egress_port;
            hdr.tree_node_1.link_latency   = (bit<32>)std_meta.deq_timedelta / 1000;
            hdr.tree_node_1.bandwidth_used = (bit<32>)std_meta.deq_qdepth * 1500 / 1024;
            hdr.tree_node_1.timestamp      = (bit<32>)std_meta.egress_global_timestamp;
        } else if (slot == 2) {
            hdr.tree_node_2.setValid();
            hdr.tree_node_2.switch_id      = meta.switch_id;
            hdr.tree_node_2.tree_level     = meta.tree_level;
            hdr.tree_node_2.child_index    = meta.child_index;
            hdr.tree_node_2.path_bit       = shifted;
            hdr.tree_node_2.ingress_port   = (bit<32>)std_meta.ingress_port;
            hdr.tree_node_2.egress_port    = (bit<32>)std_meta.egress_port;
            hdr.tree_node_2.link_latency   = (bit<32>)std_meta.deq_timedelta / 1000;
            hdr.tree_node_2.bandwidth_used = (bit<32>)std_meta.deq_qdepth * 1500 / 1024;
            hdr.tree_node_2.timestamp      = (bit<32>)std_meta.egress_global_timestamp;
        } else if (slot == 3) {
            hdr.tree_node_3.setValid();
            hdr.tree_node_3.switch_id      = meta.switch_id;
            hdr.tree_node_3.tree_level     = meta.tree_level;
            hdr.tree_node_3.child_index    = meta.child_index;
            hdr.tree_node_3.path_bit       = shifted;
            hdr.tree_node_3.ingress_port   = (bit<32>)std_meta.ingress_port;
            hdr.tree_node_3.egress_port    = (bit<32>)std_meta.egress_port;
            hdr.tree_node_3.link_latency   = (bit<32>)std_meta.deq_timedelta / 1000;
            hdr.tree_node_3.bandwidth_used = (bit<32>)std_meta.deq_qdepth * 1500 / 1024;
            hdr.tree_node_3.timestamp      = (bit<32>)std_meta.egress_global_timestamp;
        }

        hdr.telem_ctrl.hop_count = hdr.telem_ctrl.hop_count + 1;
        hdr.ipv4.total_len = hdr.ipv4.total_len + 40;
    }

    apply {
        if (hdr.telem_ctrl.isValid()) {
            if (meta.telem_mode == 1) {
                /* FILA: sempre adiciona registro */
                add_queue_record();
            } else if (meta.telem_mode == 2) {
                /* PILHA: só empilha se detectar congestionamento */
                if (std_meta.deq_qdepth > 50) {
                    push_congestion_event(1); // fila cheia
                } else if (std_meta.deq_timedelta > 1000000) {
                    push_congestion_event(2); // alta latência
                }
            } else if (meta.telem_mode == 3) {
                /* ÁRVORE: sempre adiciona nó do switch */
                add_tree_node();
            }
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
        pkt.emit(hdr.telem_ctrl);
        /* FILA */
        pkt.emit(hdr.queue_rec_0);
        pkt.emit(hdr.queue_rec_1);
        pkt.emit(hdr.queue_rec_2);
        pkt.emit(hdr.queue_rec_3);
        /* PILHA */
        pkt.emit(hdr.stack_top);
        pkt.emit(hdr.stack_1);
        pkt.emit(hdr.stack_2);
        pkt.emit(hdr.stack_3);
        /* ÁRVORE */
        pkt.emit(hdr.tree_node_0);
        pkt.emit(hdr.tree_node_1);
        pkt.emit(hdr.tree_node_2);
        pkt.emit(hdr.tree_node_3);
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
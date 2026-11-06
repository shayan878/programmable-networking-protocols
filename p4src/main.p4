#include <core.p4>
#include <v1model.p4>

const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<8> IP_PROTOCOL_TCP = 6;

#define FLOW_COUNTER_ENTRIES 4096
#define FLOW_COUNTER_WIDTH 32
#define FLOW_PACKET_THRESHOLD 1000

typedef bit<9> egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ipv4Addr_t;

header ethernet_t {
    macAddr_t dst_addr;
    macAddr_t src_addr;
    bit<16> ether_type;
}

header ipv4_t {
    bit<4> version;
    bit<4> ihl;
    bit<8> diffserv;
    bit<16> total_len;
    bit<16> identification;
    bit<3> flags;
    bit<13> frag_offset;
    bit<8> ttl;
    bit<8> protocol;
    bit<16> hdr_checksum;
    ipv4Addr_t src_addr;
    ipv4Addr_t dst_addr;
}

header tcp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<32> seq_no;
    bit<32> ack_no;
    bit<4> data_offset;
    bit<4> reserved;
    bit<1> cwr;
    bit<1> ece;
    bit<1> urg;
    bit<1> ack;
    bit<1> psh;
    bit<1> rst;
    bit<1> syn;
    bit<1> fin;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgent_ptr;
}

struct metadata {
    bit<32> hash_index_one;
    bit<32> hash_index_two;
    bit<32> counter_one;
    bit<32> counter_two;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t ipv4;
    tcp_t tcp;
}

parser MyParser(
    packet_in packet,
    out headers hdr,
    inout metadata meta,
    inout standard_metadata_t standard_metadata
) {
    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            ETHERTYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            IP_PROTOCOL_TCP: parse_tcp;
            default: accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {
        verify_checksum(
            hdr.ipv4.isValid(),
            {
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr
            },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16
        );
    }
}

control MyIngress(
    inout headers hdr,
    inout metadata meta,
    inout standard_metadata_t standard_metadata
) {
    // Two hashed counters provide an approximate frequency estimate.
    register<bit<FLOW_COUNTER_WIDTH>>(FLOW_COUNTER_ENTRIES) flow_counters;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action update_flow_counters() {
        hash(
            meta.hash_index_one,
            HashAlgorithm.crc16,
            (bit<16>)0,
            { hdr.ipv4.src_addr, hdr.ipv4.dst_addr, hdr.tcp.dst_port },
            (bit<32>)FLOW_COUNTER_ENTRIES
        );

        hash(
            meta.hash_index_two,
            HashAlgorithm.crc32,
            (bit<16>)0,
            { hdr.ipv4.src_addr, hdr.ipv4.dst_addr, hdr.tcp.dst_port },
            (bit<32>)FLOW_COUNTER_ENTRIES
        );

        flow_counters.read(meta.counter_one, meta.hash_index_one);
        flow_counters.read(meta.counter_two, meta.hash_index_two);

        meta.counter_one = meta.counter_one + 1;
        meta.counter_two = meta.counter_two + 1;

        flow_counters.write(meta.hash_index_one, meta.counter_one);
        flow_counters.write(meta.hash_index_two, meta.counter_two);
    }

    // Both source and destination MAC addresses are specified for the
    // egress subnet; this is required for the included two-subnet topology.
    action ipv4_forward(
        macAddr_t router_src_mac,
        macAddr_t next_hop_mac,
        egressSpec_t port
    ) {
        hdr.ethernet.src_addr = router_src_mac;
        hdr.ethernet.dst_addr = next_hop_mac;
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dst_addr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            if (hdr.tcp.isValid()) {
                update_flow_counters();
                if (
                    meta.counter_one > FLOW_PACKET_THRESHOLD
                    && meta.counter_two > FLOW_PACKET_THRESHOLD
                ) {
                    drop();
                } else {
                    ipv4_lpm.apply();
                }
            } else {
                ipv4_lpm.apply();
            }
        }
    }
}

control MyEgress(
    inout headers hdr,
    inout metadata meta,
    inout standard_metadata_t standard_metadata
) {
    apply { }
}

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            {
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr
            },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16
        );
    }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
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

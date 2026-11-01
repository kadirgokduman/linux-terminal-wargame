"""Minimal libpcap writer.

No external dependencies: Ethernet/IPv4/TCP frames are constructed manually
and written in classic libpcap format (microsecond timestamps). Output is
readable by `tcpdump -r`, `tshark -r`, and `strings`.

Deterministic: fixed timestamps, fixed sequence numbers, fixed IPs.
"""

from __future__ import annotations

import socket
import struct

LINKTYPE_ETHERNET = 1
SNAPLEN = 65535
PCAP_MAGIC = 0xA1B2C3D4
BASE_TS = 826675200  # 1996-03-14T00:00:00Z

CLIENT_IP = "127.0.0.1"
SERVER_IP = "127.0.0.1"
CLIENT_PORT = 49812
SERVER_PORT = 8080

CLIENT_MAC = bytes.fromhex("020000000001")
SERVER_MAC = bytes.fromhex("020000000002")


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def _frame(payload: bytes, seq: int, ack: int, source_is_client: bool) -> bytes:
    src_mac, dst_mac = (CLIENT_MAC, SERVER_MAC) if source_is_client else (SERVER_MAC, CLIENT_MAC)
    src_ip, dst_ip = (CLIENT_IP, SERVER_IP) if source_is_client else (SERVER_IP, CLIENT_IP)
    sport, dport = (CLIENT_PORT, SERVER_PORT) if source_is_client else (SERVER_PORT, CLIENT_PORT)

    ethernet = dst_mac + src_mac + b"\x08\x00"
    total_length = 20 + 20 + len(payload)
    header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45, 0, total_length, 0x1A2B, 0x4000, 64, 6, 0,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip),
    )
    header = header[:10] + struct.pack("!H", _checksum(header)) + header[12:]
    tcp = struct.pack(
        "!HHIIBBHHH", sport, dport, seq, ack, 0x50, 0x18, 65535, 0, 0
    )
    return ethernet + header + tcp + payload


def _record(index: int, frame: bytes) -> bytes:
    # Each packet is 1 ms apart: fixed, ordered, reproducible.
    ts_sec = BASE_TS + index // 1000
    ts_usec = (index % 1000) * 1000
    return struct.pack("<IIII", ts_sec, ts_usec, len(frame), len(frame)) + frame


def _http(method: str, target: str, host: str, extra: str = "", body: str = "") -> bytes:
    lines = [
        f"{method} {target} HTTP/1.1",
        f"Host: {host}",
        "User-Agent: calder-fetch/1.0",
    ]
    if extra:
        lines.extend(extra.rstrip("\n").split("\n"))
    if body:
        lines.append(f"Content-Length: {len(body.encode())}")
        lines.append("Connection: close")
        text = "\r\n".join(lines) + "\r\n\r\n" + body
    else:
        lines.append("Connection: close")
        text = "\r\n".join(lines) + "\r\n\r\n"
    return text.encode("utf-8")


def _response(status: str, body: str = "") -> bytes:
    lines = ["HTTP/1.1 " + status, "Content-Type: application/json", "Connection: close"]
    if body:
        lines.append(f"Content-Length: {len(body.encode())}")
        text = "\r\n".join(lines) + "\r\n\r\n" + body
    else:
        text = "\r\n".join(lines) + "\r\n\r\n"
    return text.encode("utf-8")


def build_capture(host: str, seal: str) -> bytes:
    """Build a small HTTP conversation carrying the flag."""
    body = '{"seal":"%s","holder":"custodian"}' % seal
    client_frames = [
        _http("GET", "/archive/index", host),
        _http("GET", "/archive/1986/summary", host),
        _http(
            "POST", "/archive/verify", host,
            extra=f"Content-Type: application/json\nX-Archive-Seal: {seal}",
            body=body,
        ),
        _http("GET", "/archive/1996/notes", host),
    ]
    server_frames = [
        _response("200 OK", '{"entries":42}'),
        _response("200 OK", '{"years":[1986,1994,1996]}'),
        _response("200 OK", '{"status":"sealed"}'),
        _response("200 OK", '{"notes":"see register"}'),
    ]

    chunks = [struct.pack("<IHHiIII", PCAP_MAGIC, 2, 4, 0, 0, SNAPLEN, LINKTYPE_ETHERNET)]
    for index, (client, server) in enumerate(zip(client_frames, server_frames)):
        chunks.append(_record(2 * index, _frame(client, 1 + index * 1024, 1, True)))
        chunks.append(_record(2 * index + 1, _frame(server, 1, 1 + index * 1024, False)))
    return b"".join(chunks)

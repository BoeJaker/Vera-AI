#!/usr/bin/env python3

# Not A Tool - A sketch of a webcam exposure scanner for internal network reconnaissance.

import asyncio
import socket
import ssl
import struct
import hashlib
import json
import ipaddress
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

import uvloop
from scapy.all import ARP, Ether, srp  # requires root
from pysnmp.hlapi.asyncio import *

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# ================= CONFIG =================

FULL_SWEEP = False            # Optional 1–65535 sweep
TOP_PORT_LIMIT = 2000         # Adaptive initial sweep
CONCURRENCY = 1000
SCORE_THRESHOLD = 80
UDP_COMMON_PORTS = [3702, 1900]
SNMP_COMMUNITY = "public"
SNMP_PORT = 161
SNMP_TIMEOUT = 2   # seconds
retries = 0        # recommended for scanning
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

CAMERA_KEYWORDS = [
    "ip camera", "network camera", "onvif",
    "snapshot.jpg", "isapi", "mjpeg"
]

TLS_VENDOR_STRINGS = [
    "hikvision", "dahua", "axis", "reolink",
    "camera", "ubiquiti", "tplink"
]

# ===========================================

@dataclass
class Host:
    ip: str
    mac: str = ""
    score: int = 0
    findings: List[str] = field(default_factory=list)
    open_ports: Set[int] = field(default_factory=set)
    vendor: Optional[str] = None

    def to_dict(self):
        return {
            "ip": self.ip,
            "mac": self.mac,
            "score": self.score,
            "findings": self.findings,
            "open_ports": list(self.open_ports),
            "vendor": self.vendor
        }
# ================= ARP SWEEP =================

def arp_sweep(subnet: str) -> List[Host]:
    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
    result = srp(packet, timeout=2, verbose=0)[0]
    hosts = []
    for _, received in result:
        hosts.append(Host(ip=received.psrc, mac=received.hwsrc))
    return hosts


# ================= OUI LOOKUP =================

def load_oui_db(path="oui.txt") -> Dict[str, str]:
    db = {}
    try:
        with open(path) as f:
            for line in f:
                if "(base 16)" in line:
                    prefix = line[:6].strip().replace("-", ":").lower()
                    vendor = line.split("(base 16)")[-1].strip()
                    db[prefix] = vendor
    except:
        pass
    return db


def lookup_vendor(mac: str, db: Dict[str, str]) -> Optional[str]:
    prefix = mac.lower()[0:8]
    return db.get(prefix)


# ================= TCP SCAN =================

async def tcp_connect(ip: str, port: int, timeout=1):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout
        )
        writer.close()
        await writer.wait_closed()
        return port
    except:
        return None


# ================= BEHAVIORAL PROBES =================

async def probe_rtsp(ip, port):
    try:
        reader, writer = await asyncio.open_connection(ip, port)
        writer.write(f"OPTIONS rtsp://{ip}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode())
        await writer.drain()
        data = await asyncio.wait_for(reader.read(1024), timeout=1)
        writer.close()
        await writer.wait_closed()
        if b"RTSP/1.0" in data:
            return True
    except:
        pass
    return False


async def probe_http(ip, port):
    try:
        reader, writer = await asyncio.open_connection(ip, port)
        writer.write(f"GET / HTTP/1.1\r\nHost: {ip}\r\n\r\n".encode())
        await writer.drain()
        data = await asyncio.wait_for(reader.read(8192), timeout=1)
        writer.close()
        await writer.wait_closed()
        text = data.decode(errors="ignore").lower()
        return any(k in text for k in CAMERA_KEYWORDS)
    except:
        return False


async def probe_tls(ip, port):
    try:
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(ip, port, ssl=ctx)
        cert = writer.get_extra_info("ssl_object").getpeercert()
        writer.close()
        await writer.wait_closed()
        if cert:
            subject = str(cert).lower()
            return any(v in subject for v in TLS_VENDOR_STRINGS)
    except:
        pass
    return False


# ================= UDP SWEEP =================

async def udp_probe(ip, port):
    try:
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: asyncio.DatagramProtocol(),
            remote_addr=(ip, port)
        )
        transport.sendto(b"\x00")
        await asyncio.sleep(0.5)
        transport.close()
    except:
        pass


# ================= ONVIF DISCOVERY =================

async def onvif_discovery():
    message = b"""<?xml version="1.0" encoding="UTF-8"?>
    <e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
    xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
    xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
    <e:Header>
    <w:MessageID>uuid:1234</w:MessageID>
    <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
    </e:Header>
    <e:Body>
    <d:Probe>
    <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
    </e:Body>
    </e:Envelope>"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (SSDP_ADDR, 3702))
    sock.close()


# ================= mDNS PASSIVE =================

async def mdns_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', MDNS_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(MDNS_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except:
            await asyncio.sleep(0.1)


# ================= SSDP PASSIVE =================

async def ssdp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', SSDP_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except:
            await asyncio.sleep(0.1)


# ================= SNMP WALK =================

async def snmp_walk(ip):
    try:
        engine = SnmpEngine()

        transport = UdpTransportTarget(
            (ip, SNMP_PORT),
            SNMP_TIMEOUT,   # timeout (positional)
            0               # retries
        )

        async for (
            errorIndication,
            errorStatus,
            errorIndex,
            varBinds
        ) in bulkCmd(
            engine,
            CommunityData(SNMP_COMMUNITY, mpModel=1),  # v2c
            transport,
            ContextData(),
            0, 25,
            ObjectType(ObjectIdentity('1.3.6.1.2.1.1')),
            lexicographicMode=False
        ):
            if errorIndication:
                return False
            if errorStatus:
                return False

        return True

    except Exception:
        return False

# ================= NVR API =================

async def query_nvr(ip, port):
    try:
        reader, writer = await asyncio.open_connection(ip, port)
        writer.write(b"GET /api/overview HTTP/1.1\r\nHost: test\r\n\r\n")
        await writer.drain()
        await reader.read(4096)
        writer.close()
        await writer.wait_closed()
    except:
        pass


# ================= SWITCH / ROUTER ARP =================

async def query_infra_arp(ip):
    await snmp_walk(ip)


# ================= HOST SCANNER =================

async def scan_host(host: Host):
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def scan_port_range(start, end):
        tasks = []
        for port in range(start, end):
            async def worker(p=port):
                async with semaphore:
                    r = await tcp_connect(host.ip, p)
                    if r:
                        host.open_ports.add(r)
            tasks.append(worker())
        await asyncio.gather(*tasks)

    await scan_port_range(1, TOP_PORT_LIMIT)

    if FULL_SWEEP and host.score < SCORE_THRESHOLD:
        await scan_port_range(TOP_PORT_LIMIT, 65536)

    for port in list(host.open_ports):
        if await probe_rtsp(host.ip, port):
            host.score += 50
            host.findings.append(f"RTSP:{port}")
        if await probe_http(host.ip, port):
            host.score += 40
            host.findings.append(f"HTTP:{port}")
        if await probe_tls(host.ip, port):
            host.score += 30
            host.findings.append(f"TLS:{port}")

        if host.score >= SCORE_THRESHOLD:
            break

    for port in UDP_COMMON_PORTS:
        await udp_probe(host.ip, port)

    await snmp_walk(host.ip)
    await query_nvr(host.ip, 80)

    return host


# ================= VLAN SCAN =================

async def scan_vlans(subnets: List[str]):
    results = []
    for subnet in subnets:
        hosts = arp_sweep(subnet)
        tasks = [scan_host(h) for h in hosts]
        results.extend(await asyncio.gather(*tasks))
    return results


# ================= MAIN =================

async def main():
    oui_db = load_oui_db()
    subnets = ["192.168.0.0/24"]

    results = await scan_vlans(subnets)

    for h in results:
        h.vendor = lookup_vendor(h.mac, oui_db)

    print(json.dumps([h.to_dict() for h in results], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
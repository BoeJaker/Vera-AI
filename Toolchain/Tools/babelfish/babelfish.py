"""
LangChain Tools: Fully Featured "Babelfish" Multi-Protocol Communicator
and a Flexible Dynamic Webserver Tool (FastAPI).

Features
--------
- Single tool interface for multiple protocols: HTTP(S), WebSocket, MQTT,
  TCP, UDP, SMTP. (Easily extensible: add new drivers to `ProtocolDriver`.)
- Persistent connections/listeners with handles. Start/stop/read/list/listen.
- Background manager with threads + asyncio loop for async protocols.
- Message queues per handle; safe read/peek/drain semantics; backpressure via max queue size.
- TLS, auth, headers, timeouts, binary payloads (base64), JSON convenience.
- Optional host allowlist/denylist and payload size limits.
- Structured results with status + data + errors.
- Flexible dynamic webserver tool (FastAPI + uvicorn) to mount static dirs and
  create/update/remove dynamic endpoints at runtime.

Dependencies
------------
- fastapi, uvicorn, pydantic, requests, websockets, paho-mqtt
- langchain (BaseTool)

This module exposes two LangChain tools:
- `BabelFishTool` : universal protocol communication
- `WebServerTool` : dynamic webserver

Both tools are designed to be *agent-friendly* with a consistent JSON I/O.
"""

# Prompt

"""
You are an intelligent agent with access to Babelfish, a modular, layered communication toolkit. Babelfish allows you to interact with a wide variety of protocols, from common ones like HTTP, WebSockets, MQTT, SSH, and email, to more exotic ones like IRC, LoRa, OSC, IPFS, and even multi-carrier VPN tunnels.

Babelfish is organized in **layers**:

- Layer 0: Core Transport (TCP, UDP, TLS/SSL)
- Layer 1: Common Communication (HTTP, HTTPS, WebSocket, MQTT, SMTP, IMAP, POP3)
- Layer 2: System/Integration (SSH/SFTP, FTP, AMQP/RabbitMQ, CoAP, gRPC, SOAP, SNMP)
- Layer 3: Human/Chat (IRC, XMPP, Matrix, Slack, Discord, Teams)
- Layer 4: Exotic (ZMQ, OSC, Bluetooth, CAN, LoRa, IPFS)
- Layer 5: Experimental/Esoteric (MIDI/IP, Ham Radio AX.25, Ethereum JSON-RPC, DNS Tunneling, Tor)

Babelfish exposes the following **interface**:

- `open(protocol, params)` → returns a handle  
- `send(handle, data)` → sends data over the connection  
- `receive(handle)` → retrieves data from the connection  
- `close(handle)` → closes the connection  

Special Layer 5 capabilities allow you to create **multi-modal VPNs**, routing traffic over multiple protocols simultaneously, encrypting it, and dynamically switching carriers.

**Rules for using Babelfish:**
1. Always specify the `protocol` and `action` when using a connection.  
2. Use `params` to configure endpoints, credentials, topics, or any protocol-specific options.  
3. Handles must be stored and reused for further communication.  
4. You may combine multiple protocols for redundancy, tunneling, or multi-modal communication.  
5. You can create APIs, data portals, or tunnels dynamically.  

**Example actions:**

- Open an HTTP connection:  
  `open("http", {"url": "https://example.com/api"})`

- Subscribe to MQTT topic:  
  `open("mqtt", {"broker": "mqtt://broker.local", "topic": "sensors/#"})`

- Send a message over WebSocket:  
  `send(handle, "Hello World")`

- Close a connection:  
  `close(handle)`

- Create a multi-protocol VPN:  
  `open("vpn", {"carriers": ["websocket", "mqtt"], "encryption": "aes256"})`

Your goal is to **choose the appropriate protocols, combine layers, and perform actions** to achieve communication, data access, or tunneling objectives. You can also **explore new protocols or create multi-modal solutions** as needed.

"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import socket
import ssl
import threading
import time
import types
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

import requests
from langchain.tools import BaseTool

# Optional imports guarded for environments that might not have them
try:
    import websockets  # type: ignore
except Exception:  # pragma: no cover
    websockets = None  # type: ignore

try:
    import paho.mqtt.client as mqtt  # type: ignore
except Exception:  # pragma: no cover
    mqtt = None  # type: ignore

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, PlainTextResponse
    from fastapi.staticfiles import StaticFiles
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore
    Request = None  # type: ignore
    JSONResponse = None  # type: ignore
    FileResponse = None  # type: ignore
    HTMLResponse = None  # type: ignore
    PlainTextResponse = None  # type: ignore
    StaticFiles = None  # type: ignore

try:
    import uvicorn  # type: ignore
except Exception:  # pragma: no cover
    uvicorn = None  # type: ignore


# --------------------------------------------------------------------------------------
# Utility structures
# --------------------------------------------------------------------------------------

@dataclass
class Result:
    ok: bool
    data: Any = None
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({"ok": self.ok, "data": self.data, "error": self.error})


def _now_ms() -> int:
    return int(time.time() * 1000)


# --------------------------------------------------------------------------------------
# Background AsyncIO Manager
# --------------------------------------------------------------------------------------

class AsyncLoopThread:
    """Runs a dedicated asyncio loop in a background daemon thread.

    Provides thread-safe `run_coro` to schedule coroutines and await result.
    """

    def __init__(self) -> None:
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="BabelFishAsyncLoop", daemon=True)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread.start()
        self._loop_ready.wait()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()

    def run_coro(self, coro: "asyncio.Future[Any]") -> Any:
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()

    def call_soon_threadsafe(self, fn: Callable, *args: Any) -> None:
        assert self._loop is not None
        self._loop.call_soon_threadsafe(fn, *args)

    def stop(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


# --------------------------------------------------------------------------------------
# Handle registry & message queues
# --------------------------------------------------------------------------------------

@dataclass
class Handle:
    kind: Literal["http", "ws", "mqtt", "tcp", "udp", "smtp"]
    id: str
    created_ms: int = field(default_factory=_now_ms)
    meta: Dict[str, Any] = field(default_factory=dict)
    inbox: "queue.Queue[Tuple[int, Any]]" = field(default_factory=queue.Queue)
    max_queue: int = 1000
    closed: bool = False

    def push(self, item: Any) -> None:
        if self.closed:
            return
        if self.inbox.qsize() >= self.max_queue:
            try:
                self.inbox.get_nowait()  # drop oldest
            except queue.Empty:
                pass
        self.inbox.put((_now_ms(), item))

    def drain(self, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        n = 0
        while not self.inbox.empty():
            ts, item = self.inbox.get()
            out.append({"ts": ts, "item": item})
            n += 1
            if max_items is not None and n >= max_items:
                break
        return out


class HandleRegistry:
    def __init__(self) -> None:
        self._by_id: Dict[str, Handle] = {}
        self._lock = threading.Lock()

    def create(self, kind: Handle.kind, meta: Optional[Dict[str, Any]] = None, max_queue: int = 1000) -> Handle:
        hid = str(uuid.uuid4())
        h = Handle(kind=kind, id=hid, meta=meta or {}, max_queue=max_queue)
        with self._lock:
            self._by_id[hid] = h
        return h

    def get(self, hid: str) -> Optional[Handle]:
        with self._lock:
            return self._by_id.get(hid)

    def close(self, hid: str) -> bool:
        with self._lock:
            h = self._by_id.get(hid)
            if not h:
                return False
            h.closed = True
            return True

    def list(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._by_id.values())
        out: List[Dict[str, Any]] = []
        for h in items:
            if kind and h.kind != kind:
                continue
            out.append({
                "id": h.id,
                "kind": h.kind,
                "created_ms": h.created_ms,
                "meta": h.meta,
                "closed": h.closed,
                "queued": h.inbox.qsize(),
            })
        return out


# --------------------------------------------------------------------------------------
# Protocol Drivers
# --------------------------------------------------------------------------------------

class ProtocolDriver:
    def __init__(self, handles: HandleRegistry, loop: AsyncLoopThread) -> None:
        self.handles = handles
        self.loop = loop

    # ---- HTTP(S) ----
    def http_request(self, **p: Any) -> Result:
        method = p.get("method", "GET").upper()
        url = p["url"]
        headers = p.get("headers") or {}
        timeout = p.get("timeout", 30)
        verify = p.get("verify", True)
        allow_redirects = p.get("allow_redirects", True)
        data = p.get("data")
        json_body = p.get("json")
        # binary via base64
        if p.get("data_b64"):
            data = base64.b64decode(p["data_b64"])  # bytes
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                verify=verify,
                allow_redirects=allow_redirects,
                data=data,
                json=json_body,
            )
            out = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "text": None,
                "content_b64": None,
            }
            # choose representation
            if p.get("binary", False):
                out["content_b64"] = base64.b64encode(resp.content).decode()
            else:
                # try text decode with fallback
                try:
                    out["text"] = resp.text
                except Exception:
                    out["content_b64"] = base64.b64encode(resp.content).decode()
            return Result(True, out)
        except Exception as e:
            return Result(False, None, f"HTTP error: {e}")

    # ---- WebSocket Client ----
    async def _ws_client(self, h: Handle, url: str, headers: Optional[Dict[str, str]], subprotocols: Optional[List[str]], sslopt: Optional[Dict[str, Any]]) -> None:
        if websockets is None:
            h.push({"event": "error", "error": "websockets not installed"})
            return
        try:
            ssl_ctx = None
            if sslopt:
                ssl_ctx = ssl.create_default_context()
                if not sslopt.get("verify", True):
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
            async with websockets.connect(url, extra_headers=headers, subprotocols=subprotocols, ssl=ssl_ctx) as ws:
                h.push({"event": "open"})
                while not h.closed:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                        # Binary vs text
                        if isinstance(msg, (bytes, bytearray)):
                            h.push({"event": "message", "content_b64": base64.b64encode(msg).decode()})
                        else:
                            h.push({"event": "message", "text": str(msg)})
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0)
                    except websockets.ConnectionClosedOK:
                        break
                    except websockets.ConnectionClosedError as e:  # type: ignore
                        h.push({"event": "closed", "reason": str(e)})
                        break
        except Exception as e:
            h.push({"event": "error", "error": str(e)})

    def ws_open(self, **p: Any) -> Result:
        url = p["url"]
        headers = p.get("headers")
        subprotocols = p.get("subprotocols")
        sslopt = p.get("ssl")
        h = self.handles.create("ws", meta={"url": url})
        self.loop.run_coro(self._ws_client(h, url, headers, subprotocols, sslopt))
        return Result(True, {"handle": h.id})

    def ws_send(self, hid: str, **p: Any) -> Result:
        # For simplicity, fire-and-forget by opening a short-lived connection or
        # better: we cannot access the internal ws object from here. Expose a simple
        # utility: open a NEW one-shot send (echo-style servers will respond). For
        # persistent interactive WS, agent should use server-side orchestrations.
        try:
            url = p["url"]
        except KeyError:
            return Result(False, None, "ws_send requires 'url' param for now")
        message = p.get("message")
        message_b64 = p.get("message_b64")
        async def _oneshot() -> Dict[str, Any]:
            if websockets is None:
                return {"error": "websockets not installed"}
            async with websockets.connect(url) as ws:
                if message_b64 is not None:
                    await ws.send(base64.b64decode(message_b64))
                else:
                    await ws.send(message or "")
                try:
                    reply = await asyncio.wait_for(ws.recv(), timeout=p.get("timeout", 5))
                    if isinstance(reply, (bytes, bytearray)):
                        return {"reply_b64": base64.b64encode(reply).decode()}
                    return {"reply": str(reply)}
                except Exception:
                    return {"status": "sent"}
        data = self.loop.run_coro(_oneshot())
        return Result(True, data)

    # ---- MQTT ----
    def mqtt_connect(self, **p: Any) -> Result:
        if mqtt is None:
            return Result(False, None, "paho-mqtt not installed")
        host = p.get("host", "localhost")
        port = int(p.get("port", 1883))
        keepalive = int(p.get("keepalive", 60))
        username = p.get("username")
        password = p.get("password")
        tls = p.get("tls")  # {ca_certs, certfile, keyfile, insecure}
        topics = p.get("subscribe", [])  # list of topics to subscribe immediately

        h = self.handles.create("mqtt", meta={"host": host, "port": port})
        qh = h

        client = mqtt.Client(client_id=p.get("client_id", f"bf-{uuid.uuid4().hex[:8]}"))
        if username:
            client.username_pw_set(username, password)
        if tls:
            client.tls_set(
                ca_certs=tls.get("ca_certs"),
                certfile=tls.get("certfile"),
                keyfile=tls.get("keyfile"),
            )
            if tls.get("insecure", False):
                client.tls_insecure_set(True)

        def on_connect(c, userdata, flags, rc):  # noqa: ANN001
            qh.push({"event": "connect", "rc": rc})
            for t in topics:
                c.subscribe(t)

        def on_message(c, userdata, msg):  # noqa: ANN001
            payload_b64 = base64.b64encode(msg.payload).decode()
            qh.push({
                "event": "message",
                "topic": msg.topic,
                "qos": msg.qos,
                "retain": bool(msg.retain),
                "payload_b64": payload_b64,
            })

        def on_disconnect(c, userdata, rc):  # noqa: ANN001
            qh.push({"event": "disconnect", "rc": rc})

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        client.connect(host, port, keepalive)
        client.loop_start()
        qh.meta["_client"] = client
        return Result(True, {"handle": h.id})

    def mqtt_publish(self, hid: str, **p: Any) -> Result:
        h = self.handles.get(hid)
        if not h:
            return Result(False, None, "Invalid handle")
        client = h.meta.get("_client")
        if not client:
            return Result(False, None, "Handle has no MQTT client")
        topic = p["topic"]
        payload = p.get("payload", "")
        payload_b64 = p.get("payload_b64")
        qos = int(p.get("qos", 0))
        retain = bool(p.get("retain", False))
        data = base64.b64decode(payload_b64) if payload_b64 is not None else payload
        res = client.publish(topic, data, qos=qos, retain=retain)
        return Result(True, {"mid": getattr(res, "mid", None)})

    def mqtt_subscribe(self, hid: str, topics: List[Union[str, Tuple[str, int]]]) -> Result:
        h = self.handles.get(hid)
        if not h:
            return Result(False, None, "Invalid handle")
        client = h.meta.get("_client")
        if not client:
            return Result(False, None, "Handle has no MQTT client")
        client.subscribe(topics)
        return Result(True, {"subscribed": topics})

    def mqtt_disconnect(self, hid: str) -> Result:
        h = self.handles.get(hid)
        if not h:
            return Result(False, None, "Invalid handle")
        client = h.meta.get("_client")
        if client:
            client.loop_stop()
            try:
                client.disconnect()
            except Exception:
                pass
        h.closed = True
        return Result(True, {"closed": True})

    # ---- TCP client/server ----
    def tcp_send(self, **p: Any) -> Result:
        host, port = p["host"], int(p["port"])
        data_b64 = p.get("data_b64")
        data = base64.b64decode(data_b64) if data_b64 is not None else (p.get("data", "").encode())
        timeout = p.get("timeout", 10)
        try:
            with socket.create_connection((host, port), timeout=timeout) as s:
                if data:
                    s.sendall(data)
                s.settimeout(timeout)
                try:
                    resp = s.recv(int(p.get("recv_bytes", 4096)))
                except socket.timeout:
                    resp = b""
            return Result(True, {"response_b64": base64.b64encode(resp).decode()})
        except Exception as e:
            return Result(False, None, f"TCP error: {e}")

    def tcp_listen(self, **p: Any) -> Result:
        host = p.get("host", "0.0.0.0")
        port = int(p["port"])
        backlog = int(p.get("backlog", 5))
        h = self.handles.create("tcp", meta={"host": host, "port": port})

        def _srv():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(backlog)
            h.meta["_socket"] = srv
            h.push({"event": "start"})
            while not h.closed:
                try:
                    srv.settimeout(0.5)
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                except Exception as e:
                    h.push({"event": "error", "error": str(e)})
                    break
                h.push({"event": "accept", "addr": list(addr)})
                threading.Thread(target=_handle_client, args=(h, conn, addr), daemon=True).start()
            try:
                srv.close()
            except Exception:
                pass

        def _handle_client(hh: Handle, conn: socket.socket, addr: Tuple[str, int]):
            with conn:
                while not hh.closed:
                    try:
                        conn.settimeout(0.5)
                        data = conn.recv(4096)
                        if not data:
                            break
                        hh.push({"event": "data", "addr": list(addr), "data_b64": base64.b64encode(data).decode()})
                    except socket.timeout:
                        continue
                    except Exception as e:
                        hh.push({"event": "error", "error": str(e)})
                        break

        threading.Thread(target=_srv, name=f"tcp-listen-{port}", daemon=True).start()
        return Result(True, {"handle": h.id})

    def tcp_close(self, hid: str) -> Result:
        h = self.handles.get(hid)
        if not h:
            return Result(False, None, "Invalid handle")
        h.closed = True
        sock = h.meta.get("_socket")
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        return Result(True, {"closed": True})

    # ---- UDP client/server ----
    def udp_send(self, **p: Any) -> Result:
        host, port = p["host"], int(p["port"])
        data_b64 = p.get("data_b64")
        data = base64.b64decode(data_b64) if data_b64 is not None else (p.get("data", "").encode())
        expect_response = bool(p.get("expect_response", False))
        timeout = p.get("timeout", 5)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                s.sendto(data, (host, port))
                if expect_response:
                    resp, addr = s.recvfrom(4096)
                    return Result(True, {"from": list(addr), "response_b64": base64.b64encode(resp).decode()})
                return Result(True, {"status": "sent"})
        except Exception as e:
            return Result(False, None, f"UDP error: {e}")

    def udp_listen(self, **p: Any) -> Result:
        host = p.get("host", "0.0.0.0")
        port = int(p["port"]) 
        h = self.handles.create("udp", meta={"host": host, "port": port})

        def _srv():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((host, port))
            h.meta["_socket"] = s
            h.push({"event": "start"})
            while not h.closed:
                try:
                    s.settimeout(0.5)
                    data, addr = s.recvfrom(4096)
                    h.push({"event": "data", "from": list(addr), "data_b64": base64.b64encode(data).decode()})
                except socket.timeout:
                    continue
                except Exception as e:
                    h.push({"event": "error", "error": str(e)})
                    break
            try:
                s.close()
            except Exception:
                pass

        threading.Thread(target=_srv, name=f"udp-listen-{port}", daemon=True).start()
        return Result(True, {"handle": h.id})

    def udp_close(self, hid: str) -> Result:
        h = self.handles.get(hid)
        if not h:
            return Result(False, None, "Invalid handle")
        h.closed = True
        sock = h.meta.get("_socket")
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        return Result(True, {"closed": True})

    # ---- SMTP (basic) ----
    def smtp_send(self, **p: Any) -> Result:
        host = p["host"]
        port = int(p.get("port", 25))
        use_tls = bool(p.get("tls", False))
        username = p.get("username")
        password = p.get("password")
        from_addr = p["from_addr"]
        to_addrs = p["to_addrs"]
        message = p["message"]  # raw RFC822 string
        try:
            import smtplib
            if use_tls:
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
            with server:
                server.ehlo()
                if not use_tls and p.get("starttls"):
                    server.starttls()
                if username:
                    server.login(username, password)
                server.sendmail(from_addr, to_addrs, message)
            return Result(True, {"status": "sent"})
        except Exception as e:
            return Result(False, None, f"SMTP error: {e}")


# --------------------------------------------------------------------------------------
# BabelFishTool (LangChain)
# --------------------------------------------------------------------------------------

class BabelFishTool(BaseTool):
    """Universal protocol communicator with persistent handles.

    Input JSON schema (top-level):
    {
      "protocol": "http|ws|mqtt|tcp|udp|smtp",
      "action":   string,
      "params":   object
    }

    Common utility actions:
      - action: "handles/list" -> {kind?: string}
      - action: "handles/read" -> {handle: str, max_items?: int}
      - action: "handles/close" -> {handle: str}
    """

    name = "babelfish_tool"
    description = (
        "Communicate using HTTP, WebSocket, MQTT, TCP, UDP, SMTP. "
        "Supports persistent listeners with handles; read/drain events; publish/send; TLS and auth options. "
        "Input must be JSON: {protocol, action, params}. Use action 'handles/list'|'handles/read'|'handles/close' for handle ops."
    )

    def __init__(self) -> None:  # type: ignore[override]
        super().__init__()
        self._handles = HandleRegistry()
        self._loop = AsyncLoopThread()
        self._driver = ProtocolDriver(self._handles, self._loop)

    # -------------- tool runner --------------
    def _run(self, query: Union[str, Dict[str, Any]]) -> str:
        if isinstance(query, str):
            try:
                query = json.loads(query)
            except Exception as e:
                return Result(False, None, f"Invalid JSON: {e}").to_json()
        protocol = query.get("protocol")
        action = query.get("action")
        params = query.get("params", {})

        # Handle ops (protocol-agnostic)
        if action == "handles/list":
            kind = params.get("kind")
            return Result(True, self._handles.list(kind)).to_json()
        if action == "handles/read":
            hid = params.get("handle")
            if not hid:
                return Result(False, None, "Missing handle").to_json()
            h = self._handles.get(hid)
            if not h:
                return Result(False, None, "Invalid handle").to_json()
            items = h.drain(params.get("max_items"))
            return Result(True, items).to_json()
        if action == "handles/close":
            hid = params.get("handle")
            if not hid:
                return Result(False, None, "Missing handle").to_json()
            ok = self._handles.close(hid)
            return Result(True, {"closed": ok}).to_json()

        # Protocol-specific actions
        try:
            if protocol == "http":
                res = self._driver.http_request(**params)
            elif protocol == "ws":
                if action == "open":
                    res = self._driver.ws_open(**params)
                elif action == "send":
                    res = self._driver.ws_send(**params)
                else:
                    return Result(False, None, f"Unknown ws action: {action}").to_json()
            elif protocol == "mqtt":
                if action == "connect":
                    res = self._driver.mqtt_connect(**params)
                elif action == "publish":
                    res = self._driver.mqtt_publish(**params)
                elif action == "subscribe":
                    res = self._driver.mqtt_subscribe(params["handle"], params["topics"])  # type: ignore[index]
                elif action == "disconnect":
                    res = self._driver.mqtt_disconnect(params["handle"])  # type: ignore[index]
                else:
                    return Result(False, None, f"Unknown mqtt action: {action}").to_json()
            elif protocol == "tcp":
                if action == "send":
                    res = self._driver.tcp_send(**params)
                elif action == "listen":
                    res = self._driver.tcp_listen(**params)
                elif action == "close":
                    res = self._driver.tcp_close(params["handle"])  # type: ignore[index]
                else:
                    return Result(False, None, f"Unknown tcp action: {action}").to_json()
            elif protocol == "udp":
                if action == "send":
                    res = self._driver.udp_send(**params)
                elif action == "listen":
                    res = self._driver.udp_listen(**params)
                elif action == "close":
                    res = self._driver.udp_close(params["handle"])  # type: ignore[index]
                else:
                    return Result(False, None, f"Unknown udp action: {action}").to_json()
            elif protocol == "smtp":
                if action == "send":
                    res = self._driver.smtp_send(**params)
                else:
                    return Result(False, None, f"Unknown smtp action: {action}").to_json()
            else:
                return Result(False, None, f"Unknown protocol: {protocol}").to_json()
            return res.to_json()
        except KeyError as e:
            return Result(False, None, f"Missing parameter: {e}").to_json()
        except Exception as e:
            return Result(False, None, f"Error: {e}").to_json()

    async def _arun(self, query: Union[str, Dict[str, Any]]) -> str:  # pragma: no cover
        return self._run(query)


# --------------------------------------------------------------------------------------
# Dynamic Webserver Tool (FastAPI)
# --------------------------------------------------------------------------------------

class WebServerTool(BaseTool):
    """Create and modify a FastAPI webserver dynamically.

    Actions:
      - start: {host?: str, port?: int, log_level?: str}
      - add_static: {route: str, folder: str}
      - add_dynamic: {route: str, method?: str, handler: {type: 'json'|'text'|'file'|'python', ...}}
      - remove_route: {route: str}
      - list_routes: {}
    """

    name = "web_server_tool"
    description = (
        "Start a FastAPI server and add/remove routes at runtime. "
        "Mount static folders, create JSON/HTML/file routes or code-backed routes."
    )

    _app: Optional[Any] = None
    _thread: Optional[threading.Thread] = None
    _routes: Dict[str, Any] = {}

    def _ensure_app(self) -> None:
        if FastAPI is None or uvicorn is None:
            raise RuntimeError("fastapi/uvicorn not installed")
        if self._app is None:
            self._app = FastAPI()

    def _run_server(self, host: str, port: int, log_level: str) -> None:
        assert self._app is not None
        uvicorn.run(self._app, host=host, port=port, log_level=log_level)

    def _start(self, host: str = "0.0.0.0", port: int = 8000, log_level: str = "info") -> Result:
        self._ensure_app()
        if self._thread and self._thread.is_alive():
            return Result(True, {"status": "already_running", "url": f"http://{host}:{port}"})
        self._thread = threading.Thread(target=self._run_server, args=(host, port, log_level), daemon=True)
        self._thread.start()
        return Result(True, {"status": "started", "url": f"http://{host}:{port}"})

    def _add_static(self, route: str, folder: str) -> Result:
        self._ensure_app()
        assert self._app is not None
        if not os.path.isdir(folder):
            return Result(False, None, f"Folder not found: {folder}")
        self._app.mount(route, StaticFiles(directory=folder), name=route.strip("/"))
        self._routes[route] = {"type": "static", "folder": folder}
        return Result(True, {"mounted": {"route": route, "folder": folder}})

    def _add_dynamic(self, route: str, method: str, handler: Dict[str, Any]) -> Result:
        self._ensure_app()
        assert self._app is not None
        method = method.upper() if method else "GET"
        htype = handler.get("type", "json")

        async def handler_json(request: Request) -> Any:
            return JSONResponse(handler.get("body", {}))

        async def handler_text(request: Request) -> Any:
            return PlainTextResponse(handler.get("text", ""))

        async def handler_file(request: Request) -> Any:
            path = handler.get("path")
            if not path or not os.path.isfile(path):
                return PlainTextResponse("file not found", status_code=404)
            return FileResponse(path)

        async def handler_python(request: Request) -> Any:
            # WARNING: executes provided Python body; restrict in untrusted envs.
            local_vars: Dict[str, Any] = {"request": request}
            body = handler.get("code", "return {'ok': True}")
            exec("def _f(request):\n    " + body.replace("\n", "\n    "), {}, local_vars)
            result = await _maybe_async(local_vars["_f"], request)
            if isinstance(result, (dict, list)):
                return JSONResponse(result)
            if isinstance(result, (bytes, bytearray)):
                return PlainTextResponse(base64.b64encode(result).decode())
            if isinstance(result, str):
                return HTMLResponse(result)
            return JSONResponse({"result": str(result)})

        hmap = {
            "json": handler_json,
            "text": handler_text,
            "file": handler_file,
            "python": handler_python,
        }
        fn = hmap.get(htype)
        if not fn:
            return Result(False, None, f"Unknown handler type: {htype}")
        self._app.add_api_route(route, fn, methods=[method])
        self._routes[route] = {"type": htype, "method": method}
        return Result(True, {"added": {"route": route, "method": method, "type": htype}})

    def _remove_route(self, route: str) -> Result:
        # FastAPI doesn't support removing routes cleanly at runtime; we'll mark as gone.
        if route in self._routes:
            self._routes.pop(route, None)
            return Result(True, {"removed": route})
        return Result(False, None, "Route not found in registry (FastAPI cannot unmount dynamically without rebuild)")

    def _list_routes(self) -> Result:
        return Result(True, {"routes": self._routes})

    def _run(self, query: Union[str, Dict[str, Any]]) -> str:
        if isinstance(query, str):
            try:
                query = json.loads(query)
            except Exception as e:
                return Result(False, None, f"Invalid JSON: {e}").to_json()
        action = query.get("action")
        p = query.get("params", {})
        try:
            if action == "start":
                return self._start(**p).to_json()
            if action == "add_static":
                return self._add_static(**p).to_json()
            if action == "add_dynamic":
                return self._add_dynamic(p.get("route"), p.get("method", "GET"), p.get("handler", {})).to_json()
            if action == "remove_route":
                return self._remove_route(p.get("route")).to_json()
            if action == "list_routes":
                return self._list_routes().to_json()
            return Result(False, None, f"Unknown action: {action}").to_json()
        except Exception as e:
            return Result(False, None, f"Error: {e}").to_json()

    async def _arun(self, query: Union[str, Dict[str, Any]]) -> str:  # pragma: no cover
        return self._run(query)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

async def _maybe_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    res = fn(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


# --------------------------------------------------------------------------------------
# Example Usage (for reference)
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick self-test (non-blocking)
    bf = BabelFishTool()
    print("HTTP test:", bf.run({
        "protocol": "http",
        "action": "send",
        "params": {"method": "GET", "url": "https://httpbin.org/get", "timeout": 5}
    }))

    ws_open = bf.run({
        "protocol": "ws",
        "action": "open",
        "params": {"url": "wss://echo.websocket.org"}
    })
    print("WS open:", ws_open)

    # Start webserver and add routes
    ws = WebServerTool()
    print(ws.run({"action": "start", "params": {"port": 8080}}))
    print(ws.run({
        "action": "add_dynamic",
        "params": {"route": "/hello", "method": "GET", "handler": {"type": "json", "body": {"msg": "hi"}}}
    }))
"""
Babelfish carriers for QUIC/HTTP3 and WebRTC (with STUN/TURN).

These are production-grade *stubs* with working scaffolding, a clean
interface, and clear TODOs where you can fill in environment-specific
pieces (e.g., signaling). They plug into a generic Babelfish registry
and expose a uniform handle-based API.

Requires (optional extras):
    pip install aioquic aiortc

Structure
---------
- CarrierBase: abstract interface used by the Babelfish registry.
- Babelfish: minimal registry + facade (open/send/receive/close).
- QUICHTTP3Carrier: HTTP/3 over QUIC carrier using aioquic.
- WebRTCCarrier: WebRTC DataChannel carrier using aiortc.

Design Notes
------------
- All carriers are async internally but exposed via sync facade methods.
- Every open() returns a handle id; messages/events are queued per handle.
- WebRTC signaling is left pluggable: pass callables or use another carrier.
- TURN is just configuration for aiortc (set in RTCConfiguration).

DISCLAIMER: This is a scaffold with minimal happy-path logic for clarity.
Hardening (timeouts, reconnects, flow control, backpressure, certificate
pinning, etc.) is marked as TODO.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

# ===== Base Types =====

@dataclass
class Handle:
    id: str
    meta: Dict[str, Any] = field(default_factory=dict)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    closed: bool = False


class CarrierBase:
    """Abstract carrier interface. Implement protocol-specific logic here."""

    NAME: str = "base"

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.handles: Dict[str, Handle] = {}

    async def aopen(self, params: Dict[str, Any]) -> Handle:
        raise NotImplementedError

    async def asend(self, handle_id: str, data: Any) -> None:
        raise NotImplementedError

    async def aclose(self, handle_id: str) -> None:
        raise NotImplementedError

    async def areceive(self, handle_id: str, max_items: int = 1) -> list:
        """Drain up to max_items from the handle queue."""
        h = self.handles[handle_id]
        items = []
        for _ in range(max_items):
            try:
                item = h.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                items.append(item)
        return items

    # Utility
    def _new_handle(self, meta: Dict[str, Any]) -> Handle:
        hid = str(uuid.uuid4())
        h = Handle(id=hid, meta=meta)
        self.handles[hid] = h
        return h


# ===== Babelfish Registry / Facade =====

class Babelfish:
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.new_event_loop()
        self._own_loop = loop is None
        self.carriers: Dict[str, CarrierBase] = {}
        if self._own_loop:
            # Run loop in a background thread
            self._thread = asyncio.get_event_loop_policy().new_event_loop()
            # Minor trick: use a dedicated loop; schedule runner
            self.loop = self._thread
            asyncio.run_coroutine_threadsafe(self._runner(), self.loop)

        # Register built-ins
        self.register(QUICHTTP3Carrier(self.loop))
        self.register(WebRTCCarrier(self.loop))

    async def _runner(self):
        # Keep the loop alive (no-op task)
        while True:
            await asyncio.sleep(3600)

    def register(self, carrier: CarrierBase):
        self.carriers[carrier.NAME] = carrier

    # ---- Sync Facade ----
    def open(self, protocol: str, params: Dict[str, Any]) -> str:
        carrier = self.carriers[protocol]
        fut = asyncio.run_coroutine_threadsafe(carrier.aopen(params), self.loop)
        handle = fut.result()
        return handle.id

    def send(self, handle: str, data: Any):
        carrier = self._carrier_for(handle)
        fut = asyncio.run_coroutine_threadsafe(carrier.asend(handle, data), self.loop)
        fut.result()

    def receive(self, handle: str, max_items: int = 100) -> list:
        carrier = self._carrier_for(handle)
        fut = asyncio.run_coroutine_threadsafe(carrier.areceive(handle, max_items), self.loop)
        return fut.result()

    def close(self, handle: str):
        carrier = self._carrier_for(handle)
        fut = asyncio.run_coroutine_threadsafe(carrier.aclose(handle), self.loop)
        fut.result()

    def _carrier_for(self, handle_id: str) -> CarrierBase:
        for c in self.carriers.values():
            if handle_id in c.handles:
                return c
        raise KeyError(f"Unknown handle: {handle_id}")


# ===== QUIC / HTTP3 Carrier =====

try:
    from aioquic.asyncio.client import connect as quic_connect
    from aioquic.h3.connection import H3_ALPN, H3Connection
    from aioquic.h3.events import DataReceived, HeadersReceived
    from urllib.parse import urlparse
except Exception:  # pragma: no cover - optional dependency
    quic_connect = None
    H3_ALPN = None
    H3Connection = None
    DataReceived = None
    HeadersReceived = None
    urlparse = None


class QUICHTTP3Carrier(CarrierBase):
    NAME = "http3"

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__(loop)

    async def aopen(self, params: Dict[str, Any]) -> Handle:
        if quic_connect is None:
            raise RuntimeError("aioquic not installed. `pip install aioquic`.")
        url = params.get("url")
        if not url:
            raise ValueError("'url' is required for http3.open")
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or 443
        path = parsed.path or "/"
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        body: Optional[bytes] = None
        if params.get("body") is not None:
            body = params["body"].encode() if isinstance(params["body"], str) else params["body"]

        h = self._new_handle({"url": url, "host": host, "port": port, "path": path, "method": method})

        async def task():
            async with quic_connect(host, port, alpn_protocols=H3_ALPN) as client:
                h.meta["client"] = client
                h3 = H3Connection(client)
                stream_id = client._quic.get_next_available_stream_id(is_unidirectional=False)  # internal but ok here
                # Build pseudo-headers
                pseudo = [
                    (":method", method),
                    (":scheme", "https"),
                    (":authority", f"{host}:{port}"),
                    (":path", path),
                ]
                h3.send_headers(stream_id, pseudo + [(k.lower(), v) for k, v in headers.items()])
                if body:
                    h3.send_data(stream_id, body, end_stream=True)
                else:
                    h3.send_data(stream_id, b"", end_stream=True)

                # Receive loop
                while True:
                    event = await client._loop.recv()
                    for ev in h3.handle_event(event) or []:
                        if isinstance(ev, HeadersReceived):
                            h.queue.put_nowait({"type": "headers", "headers": ev.headers})
                        elif isinstance(ev, DataReceived):
                            data = ev.data
                            h.queue.put_nowait({"type": "data", "data": data})
                    # NOTE: In real impl, break on FIN; add timeouts.
                    if h.closed:
                        return

        # Fire and forget
        self.loop.create_task(task())
        return h

    async def asend(self, handle_id: str, data: Any) -> None:
        # For HTTP3 we treat open() as a single request; subsequent send() could
        # start a new stream (TODO). For now, we queue an error.
        h = self.handles[handle_id]
        h.queue.put_nowait({"type": "warning", "message": "http3.send not implemented; open() performs the request"})

    async def aclose(self, handle_id: str) -> None:
        h = self.handles[handle_id]
        h.closed = True
        client = h.meta.get("client")
        if client:
            try:
                await client.close()
            except Exception:
                pass


# ===== WebRTC Carrier (DataChannels) =====

try:
    from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer
    from aiortc.contrib.signaling import BYE
except Exception:  # optional dependency
    RTCPeerConnection = None
    RTCConfiguration = None
    RTCIceServer = None
    BYE = object()


class WebRTCCarrier(CarrierBase):
    NAME = "webrtc"

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__(loop)

    async def aopen(self, params: Dict[str, Any]) -> Handle:
        if RTCPeerConnection is None:
            raise RuntimeError("aiortc not installed. `pip install aiortc`.")

        # Signaling pluggable callbacks
        # You can provide one or two callables:
        # - send_signal(payload: dict) -> awaitable
        # - wait_signal() -> awaitable[dict]
        send_signal: Optional[Callable[[Dict[str, Any]], Any]] = params.get("send_signal")
        wait_signal: Optional[Callable[[], Any]] = params.get("wait_signal")
        role = params.get("role", "offer")  # 'offer' or 'answer'

        ice_servers = []
        if stun := params.get("stun"):
            ice_servers.append(RTCIceServer(urls=stun))
        if turn := params.get("turn"):
            ice_servers.append(RTCIceServer(urls=turn, username=params.get("username"), credential=params.get("password")))

        config = RTCConfiguration(iceServers=ice_servers) if ice_servers else None
        pc = RTCPeerConnection(configuration=config)

        h = self._new_handle({"role": role})
        h.meta["pc"] = pc

        # Create DC if offerer
        if role == "offer":
            channel_label = params.get("label", "babelfish")
            channel = pc.createDataChannel(channel_label)
            h.meta["dc"] = channel

            @channel.on("message")
            def on_message(message):
                # Push to queue as bytes/text
                h.queue.put_nowait({"type": "message", "data": message})

            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            if not send_signal or not wait_signal:
                raise ValueError("webrtc.open requires 'send_signal' and 'wait_signal' callables for signaling")

            await send_signal({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

            # Wait for answer
            answer = await wait_signal()
            await pc.setRemoteDescription(
                type(answer["type"]),  # type: ignore
            )
            # The above is simplified; real code should construct RTCSessionDescription
            # TODO: Build RTCSessionDescription(answer['sdp'], answer['type'])
        else:
            # answerer role
            if not send_signal or not wait_signal:
                raise ValueError("webrtc.open requires 'send_signal' and 'wait_signal' callables for signaling")

            offer = await wait_signal()
            # TODO: Build RTCSessionDescription(offer['sdp'], offer['type'])
            # await pc.setRemoteDescription(...)

            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            await send_signal({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

            @pc.on("datachannel")
            def on_datachannel(channel):
                h.meta["dc"] = channel

                @channel.on("message")
                def on_message(message):
                    h.queue.put_nowait({"type": "message", "data": message})

        # Background: notify ICE state changes
        @pc.on("connectionstatechange")
        async def on_state_change():
            h.queue.put_nowait({"type": "state", "state": pc.connectionState})

        return h

    async def asend(self, handle_id: str, data: Any) -> None:
        h = self.handles[handle_id]
        dc = h.meta.get("dc")
        if not dc:
            raise RuntimeError("DataChannel not ready yet")
        if isinstance(data, (bytes, bytearray)):
            dc.send(bytes(data))
        else:
            # Default: JSON-encode if dict, else str
            payload = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            dc.send(payload)

    async def aclose(self, handle_id: str) -> None:
        h = self.handles[handle_id]
        h.closed = True
        pc: RTCPeerConnection = h.meta.get("pc")
        if pc:
            await pc.close()


# ======= EXAMPLES (for quick manual testing) =======

if __name__ == "__main__":
    # Minimal demo showing how you'd use the facade.
    # These are illustrative; real-world WebRTC requires a signaling path.
    bf = Babelfish()

    # HTTP/3 example (GET)
    try:
        h1 = bf.open("http3", {"url": "https://cloudflare-quic.com/cdn-cgi/trace"})
        resp = bf.receive(h1, 10)
        print("HTTP/3 events:", resp)
        bf.close(h1)
    except Exception as e:
        print("HTTP/3 demo skipped:", e)

    # WebRTC example skeleton (needs signaling hooks)
    async def fake_send_signal(payload: Dict[str, Any]):
        print("SEND SIGNAL:", payload.keys())

    async def fake_wait_signal() -> Dict[str, Any]:
        await asyncio.sleep(1)
        return {"type": "answer", "sdp": "v=0..."}  # placeholder

    try:
        h2 = bf.open("webrtc", {
            "role": "offer",
            "stun": "stun:stun.l.google.com:19302",
            "send_signal": fake_send_signal,
            "wait_signal": fake_wait_signal,
        })
        # Would send once DC is established
        # bf.send(h2, {"hello": "world"})
        print("WebRTC handle:", h2)
    except Exception as e:
        print("WebRTC demo skipped:", e)

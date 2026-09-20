"""
Minimal, zero-dependency asynchronous WebSocket client implementing RFC 6455
for communicating with Chromium/Brave DevTools Protocol (CDP).
"""

import asyncio
import base64
import json
import logging
import os
import struct
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class MinimalWebSocket:
    """Standard-library asynchronous WebSocket client (RFC 6455 compliant)."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False
        self._pending_futures: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._read_task: asyncio.Task | None = None
        self._next_id = 0

    @classmethod
    async def connect(cls, ws_url: str, timeout: float = 5.0) -> "MinimalWebSocket":
        parsed = urlparse(ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"

        ssl_ctx = None
        if parsed.scheme == "wss":
            import ssl

            ssl_ctx = ssl.create_default_context()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_ctx), timeout=timeout
        )

        # Handshake
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            "\r\n",
        ]
        writer.write("\r\n".join(headers).encode("latin1"))
        await writer.drain()

        # Read handshake response
        response_line = await reader.readline()
        if b"101" not in response_line:
            writer.close()
            await writer.wait_closed()
            raise ConnectionError(f"WebSocket handshake failed: {response_line.decode('latin1', 'ignore').strip()}")

        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break

        ws = cls(reader, writer)
        ws._start_reader()
        return ws

    def _start_reader(self) -> None:
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                frame = await self._read_frame()
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x1:  # Text frame
                    try:
                        data = json.loads(payload.decode("utf-8"))
                        req_id = data.get("id")
                        if req_id is not None and req_id in self._pending_futures:
                            fut = self._pending_futures.pop(req_id)
                            if not fut.done():
                                fut.set_result(data)
                    except Exception as e:
                        logger.debug(f"Error parsing CDP incoming frame: {e}")
                elif opcode == 0x8:  # Close frame
                    await self.close()
                    break
                elif opcode == 0x9:  # Ping
                    await self._send_frame(0xA, payload)  # Pong
        except (asyncio.CancelledError, ConnectionResetError, EOFError):
            pass
        except Exception as e:
            logger.debug(f"CDP read loop exception: {e}")
        finally:
            self._cleanup_pending(ConnectionError("WebSocket connection closed"))

    def _cleanup_pending(self, exc: Exception) -> None:
        for fut in self._pending_futures.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending_futures.clear()

    async def _read_frame(self) -> tuple[int, bytes] | None:
        first_two = await self.reader.readexactly(2)
        b1, b2 = first_two[0], first_two[1]
        opcode = b1 & 0x0F
        is_masked = bool(b2 & 0x80)
        length = b2 & 0x7F

        if length == 126:
            ext = await self.reader.readexactly(2)
            length = struct.unpack("!H", ext)[0]
        elif length == 127:
            ext = await self.reader.readexactly(8)
            length = struct.unpack("!Q", ext)[0]

        mask = None
        if is_masked:
            mask = await self.reader.readexactly(4)

        payload = await self.reader.readexactly(length)
        if is_masked and mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

        return opcode, payload

    async def _send_frame(self, opcode: int, data: bytes) -> None:
        if self._closed:
            raise ConnectionError("WebSocket is closed")

        b1 = 0x80 | (opcode & 0x0F)
        length = len(data)
        mask = os.urandom(4)
        masked_data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

        if length < 126:
            header = struct.pack("!BB", b1, 0x80 | length)
        elif length <= 0xFFFF:
            header = struct.pack("!BBH", b1, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", b1, 0x80 | 127, length)

        self.writer.write(header + mask + masked_data)
        await self.writer.drain()

    async def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        """Calls a CDP JSON-RPC method and returns response result."""
        self._next_id += 1
        req_id = self._next_id
        msg = {"id": req_id, "method": method, "params": params or {}}
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_futures[req_id] = fut

        payload = json.dumps(msg).encode("utf-8")
        await self._send_frame(0x1, payload)

        try:
            res = await asyncio.wait_for(fut, timeout=timeout)
            if "error" in res:
                raise RuntimeError(f"CDP error for {method}: {res['error']}")
            return res.get("result", {})
        finally:
            self._pending_futures.pop(req_id, None)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                # Send close frame
                await self._send_frame(0x8, b"")
            except Exception:
                pass
            if self._read_task and not self._read_task.done():
                self._read_task.cancel()
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass


class CdpClient:
    """Manages connection to Chromium/Brave DevTools Protocol."""

    def __init__(self, endpoint_url: str = "http://127.0.0.1:9222"):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.ws: MinimalWebSocket | None = None

    async def is_available(self, timeout: float = 1.0) -> bool:
        """Returns True if the CDP HTTP endpoint is reachable and listening."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{self.endpoint_url}/json/version")
                return res.status_code == 200
        except Exception:
            return False

    async def list_tabs(self, timeout: float = 2.0) -> list[dict[str, Any]]:
        """Returns list of open browser page targets."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{self.endpoint_url}/json/list")
                if res.status_code == 200:
                    return [t for t in res.json() if t.get("type") == "page"]
        except Exception as e:
            logger.debug(f"Error listing CDP tabs: {e}")
        return []

    async def attach_to_tab(self, ws_url: str, timeout: float = 5.0) -> bool:
        """Attaches to a specific tab via its WebSocket debugger URL."""
        try:
            self.ws = await MinimalWebSocket.connect(ws_url, timeout=timeout)
            try:
                await self.ws.call("Page.bringToFront", {}, timeout=2.0)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Failed to attach to CDP tab at {ws_url}: {e}")
            self.ws = None
            return False

    async def evaluate(self, expression: str, timeout: float = 10.0) -> Any:
        """Evaluates a JavaScript expression in the attached tab and returns the value."""
        if not self.ws:
            raise ConnectionError("Not attached to any CDP tab")
        res = await self.ws.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout,
        )
        result_obj = res.get("result", {})
        return result_obj.get("value")

    async def close_tab(self, target_id: str, timeout: float = 2.0) -> bool:
        """Closes a specific tab target via the CDP HTTP endpoint."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.put(f"{self.endpoint_url}/json/close/{target_id}")
                if res.status_code == 200:
                    return True
                res = await client.get(f"{self.endpoint_url}/json/close/{target_id}")
                return res.status_code == 200
        except Exception as e:
            logger.debug(f"Error closing CDP tab {target_id}: {e}")
        return False

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
            self.ws = None

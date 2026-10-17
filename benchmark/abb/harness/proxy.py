"""Egress proxy (specs/environments.md §5): an HTTP CONNECT proxy on loopback with an allow-list.

Only `CONNECT <allowed host>:<allowed port>` is tunnelled; everything else (other hosts, plain
HTTP requests) gets 403. The proxy resolves host names itself (the agent env sets
CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1). Every request is logged as one JSON line. Stdlib asyncio only.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from abb.util import utcnow_iso

MAX_HEADER = 16 * 1024


@dataclass
class ProxyConfig:
    host: str = "127.0.0.1"
    port: int = 8888
    allow_hosts: list[str] = field(default_factory=lambda: ["api.anthropic.com"])
    allow_ports: list[int] = field(default_factory=lambda: [443])
    log_path: Path | None = None
    connect_timeout_s: float = 20.0

    @classmethod
    def from_sandbox(cls, listen: str, allow_hosts: list[str], log_path: Path | None) -> "ProxyConfig":
        h, p = listen.rsplit(":", 1)
        return cls(host=h, port=int(p), allow_hosts=list(allow_hosts), log_path=log_path)


class EgressProxy:
    def __init__(self, cfg: ProxyConfig) -> None:
        self.cfg = cfg
        self._server: asyncio.base_events.Server | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._log_lock = threading.Lock()
        self.stats = {"allowed": 0, "denied": 0}

    # ------------------------------------------------------------------ logging
    def _log(self, rec: dict) -> None:
        self.stats["allowed" if rec.get("decision") == "allow" else "denied"] += 1
        if self.cfg.log_path is None:
            return
        line = json.dumps({"ts": utcnow_iso(), **rec}) + "\n"
        with self._log_lock:
            self.cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cfg.log_path, "a", encoding="utf-8") as f:
                f.write(line)

    # ------------------------------------------------------------------ protocol
    def allowed(self, host: str, port: int) -> bool:
        return host.lower().rstrip(".") in {h.lower() for h in self.cfg.allow_hosts} and port in self.cfg.allow_ports

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        t0 = time.monotonic()
        rec: dict = {"client": f"{peer[0]}:{peer[1]}" if peer else "?"}
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=30)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            writer.close()
            return
        line = head.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
        parts = line.split()
        method = parts[0].upper() if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        rec.update(method=method, target=target)
        if method != "CONNECT":
            rec.update(decision="deny", reason="only CONNECT is proxied")
            await self._reply(writer, 403, "Forbidden")
            self._log(rec)
            return
        host, _, port_s = target.rpartition(":")
        host = host.strip("[]")
        try:
            port = int(port_s)
        except ValueError:
            port = -1
        if not self.allowed(host, port):
            rec.update(decision="deny", reason="host not allow-listed")
            await self._reply(writer, 403, "Forbidden")
            self._log(rec)
            return
        up_r = up_w = None
        last: BaseException | None = None
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as e:
            infos, last = [], e
        for info in infos:  # every resolved address in turn (IPv6 and IPv4)
            addr = info[4][0]
            try:
                up_r, up_w = await asyncio.wait_for(asyncio.open_connection(addr, port), timeout=self.cfg.connect_timeout_s)
                break
            except (OSError, asyncio.TimeoutError) as e:
                last = e
        if up_w is None:
            rec.update(decision="allow", error=f"upstream: {last!r}")
            await self._reply(writer, 502, "Bad Gateway")
            self._log(rec)
            return
        rec.update(decision="allow", resolved=addr)
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        up_bytes, down_bytes = await asyncio.gather(self._pipe(reader, up_w), self._pipe(up_r, writer))
        rec.update(bytes_up=up_bytes, bytes_down=down_bytes, duration_s=round(time.monotonic() - t0, 3))
        self._log(rec)

    @staticmethod
    async def _reply(writer: asyncio.StreamWriter, code: int, text: str) -> None:
        with contextlib.suppress(ConnectionError):
            writer.write(f"HTTP/1.1 {code} {text}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
            await writer.drain()
        writer.close()

    @staticmethod
    async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> int:
        n = 0
        try:
            while chunk := await src.read(65536):
                n += len(chunk)
                dst.write(chunk)
                await dst.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                dst.close()
        return n

    # ------------------------------------------------------------------ lifecycle (background thread)
    def start(self) -> "EgressProxy":
        ready = threading.Event()
        err: list[BaseException] = []

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            try:
                self._server = self._loop.run_until_complete(
                    asyncio.start_server(self._handle, self.cfg.host, self.cfg.port, limit=MAX_HEADER))
            except BaseException as e:  # noqa: BLE001 - surfaced to the caller
                err.append(e)
                ready.set()
                return
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, name="abb-proxy", daemon=True)
        self._thread.start()
        ready.wait(10)
        if err:
            raise err[0]
        if self.cfg.port == 0 and self._server:
            self.cfg.port = self._server.sockets[0].getsockname()[1]
        return self

    def stop(self) -> None:
        if self._loop and self._server:
            async def _close() -> None:
                self._server.close()
                await self._server.wait_closed()

            fut = asyncio.run_coroutine_threadsafe(_close(), self._loop)
            with contextlib.suppress(Exception):
                fut.result(5)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(5)

    def __enter__(self) -> "EgressProxy":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def from_sandbox_config(mode: str = "user", log_path: Path | None = None) -> EgressProxy:
    from abb.config import load_sandbox

    m = load_sandbox().modes[mode]  # type: ignore[index]
    return EgressProxy(ProxyConfig.from_sandbox(m.proxy.listen, m.proxy.allow_hosts, log_path))

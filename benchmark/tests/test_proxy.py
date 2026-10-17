"""Egress proxy: allow-listed CONNECT tunnels, everything else 403, DNS resolved by the proxy, JSON log."""
from __future__ import annotations

import json
import socket
import ssl
import threading
from pathlib import Path

import pytest

from abb.harness.proxy import EgressProxy, ProxyConfig


def _echo_server() -> tuple[socket.socket, int]:
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()

    def serve() -> None:
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            data = c.recv(1024)
            c.sendall(b"echo:" + data)
            c.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv, srv.getsockname()[1]


def _connect(proxy_port: int, target: str) -> tuple[bytes, socket.socket]:
    s = socket.create_connection(("127.0.0.1", proxy_port), timeout=5)
    s.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = s.recv(1024)
        if not chunk:
            break
        head += chunk
    return head, s


@pytest.fixture()
def echo():
    srv, port = _echo_server()
    yield port
    srv.close()


def test_allowed_connect_tunnels_and_resolves_dns(tmp_path: Path, echo: int) -> None:
    log = tmp_path / "proxy.log"
    with EgressProxy(ProxyConfig(port=0, allow_hosts=["localhost"], allow_ports=[echo], log_path=log)) as p:
        head, s = _connect(p.cfg.port, f"localhost:{echo}")
        assert head.startswith(b"HTTP/1.1 200")
        s.sendall(b"ping")
        assert s.recv(1024) == b"echo:ping"
        s.close()
    rec = json.loads(log.read_text().splitlines()[-1])
    assert rec["decision"] == "allow" and rec["target"] == f"localhost:{echo}" and rec["resolved"] in ("127.0.0.1", "::1")


def test_other_host_or_port_denied(tmp_path: Path, echo: int) -> None:
    log = tmp_path / "proxy.log"
    with EgressProxy(ProxyConfig(port=0, allow_hosts=["api.anthropic.com"], allow_ports=[443], log_path=log)) as p:
        head, s = _connect(p.cfg.port, "github.com:443")
        assert head.startswith(b"HTTP/1.1 403")
        s.close()
        head, s = _connect(p.cfg.port, "api.anthropic.com:80")
        assert head.startswith(b"HTTP/1.1 403")
        s.close()
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert [r["decision"] for r in recs] == ["deny", "deny"]


def test_plain_http_denied(tmp_path: Path) -> None:
    with EgressProxy(ProxyConfig(port=0, log_path=tmp_path / "p.log")) as p:
        s = socket.create_connection(("127.0.0.1", p.cfg.port), timeout=5)
        s.sendall(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        assert s.recv(1024).startswith(b"HTTP/1.1 403")
        s.close()
        assert p.stats["denied"] == 1


@pytest.mark.skipif(not __import__("os").environ.get("ABB_INTEGRATION"), reason="network: set ABB_INTEGRATION=1")
def test_real_api_through_proxy(tmp_path: Path) -> None:
    with EgressProxy(ProxyConfig(port=0, log_path=tmp_path / "p.log")) as p:
        head, s = _connect(p.cfg.port, "api.anthropic.com:443")
        assert head.startswith(b"HTTP/1.1 200")
        tls = ssl.create_default_context().wrap_socket(s, server_hostname="api.anthropic.com")
        tls.sendall(b"GET /v1/models HTTP/1.1\r\nHost: api.anthropic.com\r\nConnection: close\r\n\r\n")
        assert tls.recv(64).startswith(b"HTTP/1.1 ")   # 401 without a key is fine
        tls.close()

from __future__ import annotations

from starlette.requests import Request

from app.core.client_ip import resolve_client_ip


def build_request(
    *,
    client_host: str | None,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("latin-1")))
    if real_ip is not None:
        headers.append((b"x-real-ip", real_ip.encode("latin-1")))

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/audit-logs",
            "headers": headers,
            "client": (client_host, 12345) if client_host is not None else None,
        }
    )


def test_resolve_client_ip_uses_forwarded_for_from_trusted_proxy() -> None:
    request = build_request(
        client_host="172.30.0.12",
        forwarded_for="203.0.113.9",
    )

    assert (
        resolve_client_ip(request, trusted_proxy_cidrs="172.30.0.0/24")
        == "203.0.113.9"
    )


def test_resolve_client_ip_ignores_forwarded_for_from_untrusted_client() -> None:
    request = build_request(
        client_host="192.168.10.25",
        forwarded_for="203.0.113.9",
    )

    assert resolve_client_ip(request, trusted_proxy_cidrs="172.30.0.0/24") == "192.168.10.25"


def test_resolve_client_ip_uses_direct_lan_or_vpn_ip_without_trusted_proxy() -> None:
    request = build_request(
        client_host="10.8.0.42",
        forwarded_for="203.0.113.9",
    )

    assert resolve_client_ip(request, trusted_proxy_cidrs="") == "10.8.0.42"


def test_resolve_client_ip_uses_real_ip_from_trusted_proxy_when_forwarded_for_missing() -> None:
    request = build_request(
        client_host="172.30.0.12",
        real_ip="198.51.100.25",
    )

    assert (
        resolve_client_ip(request, trusted_proxy_cidrs="172.30.0.0/24")
        == "198.51.100.25"
    )

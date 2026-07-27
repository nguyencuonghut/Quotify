from __future__ import annotations

from ipaddress import ip_address, ip_network

from starlette.requests import Request


def resolve_client_ip(
    request: Request,
    *,
    trusted_proxy_cidrs: str,
) -> str | None:
    direct_client_ip = request.client.host if request.client is not None else None
    if direct_client_ip and _is_trusted_proxy(direct_client_ip, trusted_proxy_cidrs):
        forwarded_ip = _first_valid_forwarded_ip(request.headers.get("X-Forwarded-For"))
        if forwarded_ip:
            return forwarded_ip

        real_ip = _valid_ip(request.headers.get("X-Real-IP"))
        if real_ip:
            return real_ip

    return direct_client_ip


def _is_trusted_proxy(client_ip: str, trusted_proxy_cidrs: str) -> bool:
    parsed_client_ip = _valid_ip(client_ip)
    if parsed_client_ip is None:
        return False

    for raw_cidr in trusted_proxy_cidrs.split(","):
        cidr = raw_cidr.strip()
        if not cidr:
            continue

        try:
            network = ip_network(cidr, strict=False)
        except ValueError:
            continue

        if ip_address(parsed_client_ip) in network:
            return True

    return False


def _first_valid_forwarded_ip(value: str | None) -> str | None:
    if not value:
        return None

    for candidate in value.split(","):
        parsed_candidate = _valid_ip(candidate.strip())
        if parsed_candidate:
            return parsed_candidate

    return None


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None

    try:
        return str(ip_address(value))
    except ValueError:
        return None

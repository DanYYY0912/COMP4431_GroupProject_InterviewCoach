"""Shared boundary checks for explicitly configured inference destinations."""

import ipaddress
from urllib.parse import urlsplit, urlunsplit


def provider_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise ValueError("Use a valid HTTP(S) base URL.") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
        or "\\" in value
        or any(c.isspace() or ord(c) < 32 for c in value)
        or "%" in host
    ):
        raise ValueError("Use an HTTP(S) base URL without credentials, query, or fragment.")
    local = host in {"localhost", "host.docker.internal", "llama", "whisper"} or host.endswith(
        ".local"
    )
    try:
        address = ipaddress.ip_address(host)
        local = (
            address.is_loopback
            or address in ipaddress.ip_network("10.0.0.0/8")
            or address in ipaddress.ip_network("172.16.0.0/12")
            or address in ipaddress.ip_network("192.168.0.0/16")
            or address in ipaddress.ip_network("fc00::/7")
        )
    except ValueError:
        pass
    if parsed.scheme == "http" and not local:
        raise ValueError(
            "Public inference endpoints require HTTPS; HTTP is allowed on localhost or a private LAN."
        )
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if parsed.scheme == "https" else 80):
        netloc += f":{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


def bearer_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}

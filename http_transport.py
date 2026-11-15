"""Conexões HTTPS com orçamento para tentativas em endereços IPv4 e IPv6."""

import http.client
import socket
import time
import urllib.request


def _connect(address, timeout, source_address=None):
    candidates = socket.getaddrinfo(*address, type=socket.SOCK_STREAM)
    # Os provedores oferecem IPv4. No Windows, IPv6 sem saída funcional
    # pode consumir o timeout em cada endereço antes de tentar IPv4.
    candidates.sort(key=lambda candidate: candidate[0] != socket.AF_INET)
    deadline = time.monotonic() + min(timeout, 5)
    last_error = OSError("Nenhum endereço disponível.")
    for family, kind, protocol, _, target in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        conn = socket.socket(family, kind, protocol)
        try:
            conn.settimeout(min(remaining, 1.5))
            if source_address:
                conn.bind(source_address)
            conn.connect(target)
            conn.settimeout(timeout)
            return conn
        except OSError as exc:
            last_error = exc
            conn.close()
    raise last_error


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _connect


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_HTTPSConnection, request)


urlopen = urllib.request.build_opener(_HTTPSHandler()).open

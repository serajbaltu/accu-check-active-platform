"""Utilidades de log: configuração do ``logging`` e hexdump de buffers.

Formato de log do projeto (fixo, para facilitate o parsing das capturas)::

    [2026-10-21 11:20:33.123] INFO  src.device: OUT 000000  45 30 00 02 ...

O hexdump tem 16 bytes por linha, offset à esquerda e ASCII à direita.
"""

from __future__ import annotations

import logging
import time
from typing import Final

LOG_FORMAT: Final = "[%(asctime)s.%(msecs)03d] %(levelname)-5s %(name)s: %(message)s"
LOG_DATEFMT: Final = "%Y-%m-%d %H:%M:%S"

_BYTES_PER_LINE: Final = 16


def setup_logging(verbose: bool = False) -> None:
    """Configura o ``logging`` raiz do projeto.

    ``verbose=True`` sobe para ``DEBUG``; o padrão é ``INFO``.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATEFMT,
    )
    # pyusb é falante demais em DEBUG.
    logging.getLogger("usb.core").setLevel(logging.INFO)


def hexdump(data: bytes, base_offset: int = 0, show_ascii: bool = True) -> str:
    """Devolve o hexdump multi-linha de ``data``.

    Cada linha tem o offset (8 dígitos hex), os bytes em hexadecimal
    separados por espaço e, à direita, a representação ASCII (``.`` para
    bytes não imprimíveis).
    """
    if not data:
        return "<vazio>"

    lines: list[str] = []
    for start in range(0, len(data), _BYTES_PER_LINE):
        chunk = data[start : start + _BYTES_PER_LINE]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        hex_part = hex_part.ljust(_BYTES_PER_LINE * 3 - 1)
        ascii_part = ""
        if show_ascii:
            ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
            ascii_part = ascii_part.ljust(_BYTES_PER_LINE)
        lines.append(f"{base_offset + start:08x}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)


def log_hex(
    logger: logging.Logger,
    direction: str,
    data: bytes,
    label: str = "",
    base_offset: int = 0,
) -> None:
    """Loga um buffer como hexdump, prefixado com direção e timestamp.

    ``direction`` deve ser ``"OUT"`` (enviado) ou ``"IN"`` (recebido).
    """
    stamp = time.monotonic()
    prefix = f"{direction} {label}".rstrip()
    logger.debug("%s @%.6f\n%s", prefix, stamp, hexdump(data, base_offset))


def log_apdu(
    logger: logging.Logger,
    direction: str,
    data: bytes,
    label: str = "",
) -> None:
    """Loga um APDU identificando o tipo pelo cabeçalho, se reconhecível."""
    from . import phdc

    try:
        apdu_type, invoke_id = phdc.parse_apdu_header(data)
    except ValueError:
        apdu_type, invoke_id = 0, 0

    name = {
        phdc.APDU_TYPE_ASSOCIATION_REQUEST: "ASSOC_REQ",
        phdc.APDU_TYPE_ASSOCIATION_RESPONSE: "ASSOC_RESP",
        phdc.APDU_TYPE_ASSOCIATION_RELEASE_REQUEST: "RELEASE_REQ",
        phdc.APDU_TYPE_ASSOCIATION_RELEASE_RESPONSE: "RELEASE_RESP",
        phdc.APDU_TYPE_PRESENTATION_APDU: "DATA",
    }.get(apdu_type, f"0x{apdu_type:04X}")

    extra = f" invoke={invoke_id}" if invoke_id else ""
    log_hex(logger, direction, data, f"{name}{extra} {label}".strip())

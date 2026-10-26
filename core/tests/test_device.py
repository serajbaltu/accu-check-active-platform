"""Testes da camada USB (:mod:`src.device`) com um aparelho falso.

O ``FakeUsbDevice`` devolve os pacotes na ordem em que foram programados,
o que permite testar a montagem de APDUs fragmentados em vários pacotes
bulk de 64 bytes — exatamente o que o Accu-Chek Active faz.
"""

from __future__ import annotations

import errno

import pytest
from src.device import Device, DeviceTimeoutError, Endpoints


class FakeUsbDevice:
    """Substitui um ``usb.core.Device`` nos testes."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)
        self.written: list[bytes] = []

    def read(self, endpoint: int, size: int, timeout: int) -> bytes:
        if not self.chunks:
            raise _timeout_error()
        return self.chunks.pop(0)

    def write(self, endpoint: int, data: bytes, timeout: int) -> int:
        self.written.append(bytes(data))
        return len(data)


def _timeout_error() -> Exception:
    import usb.core

    return usb.core.USBTimeoutError(
        "Operation timed out", -1, errno.ETIMEDOUT
    )


def make_device(chunks: list[bytes]) -> Device:
    return Device(FakeUsbDevice(chunks), Endpoints(in_ep=0x82, out_ep=0x01))


class TestReadApdu:
    """Montagem de APDUs que chegam em vários pacotes de 64 bytes."""

    def test_reads_a_single_chunk(self) -> None:
        dev = make_device([b"\xe2\x00\x00\x32" + b"\xaa" * 50])
        apdu = dev.read_apdu()
        assert len(apdu) == 54
        assert apdu[:2] == b"\xe2\x00"

    def test_joins_fragmented_chunks(self) -> None:
        """O config info real tem 270 bytes e chega em 5 pacotes."""
        full = b"\xe7\x00\x01\x0a" + bytes(range(256)) + b"\x0a" * 10
        assert len(full) == 270
        chunks = [full[i : i + 64] for i in range(0, len(full), 64)]
        assert len(chunks) == 5

        dev = make_device(chunks)
        assert dev.read_apdu() == full

    def test_stops_after_five_empty_reads(self) -> None:
        """Uma leitura vazia no meio não pode travar o cliente."""
        dev = make_device(
            [b"\xe7\x00\x00\x10", b"", b"", b"", b"", b"", b"\x01" * 16]
        )
        apdu = dev.read_apdu()
        assert apdu == b"\xe7\x00\x00\x10"

    def test_returns_short_data_untouched(self) -> None:
        dev = make_device([b"\xe2\x00"])
        assert dev.read_apdu() == b"\xe2\x00"


class TestTimeout:
    """Timeouts viram :class:`DeviceTimeoutError`, não exceção do pyusb."""

    def test_timeout_is_translated(self) -> None:
        dev = make_device([])
        with pytest.raises(DeviceTimeoutError):
            dev.bulk_in()

    def test_empty_read_is_not_a_timeout(self) -> None:
        """Um ZLP (0 bytes) é resposta válida, não expiração."""
        dev = make_device([b""])
        assert dev.bulk_in() == b""


class TestLifecycle:
    """Abertura e fechamento."""

    def test_close_is_idempotent(self) -> None:
        dev = make_device([])
        dev.close()
        dev.close()

    def test_context_manager(self) -> None:
        dev = make_device([])
        with dev as opened:
            assert opened is dev

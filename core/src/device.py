"""Camada USB — único módulo do projeto que importa ``usb`` (pyusb).

Isolar o pyusb aqui facilita escrever testes com mock: o resto do cliente
fala apenas com a interface :class:`Device` definida aqui.

Referências:
* ISO/IEEE 11073-20601 — camada de transporte PHDC.
* ``emogenet/accuchek`` — mesmo fluxo, com libusb-1.0 direto.
"""

from __future__ import annotations

import errno
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import usb.core
import usb.util

from .logging_utils import log_hex

logger = logging.getLogger(__name__)

DEFAULT_VID: Final = 0x173A
"""Roche."""

DEFAULT_PID: Final = 0x21CC
"""Accu-Chek Active."""

DEFAULT_TIMEOUT_MS: Final = 5000
"""Timeout generoso: o handshake do aparelho é lento."""

DEFAULT_INTERFACE: Final = 0
"""Interface 0 — a única, classe PHDC (15)."""

MAX_BULK_PACKET: Final = 64
"""Tamanho máximo de pacote bulk do aparelho."""

MAX_EMPTY_READS: Final = 5
"""Leituras vazias seguidas antes de desistir de completar um APDU."""


class DeviceNotFoundError(RuntimeError):
    """Nenhum dispositivo Roche com o VID/PID esperado foi encontrado."""


class DeviceOpenError(RuntimeError):
    """O dispositivo foi encontrado, mas não pôde ser aberto/reivindicado."""


class DeviceTimeoutError(RuntimeError):
    """A leitura do endpoint IN expirou sem nenhum dado."""


class DeviceIOError(RuntimeError):
    """Falha de I/O USB (handle obsoleto, aparelho desconectado, etc.)."""


@dataclass(frozen=True)
class Endpoints:
    """Endpoints bulk usados pela interface PHDC.

    O número dos endpoints varia entre modelos Roche (o artigo do ``emogenet``
    registra isso explicitamente), então eles são lidos do descritor em vez de
    fixados no código.
    """

    in_ep: int
    out_ep: int


class Device:
    """Um glicosímetro Roche aberto e reivindicado.

    Use como gerenciador de contexto::

        with Device.open() as dev:
            dev.bulk_out(b"\\xe2\\x00")
    """

    def __init__(
        self,
        dev: usb.core.Device,
        endpoints: Endpoints,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._dev = dev
        self.endpoints = endpoints
        self.timeout_ms = timeout_ms

    # -- construção ---------------------------------------------------------

    @classmethod
    def open(
        cls,
        vid: int = DEFAULT_VID,
        pid: int = DEFAULT_PID,
        interface: int = DEFAULT_INTERFACE,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> Device:
        """Encontra, abre e reivindica o dispositivo.

        Lança :class:`DeviceNotFoundError` se não houver aparelho conectado e
        :class:`DeviceOpenError` se a reivindicação falhar.
        """
        dev = None
        try:
            import libusb_package
            backend = libusb_package.get_libusb1_backend()
            dev = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
        except Exception:
            dev = usb.core.find(idVendor=vid, idProduct=pid)

        if dev is None:
            raise DeviceNotFoundError(
                f"nenhum dispositivo {vid:04x}:{pid:04x} encontrado. "
                "O aparelho está conectado e na tela de transferência de dados?"
            )

        try:
            dev.set_configuration()
        except (usb.core.USBError, NotImplementedError) as exc:
            logger.debug("set_configuration: %s", exc)

        try:
            usb.util.claim_interface(dev, interface)
        except (usb.core.USBError, NotImplementedError) as exc:
            logger.debug("claim_interface(%s): %s", interface, exc)

        try:
            if dev.is_kernel_driver_active(interface):
                logger.warning(
                    "driver de kernel ativo na interface %d; soltando", interface
                )
                dev.detach_kernel_driver(interface)
        except (NotImplementedError, usb.core.USBError):
            pass

        endpoints = _read_endpoints(dev, interface)
        logger.info(
            "dispositivo aberto: %s, endpoints IN=0x%02x OUT=0x%02x",
            _describe(dev),
            endpoints.in_ep,
            endpoints.out_ep,
        )
        return cls(dev, endpoints, timeout_ms)

    # -- I/O ----------------------------------------------------------------

    def bulk_out(self, data: bytes) -> int:
        """Envia ``data`` pelo endpoint OUT. Devolve o nº de bytes enviados."""
        logger.debug("-> %d byte(s) para OUT", len(data))
        try:
            sent = self._dev.write(
                self.endpoints.out_ep, data, timeout=self.timeout_ms
            )
        except usb.core.USBError as exc:
            raise DeviceIOError(f"falha ao escrever no endpoint OUT: {exc}") from exc
        log_hex(logger, "OUT", bytes(data[:sent]))
        return int(sent)

    def bulk_in(self, size: int = MAX_BULK_PACKET) -> bytes:
        """Lê do endpoint IN. Devolve os bytes recebidos.

        Levanta :class:`DeviceTimeoutError` se o aparelho não mandar nada
        dentro de ``timeout_ms``. Uma leitura que devolve **0 bytes** é um
        ZLP (packet vazio) e significa "ainda não tem nada" — não é timeout.
        """
        logger.debug("<- lendo ate %d byte(s) do IN", size)
        try:
            data = self._dev.read(self.endpoints.in_ep, size, timeout=self.timeout_ms)
        except usb.core.USBError as exc:
            if isinstance(exc, usb.core.USBTimeoutError) or (
                exc.errno == errno.ETIMEDOUT
            ):
                raise DeviceTimeoutError(
                    f"nenhum dado no endpoint IN em {self.timeout_ms} ms"
                ) from exc
            raise DeviceIOError(f"falha ao ler do endpoint IN: {exc}") from exc
        data = bytes(data)
        log_hex(logger, "IN", data)
        return data

    def control_get_status(self) -> bytes:
        """Faz o GET_STATUS (control transfer IN) — 1ª fase do handshake."""
        # libusb padrão: request_type | recipient | endpoint
        request_type = 0x80 | 0x00 | 0x80  # STANDARD | DEVICE | IN
        try:
            data = self._dev.ctrl_transfer(
                request_type, 0x00, 0, 0, 2, timeout=self.timeout_ms
            )
        except usb.core.USBError as exc:
            raise DeviceIOError(f"falha no GET_STATUS: {exc}") from exc
        data = bytes(data)
        log_hex(logger, "IN", data, "GET_STATUS")
        return data

    def read_apdu(self) -> bytes:
        """Lê um APDU **completo**, juntando os pacotes de 64 bytes.

        O aparelho envia APDUs grandes (o "config info" tem ~270 bytes) em
        vários pacotes bulk de 64 bytes. Uma leitura só devolve o primeiro
        pacote: é preciso continuar lendo até completar o comprimento
        declarado no cabeçalho do APDU (bytes 2-3, big-endian, exclusive
        dos 4 primeiros bytes).
        """
        data = self.bulk_in()
        if len(data) < 4:
            return data

        total = int.from_bytes(data[2:4], "big") + 4
        empty_reads = 0
        while len(data) < total:
            chunk = self.bulk_in()
            if not chunk:
                empty_reads += 1
                if empty_reads >= MAX_EMPTY_READS:
                    logger.warning(
                        "APDU incompleto: %d de %d byte(s)", len(data), total
                    )
                    break
                continue
            empty_reads = 0
            data += chunk

        if len(data) > total:
            logger.warning(
                "APDU maior que o declarado: %d byte(s) para %d", len(data), total
            )
        return data

    # -- ciclo de vida ------------------------------------------------------

    def close(self) -> None:
        """Solta a interface e fecha o handle. Idempotente."""
        # close() nunca deve levantar exceção: qualquer falha aqui é
        # engolida e registrada em nível debug.
        try:
            usb.util.release_interface(self._dev, DEFAULT_INTERFACE)
        except Exception as exc:  # noqa: BLE001
            logger.debug("release_interface: %s", exc)
        try:
            usb.util.dispose_resources(self._dev)
        except Exception as exc:  # noqa: BLE001
            logger.debug("dispose_resources: %s", exc)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Device {_describe(self._dev)}>"


def _read_endpoints(dev: usb.core.Device, interface: int) -> Endpoints:
    """Descobre os endpoints bulk IN/OUT da interface ``interface``."""
    cfg = dev.get_active_configuration()
    intf = cfg[(interface, 0)]

    in_ep = out_ep = None
    for endpoint in intf:
        if endpoint.bEndpointAddress & usb.util.ENDPOINT_IN:
            in_ep = endpoint.bEndpointAddress
        else:
            out_ep = endpoint.bEndpointAddress

    if in_ep is None or out_ep is None:
        raise DeviceOpenError(
            f"interface {interface} sem endpoints bulk IN/OUT "
            f"(in={in_ep}, out={out_ep})"
        )
    return Endpoints(in_ep=in_ep, out_ep=out_ep)


def _describe(dev: usb.core.Device) -> str:
    """Descrição curta do dispositivo, para log."""
    try:
        product = usb.util.get_string(dev, dev.iProduct) or "?"
    except (usb.core.USBError, ValueError):  # pragma: no cover
        product = "?"
    return (
        f"{dev.idVendor:04x}:{dev.idProduct:04x} {product} "
        f"(bus {dev.bus}, addr {dev.address})"
    )

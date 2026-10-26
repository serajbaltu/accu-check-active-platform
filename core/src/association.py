"""Handshake de associação com o glicosímetro (APDU ``E2``/``E3``/``E7``).

Fluxo implementado (idêntico ao ``emogenet/accuchek``, fases 1 a 9)::

    1. control transfer GET_STATUS
    2. IN  — pairing request do aparelho      (E2 00)
    3. OUT — pairing confirmation              (E3 00 + 44 B)
    4. IN  — config info (configuração estendida)
    5. OUT — config received confirmation      (E7 00 … 02 01 … 0D 1C)
    6. OUT — MDS attribute request             (E7 00 … 01 03)
    7. IN  — MDS response (modelo, serial, hora do aparelho)
    8. OUT — action request GET_INFO           (E7 00 … 01 07 … 0C 0D)
    9. IN  — action response

⚠️ O aparelho **inicia** a associação: o passo 2 é uma leitura, não uma
escrita. Se a tela mostrar "transferindo dados", o pedido já está na fila.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from . import phdc
from .device import Device, DeviceTimeoutError
from .parser import (
    ConfigInfo,
    decode_bcd,
    parse_config,
    parse_get_response,
    parse_production_spec,
)

logger = logging.getLogger(__name__)

#: Tentativas de leitura do pairing request. O aparelho **inicia** a
#: associação e manda o pedido uma única vez, logo após a conexão USB.
#: Leituras vazias (ZLP) ou timeouts significam "o pedido já foi embora".
PAIRING_REQUEST_ATTEMPTS: Final = 100

#: Pausa entre as tentativas de leitura do pairing request.
PAIRING_REQUEST_DELAY: Final = 0.2


class ProtocolError(RuntimeError):
    """O aparelho respondeu de forma inesperada.

    A mensagem original costuma ser útil: o hexdump já foi logado em DEBUG.
    """


@dataclass
class DeviceInfo:
    """Identificação do aparelho, lida do MDS (handle 0)."""

    model: str | None = None
    serial: str | None = None
    device_time: str | None = None
    raw_attributes: dict[str, bytes] = field(default_factory=dict)


@dataclass
class Session:
    """Estado de uma sessão aberta com o aparelho."""

    device: Device
    invoke_id: int = 0
    config: ConfigInfo | None = None
    pm_store_handle: int | None = None
    num_segments: int | None = None
    info: DeviceInfo = field(default_factory=DeviceInfo)

    def next_invoke_id(self) -> int:
        """Devolve o próximo invoke-id a usar numa pergunta.

        A regra do protocolo é: a próxima pergunta usa ``invoke_id + 1``.
        Errar aqui faz o aparelho **abandonar em silêncio**.
        """
        return self.invoke_id + 1

    def sync_invoke_id(self, response: bytes) -> int:
        """Atualiza o invoke-id a partir da resposta recebida (offset 6)."""
        _, invoke_id = phdc.parse_apdu_header(response)
        logger.debug("invoke-id da resposta: %d", invoke_id)
        self.invoke_id = invoke_id
        return invoke_id


def associate(dev: Device, deadline: float | None = None) -> Session:
    """Executa o handshake completo e devolve a sessão pronta para a leitura.

    Levanta :class:`ProtocolError` se qualquer resposta não for a esperada.

    ``deadline`` é um instante absoluto (``time.monotonic()``)-limite para
    esperar o pairing request do aparelho; sem ele, espera-se o tempo todo.
    """
    session = Session(device=dev)

    # --- passo 1: GET_STATUS (control transfer) ---------------------------
    logger.info("passo 1: GET_STATUS (control transfer)")
    dev.control_get_status()

    # --- passo 2: pairing request (enviado pelo aparelho) ----------------
    logger.info("passo 2: lendo pairing request")
    request = _read_pairing_request(dev, deadline)
    apdu_type, _ = phdc.parse_apdu_header(request)
    if apdu_type != phdc.APDU_TYPE_ASSOCIATION_REQUEST:
        raise ProtocolError(
            f"esperava pairing request (E2 00), veio 0x{apdu_type:04X}: "
            f"{request.hex()}"
        )

    # --- passo 3: pairing confirmation -----------------------------------
    logger.info("passo 3: enviando pairing confirmation")
    dev.bulk_out(phdc.association_response())

    # --- passo 4: config info --------------------------------------------
    logger.info("passo 4: lendo config info")
    config_raw = dev.read_apdu()
    session.sync_invoke_id(config_raw)
    session.config = parse_config(config_raw)
    session.pm_store_handle = session.config.pm_store_handle
    session.num_segments = session.config.num_segments

    if session.pm_store_handle is None:
        raise ProtocolError(
            "objeto PM-Store (MDC_MOC_VMO_PMSTORE) não encontrado no config info; "
            f"objetos vistos: {[o.class_name for o in session.config.objects]}"
        )

    # --- passo 5: config received confirmation ----------------------------
    logger.info("passo 5: enviando config received confirmation")
    dev.bulk_out(phdc.config_confirmation(session.invoke_id))

    # --- passos 6 e 7: atributos do MDS (modelo, serial, hora) ------------
    logger.info("passo 6: requesting MDS attributes")
    dev.bulk_out(phdc.get_request(handle=0, invoke_id=session.next_invoke_id()))

    logger.info("passo 7: reading MDS response")
    mds_raw = dev.read_apdu()
    session.sync_invoke_id(mds_raw)
    session.info = parse_mds_info(mds_raw)

    logger.info(
        "aparelho: modelo=%s serial=%s hora=%s",
        session.info.model,
        session.info.serial,
        session.info.device_time,
    )

    # --- passo 8: action request GET_INFO ---------------------------------
    logger.info("passo 8: action request GET_INFO")
    dev.bulk_out(
        phdc.action_request(
            handle=session.pm_store_handle,
            action=phdc.ACTION_TYPE_MDC_ACT_SEG_GET_INFO,
            action_args=phdc.ACTION_ARGS_SEG_GET_INFO,
            invoke_id=session.next_invoke_id(),
        )
    )

    logger.info("passo 9: reading action response")
    action_raw = dev.read_apdu()
    session.sync_invoke_id(action_raw)

    return session


def _read_pairing_request(dev: Device, deadline: float | None = None) -> bytes:
    """Lê o pairing request, ignorando leituras vazias e timeouts.

    O Accu-Chek Active **reenvia** o pedido de associação (``E2 00``)
    periodicamente (≈ 1 s) enquanto espera a confirmação do host, então
    basta manter a sessão de leitura aberta até ele aparecer. As ZLPs que
    vêm antes são descartadas.
    """
    for attempt in range(1, PAIRING_REQUEST_ATTEMPTS + 1):
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            request = dev.bulk_in()
        except DeviceTimeoutError:
            logger.debug(
                "tentativa %d: nada no endpoint IN (timeout)", attempt
            )
            continue
        if request:
            return request
        logger.debug("tentativa %d: leitura vazia (ZLP)", attempt)
        time.sleep(PAIRING_REQUEST_DELAY)

    raise ProtocolError(
        "o aparelho não mandou o pairing request (E2 00) dentro do prazo. "
        "Deixe o aparelho na tela de transferência de dados e rode o comando "
        "de novo; se ele estiver parado, desligue e ligue o aparelho para "
        "reiniciar o pedido de associação."
    )


def parse_mds_info(buffer: bytes) -> DeviceInfo:
    """Extrai modelo/serial/hora do APDU de resposta do MDS.

    A resposta a um GET traz uma lista de atributos no offset 18 (medido nos
    bytes reais do Active). Cada atributo é ``[class(2)][tamanho(2)][valor]``.
    """
    info = DeviceInfo()
    try:
        attributes = parse_get_response(buffer)
    except ValueError as exc:
        logger.warning("não foi possível parsear a resposta do MDS: %s", exc)
        return info

    for attr_class, value in attributes:
        info.raw_attributes[phdc.mdc_name(attr_class)] = value

        if attr_class == phdc.MDC_ATTR_ID_MODEL:
            info.model = _extract_model(value)
        elif attr_class == phdc.MDC_ATTR_ID_PROD_SPECN:
            info.serial = _extract_serial(value)
        elif attr_class == phdc.MDC_ATTR_TIME_ABS:
            info.device_time = _format_device_time(value)

    if not info.model:
        for attr_class, value in attributes:
            if attr_class == phdc.MDC_ATTR_ID_LABEL_STRING:
                info.model = _decode_text(value)
                break

    return info


def _extract_model(value: bytes) -> str | None:
    """Extrai o modelo do aparelho do atributo ``MDC_ATTR_ID_MODEL``.

    No Active o atributo traz duas cadeias MDER: o fabricante
    (``"Roche"``) e o modelo (``"2102"``). O modelo é o que interessa.
    """
    texts = _decode_mder_strings(value)
    for text in texts:
        if any(char.isdigit() for char in text):
            return text
    return texts[0] if texts else None


def _extract_serial(value: bytes) -> str | None:
    """Extrai o número de série da "production spec" do aparelho.

    O aparelho manda o texto já rotulado (``"serial-number: XXXXXXXXX"``);
    o rótulo é descartado e o que sobra é devolvido.
    """
    entries = parse_production_spec(value)
    text = entries.get("serial-number", "")
    if not text:
        return None
    # Tira o rótulo "serial-number: " (ou similar) que o aparelho prepende.
    stripped = re.sub(r"^[^:]*:\s*", "", text).strip()
    match = re.search(r"\d+", stripped)
    if match:
        return match.group(0)
    return stripped or None


def _format_device_time(value: bytes) -> str | None:
    """Formata o atributo ``MDC_ATTR_TIME_ABS`` (BCD, 7 bytes)."""
    if len(value) < 7:
        return None
    parts = [decode_bcd(byte) for byte in value[:7]]
    try:
        when = datetime(
            parts[0] * 100 + parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
        )
    except ValueError:
        return value.hex()
    return when.isoformat()


def _decode_mder_strings(value: bytes) -> list[str]:
    """Extrai as cadeias de um OCTET STRING do MDER (``[tamanho(2)][texto]``)."""
    strings: list[str] = []
    offset = 0
    while offset + 2 <= len(value):
        length = phdc.be16(value, offset)
        offset += 2
        if length == 0 or offset + length > len(value):
            break
        text = bytes(value[offset : offset + length]).decode("ascii", errors="replace")
        strings.append(text.strip("\x00").strip())
        offset += length
    return strings


def _decode_text(value: bytes) -> str | None:
    """Tenta decodificar um atributo de texto (MDER usa OCTET STRING cru)."""
    if not value:
        return None
    try:
        text = value.decode("ascii", errors="strict").strip("\x00").strip()
    except UnicodeDecodeError:
        return None
    return text or None

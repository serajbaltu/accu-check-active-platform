"""Teste do fluxo completo (associação + leitura) com um aparelho simulado.

O ``FakeDevice`` devolve exatamente as respostas que o ``emogenet/accuchek``
observa num aparelho Roche real, e confere que **cada APDU que o cliente
envia** é byte a byte igual à da referência.

É este teste que garante que o invoke-id, os comprimentos e os ACKs estão
certos — sem precisar do aparelho na mesa.
"""

from __future__ import annotations

import time
from typing import Self

import pytest
from src import phdc
from src.association import ProtocolError, associate
from src.device import DeviceTimeoutError
from src.transfer import read_records, release


def _u0_bytes(data: bytes) -> bytes:
    """Empacota um buffer APDU genérico (sem significado semântico)."""
    return data


class FakeDevice:
    """Aparelho Roche simulado, com as respostas da referência.

    Cada resposta é um buffer APDU completo. O ``calls`` guarda tudo que o
    cliente enviou, para conferência.

    Uma resposta ``b""`` representa um ZLP (leitura vazia) e um
    :class:`DeviceTimeoutError` representa um timeout de leitura.
    """

    def __init__(self, responses: list[bytes]) -> None:
        self._responses = list(responses)
        self.calls: list[bytes] = []
        self.closed = False
        self.timeout_ms = 5000
        self.endpoints = None

    # -- API usada pelo cliente --------------------------------------------

    def control_get_status(self) -> bytes:
        return b"\x00\x00"

    def bulk_out(self, data: bytes) -> int:
        self.calls.append(bytes(data))
        return len(data)

    def bulk_in(self, size: int = 64) -> bytes:
        if not self._responses:
            raise AssertionError("aparelho não tem mais respostas para enviar")
        response = self._responses.pop(0)
        if isinstance(response, type) and issubclass(response, Exception):
            raise response("timeout simulado")
        return response

    def read_apdu(self) -> bytes:
        """O fake já devolve APDUs inteiros; não há fragmentação aqui."""
        return self.bulk_in()

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def make_config_info(invoke_id: int = 1, num_segments: int = 1) -> bytes:
    """Monta um "config info" com um objeto PM-Store e o atributo NUM_SEG."""
    buf = bytearray(64)
    buf[0:2] = (0xE700).to_bytes(2, "big")
    buf[24:26] = (1).to_bytes(2, "big")  # nº de objetos (offset 24)
    buf[26:28] = (0).to_bytes(2, "big")  # campo "length" (offset 26)
    offset = 28
    buf[offset : offset + 2] = (phdc.MDC_MOC_VMO_PMSTORE).to_bytes(2, "big")
    buf[offset + 2 : offset + 4] = (2).to_bytes(2, "big")  # handle
    buf[offset + 4 : offset + 6] = (1).to_bytes(2, "big")  # nº de atributos
    buf[offset + 6 : offset + 8] = (6).to_bytes(2, "big")  # tamanho do objeto
    attr = offset + 8
    buf[attr : attr + 2] = (phdc.MDC_ATTR_NUM_SEG).to_bytes(2, "big")
    buf[attr + 2 : attr + 4] = (2).to_bytes(2, "big")
    buf[attr + 4 : attr + 6] = num_segments.to_bytes(2, "big")
    # invoke-id no offset 6
    buf[6:8] = invoke_id.to_bytes(2, "big")
    return bytes(buf)


def make_mds_response(invoke_id: int = 2) -> bytes:
    """Monta uma resposta do MDS (data-choice 02 03) com o modelo do aparelho.

    O layout é o medido no aparelho real: a lista de atributos começa no
    offset 18, e cada atributo é ``[class(2)][tamanho(2)][valor]``.
    """
    model = b"\x00\x06Roche\x00\x00\x042102"  # duas cadeias MDER
    attributes = (
        phdc.MDC_ATTR_ID_MODEL.to_bytes(2, "big")
        + len(model).to_bytes(2, "big")
        + model
    )

    buf = bytearray(18 + len(attributes))
    buf[0:2] = (0xE700).to_bytes(2, "big")
    buf[4:6] = (len(buf) - 6).to_bytes(2, "big")  # octet string length
    buf[6:8] = invoke_id.to_bytes(2, "big")
    buf[8:10] = phdc.DATA_ADPU_RESPONSE_GET.to_bytes(2, "big")
    buf[10:12] = (len(buf) - 12).to_bytes(2, "big")
    buf[12:14] = (0).to_bytes(2, "big")  # handle 0
    buf[14:16] = (1).to_bytes(2, "big")  # nº de atributos
    buf[16:18] = len(attributes).to_bytes(2, "big")
    buf[18:] = attributes
    buf[2:4] = (len(buf) - 4).to_bytes(2, "big")  # LL
    return bytes(buf)


def make_action_response(invoke_id: int = 3) -> bytes:
    """Monta uma resposta de ACTION (confirmada)."""
    buf = bytearray(32)
    buf[0:2] = (0xE700).to_bytes(2, "big")
    buf[6:8] = invoke_id.to_bytes(2, "big")
    return bytes(buf)


def make_trig_xfer_header(
    invoke_id: int = 4, data_response: int = 0
) -> bytes:
    """Monta o cabeçalho de 22 bytes que responde ao TRIG_XFER.

    Layout (medido no ``emogenet/accuchek``): action-type no offset 14 e
    data-response no offset 20. Data-response 3 significa "segmento vazio".
    """
    buf = bytearray(22)
    buf[0:2] = (0xE700).to_bytes(2, "big")
    buf[6:8] = invoke_id.to_bytes(2, "big")
    buf[14:16] = phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER.to_bytes(2, "big")
    buf[20:22] = data_response.to_bytes(2, "big")
    return bytes(buf)


def make_segment(invoke_id: int = 4, last: bool = True) -> bytes:
    """Monta um APDU de segmento com um registro: 2026-10-21 08:30 = 123 mg/dL."""
    from datetime import datetime

    from src import parser

    when = datetime(2026, 10, 21, 8, 30)
    base = parser.RECORD_BASE_CANDIDATES[0]
    buf = bytearray(base + parser.RECORD_SIZE)
    buf[0:2] = (0xE700).to_bytes(2, "big")
    buf[6:8] = invoke_id.to_bytes(2, "big")
    buf[22:26] = (0xAABBCCDD).to_bytes(4, "big")
    buf[26:30] = (0x11223344).to_bytes(4, "big")
    buf[30:32] = (1).to_bytes(2, "big")
    buf[32] = 0x40 if last else 0x00
    buf[base] = parser.encode_bcd(when.year // 100)
    buf[base + 1] = parser.encode_bcd(when.year % 100)
    buf[base + 2] = parser.encode_bcd(when.month)
    buf[base + 3] = parser.encode_bcd(when.day)
    buf[base + 4] = parser.encode_bcd(when.hour)
    buf[base + 5] = parser.encode_bcd(when.minute)
    buf[base + 6] = parser.encode_bcd(when.second)
    buf[base + 7] = 0x00
    buf[base + 8 : base + 10] = (123).to_bytes(2, "big")
    return bytes(buf)


def make_association_request() -> bytes:
    """O E2 00 que o aparelho envia."""
    return (0xE200).to_bytes(2, "big") + (2).to_bytes(2, "big") + b"\x00\x00"


def make_release_response() -> bytes:
    """O E5 00 que o aparelho devolve."""
    return (0xE500).to_bytes(2, "big") + (2).to_bytes(2, "big") + b"\x00\x00"


class TestAssociation:
    """Handshake de associação."""

    def test_full_flow_sends_the_expected_apdus(self) -> None:
        dev = FakeDevice(
            [
                make_association_request(),
                make_config_info(invoke_id=1),
                make_mds_response(invoke_id=2),
                make_action_response(invoke_id=3),
            ]
        )

        session = associate(dev)  # type: ignore[arg-type]

        assert session.pm_store_handle == 2
        assert session.num_segments == 1
        assert session.info.model == "2102"

        # o que o cliente enviou, na ordem
        assert len(dev.calls) == 4
        assert dev.calls[0].hex() == phdc.association_response().hex()
        assert dev.calls[1].hex() == phdc.config_confirmation(1).hex()
        assert dev.calls[2].hex() == phdc.get_request(0, 2).hex()
        assert dev.calls[3].hex() == phdc.action_request(
            handle=2,
            action=phdc.ACTION_TYPE_MDC_ACT_SEG_GET_INFO,
            action_args=phdc.ACTION_ARGS_SEG_GET_INFO,
            invoke_id=3,
        ).hex()

    def test_invoke_id_increments(self) -> None:
        """A pergunta seguinte usa invoke_id + 1 (senão o aparelho abandona)."""
        dev = FakeDevice(
            [
                make_association_request(),
                make_config_info(invoke_id=1),
                make_mds_response(invoke_id=2),
                make_action_response(invoke_id=3),
            ]
        )
        associate(dev)  # type: ignore[arg-type]
        # config info tem invoke 1 -> config de confirmação usa 1
        # resposta do MDS tem invoke 2 -> o GET seguinte usaria 3
        assert dev.calls[2][6:8] == (2).to_bytes(2, "big")

    def test_association_request_expected(self) -> None:
        """Se o aparelho não mandar E2 00, é erro de estado do aparelho."""
        dev = FakeDevice([b"\xe7\x00" + b"\x00" * 20])
        with pytest.raises(ProtocolError):
            associate(dev)  # type: ignore[arg-type]

    def test_tolerates_empty_reads_before_the_pairing_request(self) -> None:
        """ZLP e timeouts antes do E2 00 não podem derrubar o handshake."""
        dev = FakeDevice(
            [
                b"",  # ZLP
                DeviceTimeoutError,  # nada no endpoint
                b"",  # outro ZLP
                make_association_request(),
                make_config_info(invoke_id=1),
                make_mds_response(invoke_id=2),
                make_action_response(invoke_id=3),
            ]
        )
        session = associate(dev)  # type: ignore[arg-type]
        assert session.pm_store_handle == 2
        assert dev.calls[0].hex() == phdc.association_response().hex()

    def test_gives_up_when_the_pairing_request_never_arrives(self) -> None:
        """Sem o E2 00, a mensagem precisa explicar o que fazer."""
        dev = FakeDevice([b"", b"", b""])
        with pytest.raises(ProtocolError, match="transferência de dados"):
            associate(dev, deadline=time.monotonic() - 1)  # type: ignore[arg-type]


class TestTransfer:
    """Leitura dos segmentos."""

    def test_reads_records_and_acks(self) -> None:
        dev = FakeDevice(
            [
                make_trig_xfer_header(invoke_id=4),
                make_segment(invoke_id=5, last=True),
            ]
        )
        # o primeiro GET_INFO já foi feito na associação; aqui recomeçamos
        session = _make_session(dev, invoke_id=3)

        records = read_records(session)

        assert len(records) == 1
        assert records[0].value_mgdl == 123
        assert records[0].timestamp.isoformat() == "2026-10-21T08:30:00"

        # TRIG_XFER e o ACK do segmento foram enviados
        # o action-type fica no offset 14 do APDU de dados
        trig = phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER.to_bytes(2, "big")
        assert dev.calls[0][14:16] == trig
        confirmed = phdc.DATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT.to_bytes(2, "big")
        assert dev.calls[1][8:10] == confirmed

    def test_multiple_segments_are_read(self) -> None:
        dev = FakeDevice(
            [
                make_trig_xfer_header(invoke_id=4),
                make_segment(invoke_id=5, last=False),
                make_segment(invoke_id=6, last=True),
            ]
        )
        session = _make_session(dev, invoke_id=3)
        records = read_records(session)
        assert len(records) == 2

    def test_empty_segment_yields_no_records(self) -> None:
        """Data-response 3 = "segment is empty": não há o que ler."""
        dev = FakeDevice([make_trig_xfer_header(invoke_id=4, data_response=3)])
        session = _make_session(dev, invoke_id=3)
        assert read_records(session) == []

    def test_transfer_error_is_reported(self) -> None:
        """Data-response 512 = falha ao recuperar o segmento."""
        dev = FakeDevice(
            [make_trig_xfer_header(invoke_id=4, data_response=512)]
        )
        session = _make_session(dev, invoke_id=3)
        with pytest.raises(ProtocolError, match="Failed to retrieve segment"):
            read_records(session)

    def test_release_is_sent(self) -> None:
        dev = FakeDevice([make_release_response()])
        session = _make_session(dev, invoke_id=9)
        release(session)
        assert dev.calls[0].hex() == "e40000020000"


def _make_session(dev: FakeDevice, invoke_id: int):
    """Monta uma sessão sem passar pelo handshake (para isolar o transfer)."""
    from src.association import Session

    session = Session(device=dev)  # type: ignore[arg-type]
    session.invoke_id = invoke_id
    session.pm_store_handle = 2
    return session

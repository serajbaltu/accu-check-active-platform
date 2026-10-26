"""Testes do codec APDU (``src/phdc.py``).

Os valores esperados foram tirados **byte a byte** do ``main.cpp`` do
``emogenet/accuchek`` — a implementação C++ de referência, que funciona com
aparelhos Roche reais.
"""

from __future__ import annotations

import pytest
from src import phdc


def test_association_response_matches_reference() -> None:
    """A pairing confirmation (E3 00) tem que ser byte a byte igual à do emogenet."""
    assert phdc.association_response().hex() == (
        "e300002c000350790026800000028000800000000000000"
        "0800000000008123456780000000000000000000000000000"
    )


def test_association_response_is_48_bytes() -> None:
    """4 bytes de cabeçalho + 44 bytes de payload."""
    assert len(phdc.association_response()) == 48


def test_get_request_matches_reference() -> None:
    """GET de atributos do MDS (handle 0)."""
    assert phdc.get_request(handle=0, invoke_id=1).hex() == (
        "e700000e000c000101030006000000000000"
    )


def test_action_get_info_matches_reference() -> None:
    """ACTION GET_INFO no PM-Store (handle 2)."""
    got = phdc.action_request(
        handle=2,
        action=phdc.ACTION_TYPE_MDC_ACT_SEG_GET_INFO,
        action_args=phdc.ACTION_ARGS_SEG_GET_INFO,
        invoke_id=3,
    )
    assert got.hex() == "e7000014001200030107000c00020c0d0006000100020000"


def test_action_trig_xfer_matches_reference() -> None:
    """ACTION TRIG_XFER no PM-Store (handle 2)."""
    got = phdc.action_request(
        handle=2,
        action=phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER,
        action_args=phdc.ACTION_ARGS_SEG_TRIG_XFER,
        invoke_id=4,
    )
    assert got.hex() == "e7000010000e00040107000800020c1c00020000"


def test_segment_ack_matches_reference() -> None:
    """ACK de segmento, devolvendo u0/u1/u2 lidos do próprio segmento."""
    got = phdc.segment_ack(
        invoke_id=5, store_handle=2, u0=0x11111111, u1=0x22222222, u2=3
    )
    assert got.hex() == (
        "e700001e001c0005020100160002ffffffff0d21000c"
        "111111112222222200030080"
    )


def test_config_confirmation_matches_reference() -> None:
    """ACK da configuração estendida (config-report-id 0x4000)."""
    assert phdc.config_confirmation(invoke_id=7).hex() == (
        "e7000016001400070201000e0000000000000d1c000440000000"
    )


def test_release_request() -> None:
    """E4 00 + 00 00 (normal release)."""
    assert phdc.release_request().hex() == "e400000200 00".replace(" ", "")


@pytest.mark.parametrize(
    ("apdu_type", "expected_name"),
    [
        (phdc.APDU_TYPE_ASSOCIATION_REQUEST, "E2 00"),
        (phdc.APDU_TYPE_ASSOCIATION_RESPONSE, "E3 00"),
        (phdc.APDU_TYPE_ASSOCIATION_RELEASE_REQUEST, "E4 00"),
        (phdc.APDU_TYPE_ASSOCIATION_RELEASE_RESPONSE, "E5 00"),
        (phdc.APDU_TYPE_PRESENTATION_APDU, "E7 00"),
    ],
)
def test_parse_apdu_header_known_types(apdu_type: int, expected_name: str) -> None:
    """parse_apdu_header devolve o tipo correto e invoke-id 0 fora de E7 00."""
    size = 8 if apdu_type == phdc.APDU_TYPE_PRESENTATION_APDU else 4
    data = apdu_type.to_bytes(2, "big") + b"\x00" * (size - 2)
    got_type, got_invoke = phdc.parse_apdu_header(data)
    assert got_type == apdu_type
    assert got_invoke == 0
    assert expected_name  # só para deixar a intenção explícita no teste


def test_parse_apdu_header_reads_invoke_id_at_offset_6() -> None:
    """O invoke-id de um APDU de dados está no offset 6."""
    data = bytes.fromhex("e700001e001c000502010016")
    got_type, got_invoke = phdc.parse_apdu_header(data)
    assert got_type == phdc.APDU_TYPE_PRESENTATION_APDU
    assert got_invoke == 5


def test_parse_apdu_header_rejects_short_buffer() -> None:
    """Buffer de 1 byte não é um APDU válido."""
    with pytest.raises(ValueError):
        phdc.parse_apdu_header(b"\xe7")


def test_set_time_is_marked_forbidden() -> None:
    """SET_TIME (0C 17) está na lista de ações proibidas."""
    assert phdc.ACTION_TYPE_MDC_ACT_SEG_SET_TIME in phdc.FORBIDDEN_ACTIONS
    assert phdc.ACTION_TYPE_MDC_ACT_SEG_SET_TIME not in (
        phdc.ACTION_TYPE_MDC_ACT_SEG_GET_INFO,
        phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER,
    )


def test_mdc_names_are_unique() -> None:
    """Não pode haver dois nomes MDC com o mesmo valor."""
    values = [value for _, value in phdc.MDC_LIST]
    assert len(values) == len(set(values))


def test_mdc_name_lookup() -> None:
    """mdc_name resolve o nome e cai no hex quando não conhece o valor."""
    assert phdc.mdc_name(phdc.MDC_MOC_VMO_PMSTORE) == "MDC_MOC_VMO_PMSTORE"
    assert phdc.mdc_name(0xDEAD) == "0xDEAD"


def test_be16_be32_roundtrip() -> None:
    """put16/be16 e put32/be32 são inversos."""
    for value in (0, 1, 0x1234, 0xFFFF):
        assert phdc.be16(phdc.put16(value)) == value
    for value in (0, 1, 0x12345678, 0xFFFFFFFF):
        assert phdc.be32(phdc.put32(value)) == value

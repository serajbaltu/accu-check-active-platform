"""Testes do parser (``src/parser.py``).

Os segmentos usados aqui reproduzem, byte a byte, o layout dos segmentos
capturados do Accu-Chek Active (``0x21cc``). Como o repositório é
público, os fixtures são **sintéticos** (gerados por
``tools/make_synthetic_fixtures.py``) — mesma estrutura, leituras
fictícias.

⚠️ O layout do Active **não** é o do Guide (``0x21d5``, usado pelo
``emogenet/accuchek``): o registro tem **10 bytes** (e não 12), o segundo
fica em ``+6`` e o valor em ``+8``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from src import association, parser

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    """Lê um fixture hexadecimal (uma linha, sem espaços)."""
    return bytes.fromhex((FIXTURES / name).read_text().strip())


def make_segment(
    entries: list[tuple[datetime, int]],
    last: bool = True,
    base: int | None = None,
) -> bytes:
    """Monta um APDU de segmento sintético, no layout do Active.

    Cada registro tem 10 bytes::

        +0  2 B  ano em BCD (século, ano)
        +2  1 B  mês   (BCD)
        +3  1 B  dia   (BCD)
        +4  1 B  hora  (BCD)
        +5  1 B  minuto (BCD)
        +6  1 B  segundo (BCD)
        +7  1 B  reservado (0x00)
        +8  2 B  valor (uint16 BE, mg/dL)
    """
    if base is None:
        base = parser.RECORD_BASE_CANDIDATES[0]

    buf = bytearray(base + len(entries) * parser.RECORD_SIZE)
    buf[22:26] = (0xAABBCCDD).to_bytes(4, "big")  # u0
    buf[26:30] = (0x11223344).to_bytes(4, "big")  # u1
    buf[30:32] = len(entries).to_bytes(2, "big")  # nº de registros
    buf[32] = 0x40 if last else 0x00  # status do segmento

    offset = base
    for when, value in entries:
        buf[offset] = parser.encode_bcd(when.year // 100)
        buf[offset + 1] = parser.encode_bcd(when.year % 100)
        buf[offset + 2] = parser.encode_bcd(when.month)
        buf[offset + 3] = parser.encode_bcd(when.day)
        buf[offset + 4] = parser.encode_bcd(when.hour)
        buf[offset + 5] = parser.encode_bcd(when.minute)
        buf[offset + 6] = parser.encode_bcd(when.second)
        buf[offset + 7] = 0x00
        buf[offset + 8 : offset + 10] = value.to_bytes(2, "big")
        offset += parser.RECORD_SIZE

    return bytes(buf)


class TestDecodeBcd:
    """Decodificação BCD — o ponto onde o emogenet é frágil."""

    @pytest.mark.parametrize(
        ("byte", "expected"),
        [
            (0x00, 0),
            (0x08, 8),
            (0x10, 10),
            (0x21, 21),
            (0x30, 30),
            (0x59, 59),
            (0x99, 99),
        ],
    )
    def test_valid_bcd(self, byte: int, expected: int) -> None:
        assert parser.decode_bcd(byte) == expected

    def test_nibble_above_nine_does_not_break(self) -> None:
        """O truque do emogenet (sprintf %02X + sscanf %d) quebraria aqui.

        0x1A vem do aparelho quando o nibble alto é 1 e o baixo é A.
        O BCD "corrigido" seria 1*10 + 10 = 20; o truque do C++ devolveria 1.
        """
        assert parser.decode_bcd(0x1A) == 20
        assert parser.decode_bcd(0x5B) == 61


class TestParseSegment:
    """Parse do APDU de segmento."""

    def test_single_record(self) -> None:
        when = datetime(2026, 10, 21, 8, 30, 15)
        segment = parser.parse_segment(make_segment([(when, 123)]))

        assert len(segment.records) == 1
        record = segment.records[0]
        assert record.timestamp == when
        assert record.value_mgdl == 123
        assert record.status == 0
        assert record.is_valid

    def test_multiple_records(self) -> None:
        entries = [
            (datetime(2026, 10, 20, 7, 15, 0), 95),
            (datetime(2026, 10, 20, 12, 5, 30), 180),
            (datetime(2026, 10, 21, 8, 30, 45), 123),
        ]
        segment = parser.parse_segment(make_segment(entries))
        assert len(segment.records) == 3
        assert [r.value_mgdl for r in segment.records] == [95, 180, 123]
        assert [r.timestamp for r in segment.records] == [e[0] for e in entries]

    def test_last_segment_flag(self) -> None:
        segment = parser.parse_segment(
            make_segment([(datetime(2026, 10, 21, 8, 30), 100)], last=True)
        )
        assert segment.is_last

    def test_not_last_segment_flag(self) -> None:
        segment = parser.parse_segment(
            make_segment([(datetime(2026, 10, 21, 8, 30), 100)], last=False)
        )
        assert not segment.is_last

    def test_u0_u1_u2_are_exposed(self) -> None:
        """O ACK precisa devolver ao aparelho exatamente estes valores."""
        segment = parser.parse_segment(
            make_segment([(datetime(2026, 10, 21, 8, 30), 100)])
        )
        assert segment.u0 == 0xAABBCCDD
        assert segment.u1 == 0x11223344
        assert segment.u2 == 1

    def test_empty_segment(self) -> None:
        segment = parser.parse_segment(make_segment([]))
        assert segment.records == []
        assert segment.u2 == 0

    def test_short_buffer_raises(self) -> None:
        with pytest.raises(ValueError):
            parser.parse_segment(b"\x00" * 10)

    def test_invalid_date_is_rejected(self) -> None:
        """Um registro com mês 99 é ilegível e não pode virar uma data.

        Testado no nível da decodificação (não do segmento inteiro) porque a
        detecção de base pode encontrar outra base "plausível" por accidento
        — o que é justamente a robustez que queremos em campo.
        """
        buf = bytearray(make_segment([(datetime(2026, 10, 21, 8, 30), 123)]))
        base = parser.RECORD_BASE_CANDIDATES[0]
        buf[base + 2] = 0x99  # mês inválido
        assert parser._decode_record_at(bytes(buf), base, 0) is None

    def test_invalid_second_is_rejected(self) -> None:
        buf = bytearray(make_segment([(datetime(2026, 10, 21, 8, 30), 123)]))
        base = parser.RECORD_BASE_CANDIDATES[0]
        buf[base + 6] = 0x99  # segundo inválido
        assert parser._decode_record_at(bytes(buf), base, 0) is None

    def test_no_plausible_base_yields_no_records(self) -> None:
        """Se nenhuma base decodificar nada plausível, não há registros."""
        buf = bytearray(make_segment([(datetime(2026, 10, 21, 8, 30), 123)]))
        base = parser.RECORD_BASE_CANDIDATES[0]
        for offset in range(base, base + parser.RECORD_SIZE):
            buf[offset] = 0xFF  # lixo em todos os campos
        segment = parser.parse_segment(bytes(buf))
        assert segment.records == []


class TestFixtureSegments:
    """Segmentos no layout do Accu-Chek Active.

    Os fixtures são **sintéticos**, gerados por
    ``tools/make_synthetic_fixtures.py`` — byte a byte estruturalmente
    idênticos aos capturados no aparelho real, mas com leituras fictícias
    (o repositório é público e os dados de verdade são de saúde).
    """

    def test_segment_with_80_records(self) -> None:
        segment = parser.parse_segment(load_fixture("segment_80.hex"))
        assert segment.u2 == 80
        assert len(segment.records) == 80
        assert not segment.is_last

    def test_segment_with_41_records_is_last(self) -> None:
        segment = parser.parse_segment(load_fixture("segment_41.hex"))
        assert segment.u2 == 41
        assert len(segment.records) == 41
        assert segment.is_last

    def test_first_record_of_fixture_segment(self) -> None:
        """O primeiro registro bate com os bytes do fixture."""
        segment = parser.parse_segment(load_fixture("segment_80.hex"))
        first = segment.records[0]
        assert first.timestamp == datetime(2024, 1, 1, 7, 46, 49)
        assert first.value_mgdl == 114

    def test_all_records_have_plausible_values(self) -> None:
        for name in ("segment_80.hex", "segment_41.hex"):
            segment = parser.parse_segment(load_fixture(name))
            for record in segment.records:
                # 9 mg/dL é o piso do aparelho (e o valor usado para o -INF)
                assert 9 <= record.value_mgdl <= 600
                assert 2019 <= record.timestamp.year <= 2030

    def test_records_are_in_chronological_order(self) -> None:
        segment = parser.parse_segment(load_fixture("segment_80.hex"))
        stamps = [r.timestamp for r in segment.records]
        assert stamps == sorted(stamps)


class TestRecordBaseDetection:
    """A base dos registros é detectada por plausibilidade."""

    def test_detects_standard_base(self) -> None:
        buf = make_segment([(datetime(2026, 10, 21, 8, 30), 123)])
        assert parser.detect_record_base(buf, 1) == 36

    def test_detects_shifted_base(self) -> None:
        """Se o Active mandar os registros 4 bytes adiante, ainda achamos."""
        entries = [(datetime(2026, 10, 21, 8, 30), 123)]
        buf = make_segment(entries, base=40)
        found = parser.detect_record_base(buf, 1)
        assert found == 40

    def test_shifted_base_decodes_correctly(self) -> None:
        """Um segmento com a base deslocada ainda produz a leitura certa."""
        when = datetime(2026, 10, 21, 8, 30)
        segment = parser.parse_segment(make_segment([(when, 123)], base=40))
        assert len(segment.records) == 1
        assert segment.records[0].timestamp == when
        assert segment.records[0].value_mgdl == 123


class TestUnits:
    """Conversão de unidades."""

    def test_mmol_conversion(self) -> None:
        assert parser.mgdl_to_mmol(180) == pytest.approx(10.0)
        assert parser.mgdl_to_mmol(100) == pytest.approx(5.5556, abs=1e-3)


class TestGlucoseRecord:
    """Dataclass de saída."""

    def test_to_dict(self) -> None:
        record = parser.GlucoseRecord(
            timestamp=datetime(2026, 10, 21, 8, 30),
            value_mgdl=123,
            status=0,
        )
        data = record.to_dict()
        assert data["mg/dL"] == 123
        assert data["mmol/L"] == pytest.approx(6.833, abs=1e-3)
        assert data["timestamp"] == "2026-10-21T08:30:00"
        assert "epoch" in data

    def test_out_of_range_is_reported(self) -> None:
        record = parser.GlucoseRecord(
            timestamp=datetime(2026, 10, 21, 8, 30),
            value_mgdl=601,
            status=0,
            out_of_range="high",
        )
        assert record.to_dict()["out_of_range"] == "high"


class TestOutOfRange:
    """Valores +INF / -INF do aparelho."""

    def test_positive_infinity_is_clamped(self) -> None:
        when = datetime(2026, 10, 21, 8, 30)
        segment = parser.parse_segment(
            make_segment([(when, parser.VALUE_POSITIVE_INFINITY)])
        )
        record = segment.records[0]
        assert record.value_mgdl == 601
        assert record.out_of_range == "high"

    def test_negative_infinity_is_clamped(self) -> None:
        when = datetime(2026, 10, 21, 8, 30)
        segment = parser.parse_segment(
            make_segment([(when, parser.VALUE_NEGATIVE_INFINITY)])
        )
        record = segment.records[0]
        assert record.value_mgdl == 9
        assert record.out_of_range == "low"


class TestParseConfig:
    """Parse do APDU de configuração."""

    def test_finds_pm_store_and_num_segments(self) -> None:
        buf = bytearray(80)
        buf[24:26] = (1).to_bytes(2, "big")  # 1 objeto
        buf[26:28] = (0).to_bytes(2, "big")  # campo "length" (ignorado)
        offset = 28
        buf[offset : offset + 2] = (parser.phdc.MDC_MOC_VMO_PMSTORE).to_bytes(2, "big")
        buf[offset + 2 : offset + 4] = (2).to_bytes(2, "big")  # handle
        buf[offset + 4 : offset + 6] = (1).to_bytes(2, "big")  # nº de atributos
        attr_size = 2
        buf[offset + 6 : offset + 8] = (4 + attr_size).to_bytes(2, "big")
        attr = offset + 8
        buf[attr : attr + 2] = (parser.phdc.MDC_ATTR_NUM_SEG).to_bytes(2, "big")
        buf[attr + 2 : attr + 4] = attr_size.to_bytes(2, "big")
        buf[attr + 4 : attr + 6] = (7).to_bytes(2, "big")  # 7 segmentos

        config = parser.parse_config(bytes(buf))
        assert config.pm_store_handle == 2
        assert config.num_segments == 7
        assert config.objects[0].class_name == "MDC_MOC_VMO_PMSTORE"

    def test_short_buffer_raises(self) -> None:
        with pytest.raises(ValueError):
            parser.parse_config(b"\x00" * 4)


class TestParseGetResponse:
    """Parse da resposta a um GET (data-choice 02 03)."""

    def test_fixture_mds_response(self) -> None:
        """A resposta tem 8 atributos, começando no offset 18."""
        buffer = load_fixture("mds_response.hex")
        attributes = parser.parse_get_response(buffer)

        assert len(attributes) == 8
        classes = [cls for cls, _ in attributes]
        assert parser.phdc.MDC_ATTR_ID_MODEL in classes
        assert parser.phdc.MDC_ATTR_ID_PROD_SPECN in classes
        assert parser.phdc.MDC_ATTR_TIME_ABS in classes

    def test_model_attribute(self) -> None:
        buffer = load_fixture("mds_response.hex")
        attributes = dict(parser.parse_get_response(buffer))
        model = attributes[parser.phdc.MDC_ATTR_ID_MODEL]
        assert model == b"\x00\x06Roche\x00\x00\x042102"

    def test_short_buffer_raises(self) -> None:
        with pytest.raises(ValueError):
            parser.parse_get_response(b"\x00" * 4)


class TestParseProductionSpec:
    """Parse da "production spec" (serial, firmware)."""

    def test_fixture_production_spec(self) -> None:
        buffer = load_fixture("mds_response.hex")
        attributes = dict(parser.parse_get_response(buffer))
        entries = parser.parse_production_spec(
            attributes[parser.phdc.MDC_ATTR_ID_PROD_SPECN]
        )
        assert entries["serial-number"] == "serial-number: XXXXXXXXX"
        assert "fw-revision" in entries
        assert entries["fw-revision"].startswith("fw-rev")

    def test_empty_value(self) -> None:
        assert parser.parse_production_spec(b"") == {}


class TestExtractSerial:
    """Extração do número de série a partir da "production spec"."""

    @staticmethod
    def _production_spec(text: str) -> bytes:
        """Monta um valor de production spec com uma entrada de série."""
        payload = text.encode("ascii")
        entry = (
            (1).to_bytes(2, "big")  # tipo = serial-number
            + (0x0409).to_bytes(2, "big")  # idioma
            + len(payload).to_bytes(2, "big")
            + payload
        )
        return (1).to_bytes(2, "big") + len(entry).to_bytes(2, "big") + entry

    def test_digits_are_extracted_from_the_labelled_text(self) -> None:
        value = self._production_spec("serial-number: 123456789")
        assert association._extract_serial(value) == "123456789"

    def test_label_is_stripped_even_without_digits(self) -> None:
        """Série anonimizada (``XXXXXXXXX``) não tem dígitos."""
        value = self._production_spec("serial-number: XXXXXXXXX")
        assert association._extract_serial(value) == "XXXXXXXXX"

    def test_missing_entry_returns_none(self) -> None:
        assert association._extract_serial(b"") is None

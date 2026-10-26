"""Decodificação das estruturas 11073-10417 recebidas do aparelho.

Este módulo é **puro**: recebe bytes e devolve dataclasses. Nada de I/O.

⚠️ O layout do registro **foi medido no Accu-Chek Active** (``0x21cc``) a
partir de bytes reais (ver ``docs/captures/sessao-01/dump2.log``)::

    offset 36 + 10 bytes por registro
    +0..+1  ano em BCD (século, ano)   ex.: 20 20 -> 2020
    +2      mês   (BCD)
    +3      dia   (BCD)
    +4      hora  (BCD)
    +5      minuto (BCD)
    +6      segundo (BCD)
    +7      0x00 (reservado)
    +8..+9  valor em mg/dL (uint16 big-endian)

O Accu-Chek **Guide** (``0x21d5``), que o ``emogenet/accuchek`` usa como
referência, tem registros de **12 bytes** e não traz o segundo. A diferença
está documentada em ``docs/protocol-notes.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from . import phdc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Offsets dentro do APDU de dados "segment stream" (event-type 0D 21)
# ---------------------------------------------------------------------------

SEGMENT_U0_OFFSET: Final = 22
"""uint32 no offset 22 — devolvemos isto no ACK do segmento."""

SEGMENT_U1_OFFSET: Final = 26
"""uint32 no offset 26 — devolvemos isto no ACK do segmento."""

SEGMENT_ENTRY_COUNT_OFFSET: Final = 30
"""uint16 no offset 30 — número de registros do segmento."""

SEGMENT_STATUS_OFFSET: Final = 32
"""Byte no offset 32 — bit ``0x40`` indica "último segmento"."""

#: Base do primeiro registro dentro do APDU do segmento. Medida nos bytes
#: reais do Active: o segmento começa em 36 (depois do cabeçalho de 36 bytes).
SEGMENT_RECORD_BASE: Final = 36

#: Bases candidatas para o primeiro registro do segmento. A primeira que
#: produzir datas plausíveis vence.
RECORD_BASE_CANDIDATES: Final = (36, 34, 38, 32, 40, 30)

RECORD_SIZE: Final = 10
"""Tamanho de cada registro, em bytes (medido no Active)."""

RECORD_DATE_OFFSET: Final = 0
"""Ano (2 bytes BCD) + mês, dia, hora e minuto."""

RECORD_SECOND_OFFSET: Final = 6
"""Segundo da medição, em BCD."""

RECORD_VALUE_OFFSET: Final = 8
"""Valor da glicemia, uint16 big-endian, em mg/dL."""

#: Bit ``0x40`` do status do segmento: não há mais segmentos depois.
SEGMENT_STATUS_LAST: Final = 0x40

#: Valor do status que significa "registro válido" (o C++ só exporta status 0).
RECORD_STATUS_OK: Final = 0x0000

# ---------------------------------------------------------------------------
# Valores fora da faixa de medição
# ---------------------------------------------------------------------------

VALUE_POSITIVE_INFINITY: Final = 0x07FE
"""``+INF`` — o aparelho não consegue ler acima disto (Tidepool: 601 mg/dL)."""

VALUE_NEGATIVE_INFINITY: Final = 0x0802
"""``-INF`` — leitura abaixo do mínimo (Tidepool: 9 mg/dL)."""

VALUE_POSITIVE_INFINITY_CLAMP: Final = 601
"""Substituto para ``+INF``, em mg/dL (mesmo valor do driver do Tidepool)."""

VALUE_NEGATIVE_INFINITY_CLAMP: Final = 9
"""Substituto para ``-INF``, em mg/dL (mesmo valor do driver do Tidepool)."""

# ---------------------------------------------------------------------------
# Offsets dentro do APDU "config info" (event-type 0D 1C)
# ---------------------------------------------------------------------------

CONFIG_OBJECT_COUNT_OFFSET: Final = 24
"""uint16 no offset 24 — número de objetos na configuração."""

CONFIG_OBJECT_HEADER_SIZE: Final = 8
"""class(2) + handle(2) + attr-count(2) + size(2)."""

CONFIG_ATTR_HEADER_SIZE: Final = 4
"""class(2) + size(2)."""

# ---------------------------------------------------------------------------
# Offsets dentro da resposta a um GET (data-choice 02 03)
# ---------------------------------------------------------------------------

GET_ATTR_LIST_OFFSET: Final = 18
"""Começo da lista de atributos na resposta a um GET."""

GET_ATTR_LIST_LENGTH_OFFSET: Final = 16
"""uint16 com o comprimento da lista de atributos."""

# ---------------------------------------------------------------------------
# Decodificação de campos
# ---------------------------------------------------------------------------


def decode_bcd(byte: int) -> int:
    """Decodifica um byte BCD padrão (high nibble = dezenas, low = unidades).

    >>> decode_bcd(0x21)
    21
    >>> decode_bcd(0x10)
    10

    O ``emogenet`` decodifica BCD de um jeito equivalente porém frágil
    (``sprintf("%02X")`` seguido de ``sscanf("%d")``), que quebra se algum
    nibble for maior que 9. Aqui a conta é feita direto.
    """
    return (byte >> 4) * 10 + (byte & 0x0F)


def encode_bcd(value: int) -> int:
    """Codifica um número de 0 a 99 em BCD padrão.

    >>> hex(encode_bcd(21))
    '0x21'
    >>> hex(encode_bcd(10))
    '0x10'
    """
    if not 0 <= value <= 99:
        raise ValueError(f"fora da faixa de BCD: {value}")
    return ((value // 10) << 4) | (value % 10)



def mgdl_to_mmol(value_mgdl: float) -> float:
    """Converte mg/dL para mmol/L (fator 18,0)."""
    return value_mgdl / 18.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Object:
    """Um objeto (classe + handle) da configuração estendida."""

    obj_class: int
    handle: int
    attributes: tuple[tuple[int, bytes], ...] = ()

    @property
    def class_name(self) -> str:
        """Nome MDC da classe do objeto."""
        return phdc.mdc_name(self.obj_class)


@dataclass
class ConfigInfo:
    """Conteúdo do APDU "config info" (``E7 00 … 0D 1C``)."""

    objects: list[Object] = field(default_factory=list)
    pm_store_handle: int | None = None
    num_segments: int | None = None
    raw: bytes = b""

    def find_attribute(self, attr_class: int) -> bytes | None:
        """Devolve o valor bruto do primeiro atributo com a classe pedida."""
        for obj in self.objects:
            for ac, value in obj.attributes:
                if ac == attr_class:
                    return value
        return None


@dataclass(frozen=True)
class GlucoseRecord:
    """Uma leitura de glicemia."""

    timestamp: datetime
    value_mgdl: int
    status: int = RECORD_STATUS_OK
    raw_status: int = 0
    index: int = 0
    out_of_range: str | None = None
    """``"high"``, ``"low"`` ou ``None`` — leitura fora da faixa do aparelho."""

    @property
    def value_mmol(self) -> float:
        """Valor convertido para mmol/L."""
        return mgdl_to_mmol(self.value_mgdl)

    @property
    def is_valid(self) -> bool:
        """True se o registro indica leitura válida.

        O Active não manda um campo de status por registro (ao contrário do
        Guide), então todos os registros são considerados válidos.
        """
        return self.status == RECORD_STATUS_OK

    def to_dict(self) -> dict[str, object]:
        """Representação serializável em JSON."""
        data: dict[str, object] = {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "epoch": int(self.timestamp.timestamp()),
            "mg/dL": self.value_mgdl,
            "mmol/L": round(self.value_mmol, 3),
            "status": self.status,
        }
        if self.out_of_range:
            data["out_of_range"] = self.out_of_range
        return data


@dataclass
class Segment:
    """Um segmento de dados recebido do aparelho."""

    records: list[GlucoseRecord] = field(default_factory=list)
    is_last: bool = False
    u0: int = 0
    u1: int = 0
    u2: int = 0
    raw: bytes = b""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_config(buffer: bytes) -> ConfigInfo:
    """Parseia o APDU "config info" e extrai PM-Store e nº de segmentos.

    O layout é o do ``emogenet``: a partir do offset 24 vem a contagem de
    objetos, e cada objeto tem um cabeçalho de 8 bytes
    (``class, handle, attr-count, size``) seguido da sua lista de atributos
    (``class, size`` + valor, repetidos).
    """
    config = ConfigInfo(raw=bytes(buffer))

    if len(buffer) < CONFIG_OBJECT_COUNT_OFFSET + 2:
        raise ValueError(
            f"config info curto demais: {len(buffer)} byte(s), "
            f"esperado >= {CONFIG_OBJECT_COUNT_OFFSET + 2}"
        )

    count = phdc.be16(buffer, CONFIG_OBJECT_COUNT_OFFSET)
    offset = CONFIG_OBJECT_COUNT_OFFSET + 4  # +4: pula count e o campo "length"

    for _ in range(count):
        if offset + CONFIG_OBJECT_HEADER_SIZE > len(buffer):
            logger.warning(
                "config info truncado no offset %d (de %d objeto(s))",
                offset,
                count,
            )
            break

        obj_class = phdc.be16(buffer, offset)
        handle = phdc.be16(buffer, offset + 2)
        attr_count = phdc.be16(buffer, offset + 4)
        obj_size = phdc.be16(buffer, offset + 6)
        offset += CONFIG_OBJECT_HEADER_SIZE

        attributes: list[tuple[int, bytes]] = []
        attr_offset = offset
        for _ in range(attr_count):
            if attr_offset + CONFIG_ATTR_HEADER_SIZE > len(buffer):
                logger.warning("lista de atributos truncada no offset %d", attr_offset)
                break
            attr_class = phdc.be16(buffer, attr_offset)
            attr_size = phdc.be16(buffer, attr_offset + 2)
            value_start = attr_offset + CONFIG_ATTR_HEADER_SIZE
            value = bytes(buffer[value_start : value_start + attr_size])
            attributes.append((attr_class, value))
            attr_offset += CONFIG_ATTR_HEADER_SIZE + attr_size

        config.objects.append(Object(obj_class, handle, tuple(attributes)))
        offset += obj_size

    for obj in config.objects:
        if obj.obj_class == phdc.MDC_MOC_VMO_PMSTORE:
            config.pm_store_handle = obj.handle
            for attr_class, value in obj.attributes:
                if attr_class == phdc.MDC_ATTR_NUM_SEG and len(value) >= 2:
                    config.num_segments = phdc.be16(value, 0)
            break

    logger.info(
        "config: %d objeto(s), pm_store_handle=%s, num_segments=%s",
        len(config.objects),
        config.pm_store_handle,
        config.num_segments,
    )
    for obj in config.objects:
        logger.info(
            "  objeto %s (handle %d) com %d atributo(s)",
            obj.class_name,
            obj.handle,
            len(obj.attributes),
        )
    return config


def _decode_record_at(
    buffer: bytes, base: int, index: int
) -> GlucoseRecord | None:
    """Decodifica o registro de índice ``index`` na base ``base``.

    Devolve ``None`` se os campos não fizerem sentido (data impossível).
    """
    start = base + index * RECORD_SIZE
    end = start + RECORD_SIZE
    if end > len(buffer):
        return None

    cc = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 0])
    yy = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 1])
    mm = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 2])
    dd = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 3])
    hh = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 4])
    mn = decode_bcd(buffer[start + RECORD_DATE_OFFSET + 5])
    ss = decode_bcd(buffer[start + RECORD_SECOND_OFFSET])

    if not (1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mn <= 59):
        return None
    if ss > 59 or yy > 99 or cc > 99:
        return None

    value = phdc.be16(buffer, start + RECORD_VALUE_OFFSET)

    # A data vem em 6 bytes: cc (século), yy (ano), mm, dd, hh, mn.
    # O emogenet monta o ano como cc*100 + yy.
    year = cc * 100 + yy
    if year < 1900:  #issenza de século no aparelho: assume 20xx
        year = 2000 + yy

    try:
        timestamp = datetime(year, mm, dd, hh, mn, ss)
    except ValueError:
        return None

    out_of_range = None
    if value == VALUE_POSITIVE_INFINITY:
        value = VALUE_POSITIVE_INFINITY_CLAMP
        out_of_range = "high"
    elif value == VALUE_NEGATIVE_INFINITY:
        value = VALUE_NEGATIVE_INFINITY_CLAMP
        out_of_range = "low"

    return GlucoseRecord(
        timestamp=timestamp,
        value_mgdl=value,
        status=RECORD_STATUS_OK,
        index=index,
        out_of_range=out_of_range,
    )


def _score_base(buffer: bytes, count: int, base: int) -> int:
    """Conta quantos registros decodificam de forma plausível na base ``base``."""
    return sum(
        1
        for i in range(count)
        if _decode_record_at(buffer, base, i) is not None
    )


def detect_record_base(buffer: bytes, count: int) -> int | None:
    """Descobre a base do primeiro registro testando as candidatas conhecidas.

    Devolve a base com mais registros plausíveis, ou ``None`` se nenhuma
    servir. Em caso de empate, vence a primeira candidata (a ordem de
    :data:`RECORD_BASE_CANDIDATES` é a do ``emogenet``).
    """
    best_base: int | None = None
    best_score = 0
    for base in RECORD_BASE_CANDIDATES:
        score = _score_base(buffer, count, base)
        logger.debug("base %d: %d registro(s) plausível(is)", base, score)
        if score > best_score:
            best_score = score
            best_base = base
    if best_base is None:
        return None
    logger.info(
        "base dos registros: offset %d (%d/%d registro(s) plausível(is))",
        best_base,
        best_score,
        count,
    )
    return best_base


def parse_get_response(buffer: bytes) -> list[tuple[int, bytes]]:
    """Parseia a resposta a um GET (``data-choice 02 03``).

    A lista de atributos começa no offset 18; cada atributo é
    ``[class(2)][size(2)][valor(size)]``. O comprimento total da lista
    está no offset 16.
    """
    attributes: list[tuple[int, bytes]] = []
    if len(buffer) < GET_ATTR_LIST_OFFSET:
        raise ValueError(
            f"resposta a GET curta demais: {len(buffer)} byte(s)"
        )

    length = phdc.be16(buffer, GET_ATTR_LIST_LENGTH_OFFSET)
    offset = GET_ATTR_LIST_OFFSET
    end = min(offset + length, len(buffer))

    while offset + CONFIG_ATTR_HEADER_SIZE <= end:
        attr_class = phdc.be16(buffer, offset)
        attr_size = phdc.be16(buffer, offset + 2)
        value_start = offset + CONFIG_ATTR_HEADER_SIZE
        if value_start + attr_size > len(buffer):
            logger.warning("atributo truncado no offset %d", value_start)
            break
        attributes.append(
            (attr_class, bytes(buffer[value_start : value_start + attr_size]))
        )
        offset = value_start + attr_size

    return attributes


#: Nomes das entradas de "production spec" (ISO 11073-20601), na ordem em
#: que o aparelho as usa (mesma lista do ``utils.js`` do Tidepool).
PROD_SPEC_ENTRIES: Final = (
    "unspecified",
    "serial-number",
    "part-number",
    "hw-revision",
    "sw-revision",
    "fw-revision",
    "protocol-revision",
    "prod-spec-gmdn",
)

#: Cabeçalho de cada entrada de "production spec": tipo(2) + idioma(2) +
#: tamanho do texto(2).
PROD_SPEC_ENTRY_HEADER_SIZE: Final = 6


def parse_production_spec(value: bytes) -> dict[str, str]:
    """Parseia o atributo ``MDC_ATTR_ID_PROD_SPECN``.

    Layout medido nos bytes reais do Active
    (``docs/captures/sessao-01/dump2.log``)::

        [contagem(2)][comprimento-total(2)]
        [tipo(2)][?2][tamanho(2)][texto(tamanho)]   x contagem

    O ``tipo`` segue a tabela ``prd_spec_type`` do ISO 11073-20601 (a mesma
    do ``utils.js`` do Tidepool): 1 = ``serial-number``, 5 = ``fw-revision``.
    O campo ``?`` (2 bytes) parece ser o código de idioma e é ignorado.
    """
    entries: dict[str, str] = {}
    if len(value) < 4:
        return entries

    count = phdc.be16(value, 0)
    offset = 4
    for _ in range(count):
        if offset + PROD_SPEC_ENTRY_HEADER_SIZE > len(value):
            break
        type_index = phdc.be16(value, offset)
        length = phdc.be16(value, offset + 4)
        start = offset + PROD_SPEC_ENTRY_HEADER_SIZE
        if start + length > len(value):
            break
        text = bytes(value[start : start + length]).decode("ascii", errors="replace")
        name = (
            PROD_SPEC_ENTRIES[type_index]
            if type_index < len(PROD_SPEC_ENTRIES)
            else f"entry-{type_index}"
        )
        entries.setdefault(name, text.strip())
        offset = start + length

    return entries


def parse_segment(buffer: bytes) -> Segment:
    """Parseia o APDU de dados de um segmento (``E7 00 … 0D 21``)."""
    segment = Segment(raw=bytes(buffer))

    if len(buffer) < SEGMENT_ENTRY_COUNT_OFFSET + 2:
        raise ValueError(
            f"segmento curto demais: {len(buffer)} byte(s), "
            f"esperado >= {SEGMENT_ENTRY_COUNT_OFFSET + 2}"
        )

    count = phdc.be16(buffer, SEGMENT_ENTRY_COUNT_OFFSET)
    has_u0 = len(buffer) >= SEGMENT_U0_OFFSET + 4
    has_u1 = len(buffer) >= SEGMENT_U1_OFFSET + 4
    segment.u0 = phdc.be32(buffer, SEGMENT_U0_OFFSET) if has_u0 else 0
    segment.u1 = phdc.be32(buffer, SEGMENT_U1_OFFSET) if has_u1 else 0
    segment.u2 = count
    segment.is_last = bool(
        len(buffer) > SEGMENT_STATUS_OFFSET
        and buffer[SEGMENT_STATUS_OFFSET] & SEGMENT_STATUS_LAST
    )

    if count == 0:
        logger.info("segmento vazio (0 registro(s))")
        return segment

    base = detect_record_base(buffer, count)
    if base is None:
        logger.warning("não foi possível localizar os registros do segmento")
        return segment

    for i in range(count):
        record = _decode_record_at(buffer, base, i)
        if record is None:
            logger.warning("registro %d ilegível (base %d)", i, base)
            continue
        segment.records.append(record)
    logger.info(
        "segmento: %d registro(s) (de %d declarados), último=%s",
        len(segment.records),
        count,
        segment.is_last,
    )
    for record in segment.records:
        logger.info(
            "  %s => %d mg/dL (%.3f mmol/L) status=0x%04x",
            record.timestamp.isoformat(),
            record.value_mgdl,
            record.value_mmol,
            record.status,
        )
    return segment

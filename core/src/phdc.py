"""Constantes e codec APDU do PHDC (ISO/IEEE 11073-20601 / 11073-10417).

Este módulo é **puro**: só constantes e funções de encode/decode, sem I/O e
sem import de ``usb``. Tudo aqui é testável sem hardware.

Fontes das constantes:

* ``Tidepool``  — driver JS ``lib/drivers/roche/accuChekUSB.js`` do
  repositório ``tidepool-org/uploader``. Foi de onde o protocolo foi
  originalmente descrito.
* ``emogenet``  — port C++17/libusb-1.0 do driver acima, repositório
  ``https://github.com/emogenet/accuchek`` (arquivo ``main.cpp``). É a
  referência mais completa: traz o fluxo APDU inteiro com hexdump de cada fase.
* ``ISO 11073`` — nomenclatura padrão (MDC) para o que não está nos dois acima.
"""

from __future__ import annotations

import struct
from typing import Final

# ---------------------------------------------------------------------------
# Tipos de APDU (campo de 2 bytes, big-endian, no início de toda mensagem)
# ---------------------------------------------------------------------------

APDU_TYPE_ASSOCIATION_REQUEST: Final = 0xE200
"""``E2 00`` — pedido de associação. **Enviado pelo aparelho**, não por nós."""

APDU_TYPE_ASSOCIATION_RESPONSE: Final = 0xE300
"""``E3 00`` — resposta de associação (pairing confirmation). Enviado por nós."""

APDU_TYPE_ASSOCIATION_RELEASE_REQUEST: Final = 0xE400
"""``E4 00`` — pedido de encerramento da associação. Enviado por nós."""

APDU_TYPE_ASSOCIATION_RELEASE_RESPONSE: Final = 0xE500
"""``E5 00`` — confirmação de encerramento. Enviado pelo aparelho."""

APDU_TYPE_ASSOCIATION_ABORT: Final = 0xE600
"""``E6 00`` — abort. **NUNCA enviar** neste projeto."""

APDU_TYPE_PRESENTATION_APDU: Final = 0xE700
"""``E7 00`` — APDU de dados (GET, ACTION, eventos, ACKs)."""

# ---------------------------------------------------------------------------
# Data choices (2 bytes, offset 8 do APDU de dados)
# ---------------------------------------------------------------------------

DATA_ADPU_INVOKE_EVENT_NOTIFICATION: Final = 0x0101
"""Notificação do aparelho, aguardando ACK."""

DATA_ADPU_INVOKE_GET: Final = 0x0103
"""Leitura de atributos (GET)."""

DATA_ADPU_INVOKE_CONFIRMED_ACTION: Final = 0x0107
"""Ação confirmada (ACTION) — GET_INFO, TRIG_XFER, SET_TIME…"""

DATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT: Final = 0x0201
"""ACK de notificação — também usado para confirmar config e segmento."""

DATA_ADPU_RESPONSE_GET: Final = 0x0203
"""Resposta a um GET."""

DATA_ADPU_RESPONSE_CONFIRMED_ACTION: Final = 0x0207
"""Resposta a uma ACTION."""

# ---------------------------------------------------------------------------
# Event types (2 bytes)
# ---------------------------------------------------------------------------

EVENT_TYPE_MDC_NOTI_CONFIG: Final = 0x0D1C
"""``MDC_NOTI_CONFIG`` — o aparelho anuncia sua configuração estendida."""

EVENT_TYPE_MDC_NOTI_SEGMENT_DATA: Final = 0x0D21
"""``MDC_NOTI_SEGMENT_DATA`` — o aparelho anuncia os dados de um segmento."""

# ---------------------------------------------------------------------------
# Action types (2 bytes)
# ---------------------------------------------------------------------------

ACTION_TYPE_MDC_ACT_SEG_GET_INFO: Final = 0x0C0D
"""``MDC_ACT_SEG_GET_INFO`` — pede informações de um segmento."""

ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER: Final = 0x0C1C
"""``MDC_ACT_SEG_TRIG_XFER`` — dispara a transferência de um segmento."""

ACTION_TYPE_MDC_ACT_SEG_GET_ID_LIST: Final = 0x0C1E
"""``MDC_ACT_SEG_GET_ID_LIST`` — pede a lista de segmentos."""

ACTION_TYPE_MDC_ACT_SEG_SET_TIME: Final = 0x0C17
"""``MDC_ACT_SEG_SET_TIME`` — **PROIBIDO**: define o relógio do aparelho.

O driver do Tidepool usa isto para sincronizar a hora. Este projeto é
somente leitura e não deve alterar o relógio interno do dispositivo.
"""

# ---------------------------------------------------------------------------
# Códigos de resposta (data-response, offset 20 do APDU de resposta)
# ---------------------------------------------------------------------------

DATA_RESPONSE_TRANSFER_SUCCESSFUL: Final = 0
"""Transferência concluída com sucesso."""

DATA_RESPONSE_NO_SUCH_SEGMENT: Final = 1
"""Não existe o segmento pedido."""

DATA_RESPONSE_TRY_AGAIN_LATER: Final = 2
"""O aparelho pede para tentar de novo mais tarde."""

DATA_RESPONSE_SEGMENT_EMPTY: Final = 3
"""O segmento pedido existe, mas está vazio (sem leituras)."""

DATA_RESPONSE_FAILED_TO_RETRIEVE: Final = 512
"""Falha ao recuperar o segmento."""


def data_response_name(code: int) -> str:
    """Devolve um nome legível para um código de data-response.

    >>> data_response_name(3)
    'Segment is empty'
    """
    return {
        DATA_RESPONSE_TRANSFER_SUCCESSFUL: "Transfer successful",
        DATA_RESPONSE_NO_SUCH_SEGMENT: "No such segment",
        DATA_RESPONSE_TRY_AGAIN_LATER: "Try again later",
        DATA_RESPONSE_SEGMENT_EMPTY: "Segment is empty",
        DATA_RESPONSE_FAILED_TO_RETRIEVE: "Failed to retrieve segment",
    }.get(code, f"Unknown ({code})")

#: Ações que este cliente jamais pode enviar.
FORBIDDEN_ACTIONS: Final = frozenset({ACTION_TYPE_MDC_ACT_SEG_SET_TIME})

# ---------------------------------------------------------------------------
# Nomenclatura MDC (objetos, classes e atributos)
# ---------------------------------------------------------------------------

MDC_LIST: Final[tuple[tuple[str, int], ...]] = (
    ("MDC_MOC_VMO_METRIC", 4),
    ("MDC_MOC_VMO_METRIC_ENUM", 5),
    ("MDC_MOC_VMO_METRIC_NU", 6),
    ("MDC_MOC_VMO_METRIC_SA_RT", 9),
    ("MDC_MOC_SCAN", 16),
    ("MDC_MOC_SCAN_CFG", 17),
    ("MDC_MOC_SCAN_CFG_EPI", 18),
    ("MDC_MOC_SCAN_CFG_PERI", 19),
    ("MDC_MOC_VMS_MDS_SIMP", 37),
    ("MDC_MOC_VMO_PMSTORE", 61),
    ("MDC_MOC_PM_SEGMENT", 62),
    ("MDC_ATTR_CONFIRM_MODE", 2323),
    ("MDC_ATTR_CONFIRM_TIMEOUT", 2324),
    ("MDC_ATTR_TRANSPORT_TIMEOUT", 2694),
    ("MDC_ATTR_ID_HANDLE", 2337),
    ("MDC_ATTR_ID_INSTNO", 2338),
    ("MDC_ATTR_ID_LABEL_STRING", 2343),
    ("MDC_ATTR_ID_MODEL", 2344),
    ("MDC_ATTR_ID_PHYSIO", 2347),
    ("MDC_ATTR_ID_PROD_SPECN", 2349),
    ("MDC_ATTR_ID_TYPE", 2351),
    ("MDC_ATTR_METRIC_STORE_CAPAC_CNT", 2369),
    ("MDC_ATTR_METRIC_STORE_SAMPLE_ALG", 2371),
    ("MDC_ATTR_METRIC_STORE_USAGE_CNT", 2372),
    ("MDC_ATTR_MSMT_STAT", 2375),
    ("MDC_ATTR_NU_ACCUR_MSMT", 2378),
    ("MDC_ATTR_NU_CMPD_VAL_OBS", 2379),
    ("MDC_ATTR_NU_VAL_OBS", 2384),
    ("MDC_ATTR_NUM_SEG", 2385),
    ("MDC_ATTR_OP_STAT", 2387),
    ("MDC_ATTR_POWER_STAT", 2389),
    ("MDC_ATTR_SA_SPECN", 2413),
    ("MDC_ATTR_SCALE_SPECN_I16", 2415),
    ("MDC_ATTR_SCALE_SPECN_I32", 2416),
    ("MDC_ATTR_SCALE_SPECN_I8", 2417),
    ("MDC_ATTR_SCAN_REP_PD", 2421),
    ("MDC_ATTR_SEG_USAGE_CNT", 2427),
    ("MDC_ATTR_SYS_ID", 2436),
    ("MDC_ATTR_SYS_TYPE", 2438),
    ("MDC_ATTR_TIME_ABS", 2439),
    ("MDC_ATTR_TIME_BATT_REMAIN", 2440),
    ("MDC_ATTR_TIME_END_SEG", 2442),
    ("MDC_ATTR_TIME_PD_SAMP", 2445),
    ("MDC_ATTR_TIME_REL", 2447),
    ("MDC_ATTR_TIME_STAMP_ABS", 2448),
    ("MDC_ATTR_TIME_STAMP_REL", 2449),
    ("MDC_ATTR_TIME_START_SEG", 2450),
    ("MDC_ATTR_TX_WIND", 2453),
    ("MDC_ATTR_UNIT_CODE", 2454),
    ("MDC_ATTR_UNIT_LABEL_STRING", 2457),
    ("MDC_ATTR_VAL_BATT_CHARGE", 2460),
    ("MDC_ATTR_VAL_ENUM_OBS", 2462),
    ("MDC_ATTR_TIME_REL_HI_RES", 2536),
    ("MDC_ATTR_TIME_STAMP_REL_HI_RES", 2537),
    ("MDC_ATTR_DEV_CONFIG_ID", 2628),
    ("MDC_ATTR_MDS_TIME_INFO", 2629),
    ("MDC_ATTR_METRIC_SPEC_SMALL", 2630),
    ("MDC_ATTR_SOURCE_HANDLE_REF", 2631),
    ("MDC_ATTR_SIMP_SA_OBS_VAL", 2632),
    ("MDC_ATTR_ENUM_OBS_VAL_SIMP_OID", 2633),
    ("MDC_ATTR_ENUM_OBS_VAL_SIMP_STR", 2634),
    ("MDC_REG_CERT_DATA_LIST", 2635),
    ("MDC_ATTR_NU_VAL_OBS_BASIC", 2636),
    ("MDC_ATTR_PM_STORE_CAPAB", 2637),
    ("MDC_ATTR_PM_SEG_MAP", 2638),
    ("MDC_ATTR_PM_SEG_PERSON_ID", 2639),
    ("MDC_ATTR_SEG_STATS", 2640),
    ("MDC_ATTR_SEG_FIXED_DATA", 2641),
    ("MDC_ATTR_SCAN_HANDLE_ATTR_VAL_MAP", 2643),
    ("MDC_ATTR_SCAN_REP_PD_MIN", 2644),
    ("MDC_ATTR_ATTRIBUTE_VAL_MAP", 2645),
    ("MDC_ATTR_NU_VAL_OBS_SIMP", 2646),
    ("MDC_ATTR_PM_STORE_LABEL_STRING", 2647),
    ("MDC_ATTR_PM_SEG_LABEL_STRING", 2648),
    ("MDC_ATTR_TIME_PD_MSMT_ACTIVE", 2649),
    ("MDC_ATTR_SYS_TYPE_SPEC_LIST", 2650),
    ("MDC_ATTR_METRIC_ID_PART", 2655),
    ("MDC_ATTR_ENUM_OBS_VAL_PART", 2656),
    ("MDC_ATTR_SUPPLEMENTAL_TYPES", 2657),
    ("MDC_ATTR_TIME_ABS_ADJUST", 2658),
    ("MDC_ATTR_CLEAR_TIMEOUT", 2659),
    ("MDC_ATTR_TRANSFER_TIMEOUT", 2660),
    ("MDC_ATTR_ENUM_OBS_VAL_SIMP_BIT_STR", 2661),
    ("MDC_ATTR_ENUM_OBS_VAL_SIMP_BASIC_BIT_STR", 2662),
    ("MDC_ATTR_NU_CMPD_VAL_OBS_BASIC", 2677),
    ("MDC_ATTR_NU_CMPD_VAL_OBS_SIMP", 2676),
    ("MDC_ATTR_ID_PHYSIO_LIST", 2678),
    ("MDC_ATTR_SCAN_HANDLE_LIST", 2679),
    ("MDC_ATTR_TIME_BO", 2689),
    ("MDC_ATTR_TIME_STAMP_BO", 2690),
    ("MDC_ATTR_TIME_START_SEG_BO", 2691),
    ("MDC_ATTR_TIME_END_SEG_BO", 2692),
    ("MDC_ATTR_TIME_STAMP_BO", 2693),
    ("MDC_ATTR_INPUT_DEVTYPE_LIST", 2674),
    ("MDC_ATTR_UNIT_SPECN", 2422),
)
"""Constantes MDC extraídas do ``MDC_LIST`` do ``emogenet/accuchek``.

O C++ usa a técnica das X-macros para gerar a enumeração e uma função de
busca reversa; aqui a mesma lista vira uma tupla de pares.
"""

#: Índice reverso valor -> nome, para log legível.
MDC_BY_VALUE: Final[dict[int, str]] = {value: name for name, value in MDC_LIST}

#: Objetos/atributos usados no fluxo deste cliente.
MDC_MOC_VMS_MDS_SIMP: Final = 37
"""Medical Device System simplificado — o próprio aparelho (handle 0)."""

MDC_MOC_VMO_PMSTORE: Final = 61
"""Persistent Metric Store — a memória onde ficam as leituras."""

MDC_ATTR_NUM_SEG: Final = 2385
"""Quantidade de segmentos no PM-Store."""

MDC_ATTR_SEG_USAGE_CNT: Final = 2427
"""Quantidade de entradas em um segmento."""

MDC_ATTR_TIME_ABS: Final = 2439
"""Relógio do aparelho (data/hora absolutas)."""

MDC_ATTR_ID_MODEL: Final = 2344
"""Modelo do aparelho."""

MDC_ATTR_ID_PROD_SPECN: Final = 2349
"""Production specification — lista com serial number, fw-revision etc."""

MDC_ATTR_ID_LABEL_STRING: Final = 2343
"""Rótulo (nome) do objeto."""

MDC_CTXT_GLU_MEAL_FASTING: Final = 29268
"""Marcador de contexto "em jejum".

Fonte: nomenclatura ISO 11073-20601, citada no artigo do ``emogenet``.
Não foi observado nos bytes do Active — tratar como não verificado.
"""

# ---------------------------------------------------------------------------
# Códigos de resultado
# ---------------------------------------------------------------------------

CONFIG_REPORT_ID_EXTENDED_CONFIG_START: Final = 0x4000
"""``config-report-id`` que significa "início da configuração estendida"."""

CONFIG_RESULT_ACCEPTED_CONFIG: Final = 0x0000
"""``config-result``: configuração aceita."""

ACCEPTED_UNKNOWN_CONFIG: Final = 0x0003
"""Escolha de associação: aceitamos configuração desconhecida."""

DATA_PROTO_ID_11073: Final = 20601
"""``data-proto-id``: ISO/IEEE 11073-20601."""

PROTOCOL_VERSION_1: Final = 0x80000002
"""``protocolVersion``: 1, com o bit "prefers negotiation" ligado."""

ENCODING_RULES_MDER: Final = 0x8000
"""``encoding-rules``: MDER (Medical Device Encoding Rules)."""

NOMENCLATURE_VERSION: Final = 0x80000000
"""``nomenclatureVersion``."""

SYSTEM_TYPE_MANAGER: Final = 0x80000000
"""``systemType``: o PC é o gerenciador da associação."""


# ---------------------------------------------------------------------------
# Codec — inteiros big-endian
# ---------------------------------------------------------------------------


def be16(data: bytes, offset: int = 0) -> int:
    """Lê um ``uint16`` big-endian em ``data[offset:]``."""
    return struct.unpack_from(">H", data, offset)[0]


def be32(data: bytes, offset: int = 0) -> int:
    """Lê um ``uint32`` big-endian em ``data[offset:]``."""
    return struct.unpack_from(">I", data, offset)[0]


def put16(value: int) -> bytes:
    """Codifica um ``uint16`` big-endian."""
    return struct.pack(">H", value)


def put32(value: int) -> bytes:
    """Codifica um ``uint32`` big-endian."""
    return struct.pack(">I", value)


def mdc_name(value: int) -> str:
    """Devolve o nome MDC correspondente a ``value`` (ou ``"0x%04X"``)."""
    return MDC_BY_VALUE.get(value, f"0x{value:04X}")


# ---------------------------------------------------------------------------
# Construção de APDUs
# ---------------------------------------------------------------------------


def association_response() -> bytes:
    """Monta a "pairing confirmation" (``E3 00``) que o aparelho espera.

    Payload de 44 bytes, idêntico ao que o ``emogenet/accuchek`` envia:
    aceitamos configuração desconhecida, protocolo 11073-20601, codificação
    MDER e o PC se declara como *manager* da associação.
    """
    body = b"".join(
        (
            put16(ACCEPTED_UNKNOWN_CONFIG),
            put16(DATA_PROTO_ID_11073),
            put16(38),  # comprimento do bloco de informação de protocolo
            put32(PROTOCOL_VERSION_1),
            put16(ENCODING_RULES_MDER),
            put32(NOMENCLATURE_VERSION),
            put32(0),  # functionalUnits: associação normal
            put32(SYSTEM_TYPE_MANAGER),
            put16(8),  # tamanho do system-id
            put32(0x12345678),  # system-id high
            put32(0),
            put32(0),
            put32(0),
            put16(0),
        )
    )
    assert len(body) == 44, len(body)
    return put16(APDU_TYPE_ASSOCIATION_RESPONSE) + put16(len(body)) + body


def presentation(
    data_choice: int,
    payload: bytes,
    invoke_id: int,
) -> bytes:
    """Monta um APDU de dados (``E7 00``).

    Estrutura (ISO 11073-20601, codificação MDER)::

        E7 00 | LL LL | OO OO | II II | DD DD | payload…

        LL = comprimento total a partir do campo LL (= OO + 2)
        OO = comprimento da "octet string" (invoke-id + data-choice + payload)
        II = invoke-id
        DD = data-choice

    O campo ``LL`` é sempre ``OO + 2`` — confirmado nos quatro tipos de APDU
    medidos no ``emogenet/accuchek`` (GET, ACTION, ACK de config, ACK de
    segmento). Note que ``LL`` **não** inclui o próprio campo ``OO``, e sim
    o campo ``OO`` mais a octet string.

    ``payload`` é o conteúdo que vem **depois** do data-choice.
    """
    inner = put16(invoke_id) + put16(data_choice) + payload
    return (
        put16(APDU_TYPE_PRESENTATION_APDU)
        + put16(len(inner) + 2)
        + put16(len(inner))
        + inner
    )


def get_request(handle: int = 0, invoke_id: int = 0) -> bytes:
    """Monta um GET de atributos (data-choice ``01 03``) do objeto ``handle``.

    O "data-append" de um GET é::

        [length-of-attribute-list(2)][handle(2)][current-time(4)][atributos…]

    O comprimento cobre tudo depois dele. Como pedimos a lista vazia, ele
    vale 6 (handle + current-time).
    """
    payload = put16(6) + put16(handle) + put32(0)
    return presentation(DATA_ADPU_INVOKE_GET, payload, invoke_id)


def action_request(
    handle: int,
    action: int,
    action_args: bytes = b"",
    invoke_id: int = 0,
) -> bytes:
    """Monta uma ACTION (data-choice ``01 07``).

    O "data-append" de uma ACTION é::

        [length-of-action-argument-list(2)][handle(2)][action-type(2)][args…]

    O comprimento cobre handle + action-type + argumentos, ou seja
    ``4 + len(action_args)``.
    """
    payload = put16(4 + len(action_args)) + put16(handle) + put16(action) + action_args
    return presentation(DATA_ADPU_INVOKE_CONFIRMED_ACTION, payload, invoke_id)


#: Argumentos da ação ``MDC_ACT_SEG_GET_INFO``: todos os segmentos.
#: Estrutura: [scope-length(2)][scope(2)][attr-length(2)][attr(2)]
ACTION_ARGS_SEG_GET_INFO: Final = put16(6) + put16(1) + put16(2) + put16(0)

#: Argumentos da ação ``MDC_ACT_SEG_TRIG_XFER``: transfer o segmento 0.
#: Estrutura: [segment-length(2)][segment(2)]
ACTION_ARGS_SEG_TRIG_XFER: Final = put16(2) + put16(0)


def config_confirmation(invoke_id: int = 0) -> bytes:
    """Monta o ACK de configuração (``02 01`` + evento ``0D 1C``).

    Conteúdo: ``config-report-id = 0x4000`` (início da configuração estendida)
    e ``config-result = 0`` (configuração aceita).

    O "event report" tem a forma::

        [length-of-content(2)][handle(2)][time(4)][event-type(2)]
        [length-of-contents(2)][contents]

    com ``length-of-content`` = 10 + ``len(contents)``.
    """
    contents = put16(CONFIG_REPORT_ID_EXTENDED_CONFIG_START) + put16(
        CONFIG_RESULT_ACCEPTED_CONFIG
    )
    payload = (
        put16(10 + len(contents))  # length-of-content
        + put16(0)  # handle
        + put32(0)  # current time
        + put16(EVENT_TYPE_MDC_NOTI_CONFIG)
        + put16(len(contents))
        + contents
    )
    return presentation(DATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT, payload, invoke_id)


def segment_ack(
    invoke_id: int,
    store_handle: int,
    u0: int,
    u1: int,
    u2: int,
) -> bytes:
    """Monta o ACK de um segmento de dados (``02 01`` + evento ``0D 21``).

    ``u0``/``u1``/``u2`` são os valores lidos do próprio segmento e precisam
    ser devolvidos ao aparelho.

    Estrutura (medida no ``emogenet/accuchek``)::

        [length-of-content(2)][handle(2)][time(4)][event-type(2)]
        [length-of-contents(2)][u0(4)][u1(4)][u2(2)][00 80(2)]

    O flag final ``00 80`` ("data received") fica **dentro** do conteúdo
    (``length-of-contents`` = 12), e ``length-of-content`` = 22.
    """
    contents = put32(u0) + put32(u1) + put16(u2) + put16(0x0080)
    payload = (
        put16(10 + len(contents))  # length-of-content
        + put16(store_handle)
        + put32(0xFFFFFFFF)  # tempo relativo
        + put16(EVENT_TYPE_MDC_NOTI_SEGMENT_DATA)
        + put16(len(contents))
        + contents
    )
    return presentation(DATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT, payload, invoke_id)





def release_request() -> bytes:
    """Monta o pedido de encerramento da associação (``E4 00`` + ``00 00``)."""
    return put16(APDU_TYPE_ASSOCIATION_RELEASE_REQUEST) + put16(2) + put16(0)


def parse_apdu_header(data: bytes) -> tuple[int, int]:
    """Lê ``(tipo_apdu, invoke_id)`` do início de um APDU.

    Para APDUs de dados (``E7 00``) o invoke-id fica no offset 6. Para os
    demais tipos não há invoke-id — ``0`` é devolvido.
    """
    if len(data) < 2:
        raise ValueError(f"APDU curto demais: {len(data)} byte(s)")
    apdu_type = be16(data, 0)
    if apdu_type == APDU_TYPE_PRESENTATION_APDU:
        if len(data) < 8:
            raise ValueError(f"APDU de dados curto demais: {len(data)} byte(s)")
        return apdu_type, be16(data, 6)
    return apdu_type, 0

"""Gera fixtures e um dataset **sintético** com o mesmo layout dos dados reais.

Por que este script existe
---------------------------
O layout de 10 bytes por registro, o cabeçalho de 36 bytes do segmento e a
estrutura da resposta do MDS só são críveis se vierem de bytes de verdade.
Mas os bytes de verdade **são leituras de glicemia de uma pessoa** — dado de
saúde, com data e hora, que identifica a rotina (quando acorda, quando
come, hipoglicemias) e o aparelho físico (série ``XXXXXXXXX``).

Este script gera um conjunto sintético **byte a byte estruturalmente
idêntico** ao real:

* mesmo APDU (``e7 00 ...``), mesmo comprimento, mesmos campos;
* mesmo cabeçalho de segmento (36 bytes), com o contador, o bit de "último
  segmento" e o ``u1`` calculados igual;
* mesmos 10 bytes por registro: ano BCD (século, ano), mês, dia, hora,
  minuto, segundo BCD, reservado, valor uint16 BE em mg/dL;
* mesma resposta do MDS com os 8 atributos, no mesmo offsets, com o mesmo
  ``MODEL`` (``Roche`` / ``2102``) e o mesmo ``fw-revision`` — só a série e a
  hora do aparelho são trocadas.

Os fixtures e o ``examples/data_sintetico.json`` que ele produz são o que o
repositório versiona. Para um fork que queira os dados de verdade: apague os
fixtures, apague o script e use o aparelho.

Uso::

    python tools/make_synthetic_fixtures.py

Determinístico: a mesma semente sempre gera os mesmos bytes.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

#: Semente do gerador — mudar aqui muda todos os bytes.
SEED = 20261021

#: Início e fim do período coberto pelo dataset sintético.
PERIOD_START = datetime(2024, 1, 1, 0, 0, 0)
PERIOD_END = datetime(2024, 11, 30, 23, 59, 59)

#: Número de registros e de dias com medição.
N_RECORDS = 121
N_MEASURED_DAYS = 60

#: Máximo de registros por segmento (o aparelho segmenta em 80 + resto).
MAX_RECORDS_PER_SEGMENT = 80

#: Série e hora do aparelho usadas no MDS sintético.
SYNTHETIC_SERIAL = "XXXXXXXXX"
SYNTHETIC_DEVICE_TIME = datetime(2024, 12, 1, 9, 15, 0)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLES = ROOT / "examples"


# ---------------------------------------------------------------------------
# Codificação
# ---------------------------------------------------------------------------


def bcd(value: int) -> int:
    """Codifica um número decimal de 0 a 99 em BCD (2 nibbles)."""
    if not 0 <= value <= 99:
        raise ValueError(f"fora do intervalo BCD: {value}")
    return ((value // 10) << 4) | (value % 10)


def encode_record(when: datetime, value_mgdl: int) -> bytes:
    """Codifica um registro no layout de 10 bytes do Accu-Chek Active.

    ``+0..+1`` ano BCD (século, ano) · ``+2`` mês · ``+3`` dia · ``+4`` hora ·
    ``+5`` minuto · ``+6`` segundo · ``+7`` reservado · ``+8..+9`` valor.
    """
    return bytes(
        [
            bcd(when.year // 100),
            bcd(when.year % 100),
            bcd(when.month),
            bcd(when.day),
            bcd(when.hour),
            bcd(when.minute),
            bcd(when.second),
            0x00,
            (value_mgdl >> 8) & 0xFF,
            value_mgdl & 0xFF,
        ]
    )


# ---------------------------------------------------------------------------
# Geração dos dados
# ---------------------------------------------------------------------------


#: (faixa de hora, média, desvio) do valor de glicemia, em mg/dL.
#: Reproduz o comportamento fisiológico: queda de madrugada, pico
#: pós-prandial à hora do almoço e nova elevação à noite.
VALUE_PROFILE = (
    ((0, 5), 96, 17),
    ((5, 9), 118, 21),
    ((9, 15), 143, 31),
    ((15, 18), 124, 24),
    ((18, 24), 139, 29),
)


def _value_for_hour(rng: random.Random, hour: int) -> int:
    """Sorteia um valor de glicemia plausível para a hora do dia.

    O piso é 60 mg/dL: hipoglicemia é injetada de propósito adiante, e
    assim o conjunto final tem um número controlado de eventos.
    """
    for (start, end), mean, sd in VALUE_PROFILE:
        if start <= hour < end:
            return max(60, min(320, int(rng.gauss(mean, sd))))
    return 120


def synthetic_readings(
    count: int = N_RECORDS,
    days: int = N_MEASURED_DAYS,
    seed: int = SEED,
) -> list[tuple[datetime, int]]:
    """Gera leituras plausíveis: horários de rotina e valores realistas.

    A rotina é irregular de propósito: a maioria dos dias tem duas
    medições (jejum ao acordar e à noite), alguns dias têm três (com
    almoço), alguns têm uma só — e de vez em quando há uma medição de
    madrugada, que é o que faz o "efeito dawn" aparecer.
    """
    rng = random.Random(seed)
    span_days = (PERIOD_END.date() - PERIOD_START.date()).days
    measured = sorted(rng.sample(range(span_days), days))

    readings: list[tuple[datetime, int]] = []
    for day_offset in measured:
        day = PERIOD_START + timedelta(days=day_offset)
        profile = rng.random()
        if profile < 0.66:  # jejum + noite
            hours = [rng.randint(5, 9), rng.randint(18, 23)]
        elif profile < 0.90:  # jejum + almoço + noite
            morning = rng.randint(5, 9)
            # o almoço sai 2 a 3 h depois do jejum: é a leitura pós-prandial
            midday = min(15, morning + rng.randint(2, 3))
            hours = [morning, midday, rng.randint(18, 23)]
        elif profile < 0.97:  # uma só, de manhã
            hours = [rng.randint(6, 11)]
        else:  # madrugada — o usuário acordou com sintoma
            hours = [rng.randint(1, 5)]

        for hour in hours:
            when = day.replace(
                hour=hour,
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
            )
            readings.append((when, _value_for_hour(rng, hour)))

    readings.sort(key=lambda item: item[0])

    # Ajusta o total para exatamente `count` leituras, mantendo a ordem.
    if len(readings) > count:
        step = len(readings) / count
        readings = [readings[int(i * step)] for i in range(count)]
    while len(readings) < count:
        extra = readings[len(readings) % max(1, len(readings))]
        readings.append(extra)

    # Hipoglicemias: uma grave e três leves, para o relatório ter o que mostrar.
    for position, value in ((17, 47), (64, 58), (92, 61), (110, 65)):
        readings[position] = (readings[position][0], value)

    readings.sort(key=lambda item: item[0])
    assert len(readings) == count, f"{len(readings)} != {count}"
    return readings


# ---------------------------------------------------------------------------
# Montagem dos APDUs
# ---------------------------------------------------------------------------


def build_segment(
    records: list[tuple[datetime, int]],
    *,
    already_sent: int,
    is_last: bool,
) -> bytes:
    """Monta o APDU de um segmento de dados (``0D 21``).

    O cabeçalho tem 36 bytes e os registros começam no offset 36. Os campos
    que interessam:

    * offset 20-21: comprimento da área de dados (registros + 14);
    * offset 26-29: ``u1`` — quantos registros já foram enviados antes;
    * offset 30-31: número de registros neste segmento;
    * offset 32-33: status — o bit ``0x40`` marca o último segmento;
    * offset 34-35: comprimento da área de registros.
    """
    payload = b"".join(encode_record(when, value) for when, value in records)
    count = len(records)
    status = 0x8000 | (0x4000 if is_last else 0x0000)
    u1 = (already_sent << 16) & 0xFFFFFFFF

    header = bytearray(36)
    header[0:4] = b"\xe7\x00\x00\x00"  # APDU + comprimento (preenchido depois)
    header[6:8] = (already_sent + 1).to_bytes(2, "big")  # invoke-id
    header[8:12] = b"\x01\x01\x01\x03"  # data-choice
    header[12:14] = b"\x00\x05"  #Handles
    header[14:18] = b"\xff\xff\xff\xff"  # handle de contexto
    header[18:20] = b"\x0d\x21"  # EVENT_REPORT: segment data
    header[20:22] = (len(payload) + 14).to_bytes(2, "big")
    header[22:26] = (0).to_bytes(4, "big")  # u0
    header[26:30] = u1.to_bytes(4, "big")
    header[30:32] = count.to_bytes(2, "big")
    header[32:34] = status.to_bytes(2, "big")
    header[34:36] = len(payload).to_bytes(2, "big")

    apdu = bytes(header) + payload
    total = len(apdu)
    apdu = apdu[:2] + (total - 4).to_bytes(2, "big") + apdu[4:]
    return apdu


def build_mds_response(
    serial: str = SYNTHETIC_SERIAL,
    device_time: datetime = SYNTHETIC_DEVICE_TIME,
) -> bytes:
    """Monta a resposta do MDS (data-choice ``02 03``) com 8 atributos.

    A lista de atributos começa no **offset 18**: ``[nº de atributos(2)]``
    ``[comprimento da lista(2)]`` e, para cada atributo,
    ``[classe(2)][tamanho(2)][valor]``.
    """
    model = b"\x00\x06Roche\x00\x00\x042102"
    sys_id = bytes([0x00, 0x08, 0x00, 0x60, 0x19, 0x08, 0x37, 0x03, 0x92, 0x6E])
    dev_config_id = b"\x40\x40"

    entries = [
        (1, 0, f"serial-number: {serial}".encode("ascii")),
        (5, 0, b"fw-rev:   V02.04"),
        (5, 1, b"fw-rev:     V02.04"),
    ]
    prod_spec = (len(entries)).to_bytes(2, "big")
    body = b""
    for entry_type, language, text in entries:
        body += (
            entry_type.to_bytes(2, "big")
            + language.to_bytes(2, "big")
            + len(text).to_bytes(2, "big")
            + text
        )
    prod_spec += len(body).to_bytes(2, "big") + body

    time_abs = bytes(
        [
            bcd(device_time.year // 100),
            bcd(device_time.year % 100),
            bcd(device_time.month),
            bcd(device_time.day),
            bcd(device_time.hour),
            bcd(device_time.minute),
            bcd(device_time.second),
            0x00,
        ]
    )
    mds_time_info = bytes.fromhex("c0001f00ffffffff0064000000000000")
    reg_cert = bytes.fromhex("00020012020100080400000100022011020200020000")
    sys_type = bytes.fromhex("0001000410110002")

    attributes = [
        (0x0928, model),
        (0x0984, sys_id),
        (0x0A44, dev_config_id),
        (0x092D, prod_spec),
        (0x0987, time_abs),
        (0x0A45, mds_time_info),
        (0x0A4B, reg_cert),
        (0x0A5A, sys_type),
    ]

    body = b"".join(
        cls.to_bytes(2, "big") + len(value).to_bytes(2, "big") + value
        for cls, value in attributes
    )

    apdu = bytearray(18)
    apdu[0:4] = b"\xe7\x00\x00\x00"
    apdu[4:6] = b"\x00\xcc"
    apdu[6:8] = b"\x00\x01"  # invoke-id
    apdu[8:10] = b"\x02\x03"  # data-choice: resposta a um GET
    apdu[10:12] = b"\x00\xc6"
    apdu[12:14] = b"\x00\x00"
    apdu[14:16] = len(attributes).to_bytes(2, "big")
    apdu[16:18] = len(body).to_bytes(2, "big")

    result = bytes(apdu) + body
    return result[:2] + (len(result) - 4).to_bytes(2, "big") + result[4:]


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------


def write_hex(path: Path, data: bytes) -> None:
    """Grava um APDU em hexadecimal, uma linha, sem espaços."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.hex() + "\n", encoding="utf-8")


def write_example_json(readings: list[tuple[datetime, int]]) -> Path:
    """Grava o dataset sintético no mesmo formato do ``src.cli dump``."""
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    target = EXAMPLES / "data_sintetico.json"
    payload = {
        "device": {
            "vendor_id": 0x173A,
            "product_id": 0x21CC,
            "model": "2102",
            "serial": SYNTHETIC_SERIAL,
            "device_time": SYNTHETIC_DEVICE_TIME.isoformat(),
        },
        "read_at": datetime(2024, 12, 1, 9, 30, 0).isoformat(),
        "count": len(readings),
        "records": [
            {
                "index": index,
                "timestamp": when.isoformat(),
                "epoch": int(when.timestamp()),
                "mg/dL": value,
                "mmol/L": round(value / 18.0182, 3),
                "status": 0,
            }
            for index, (when, value) in enumerate(readings)
        ],
    }
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


def main() -> None:
    """Gera os três fixtures e o dataset de exemplo."""
    readings = synthetic_readings()

    first = readings[:MAX_RECORDS_PER_SEGMENT]
    second = readings[MAX_RECORDS_PER_SEGMENT:]

    write_hex(
        FIXTURES / "segment_80.hex",
        build_segment(first, already_sent=0, is_last=False),
    )
    write_hex(
        FIXTURES / "segment_41.hex",
        build_segment(second, already_sent=len(first), is_last=True),
    )
    write_hex(FIXTURES / "mds_response.hex", build_mds_response())

    example = write_example_json(readings)

    print(f"segment_80.hex   {len(first)} registros")
    print(f"segment_41.hex   {len(second)} registros")
    print("mds_response.hex 8 atributos")
    print(f"{example.relative_to(ROOT)}  {len(readings)} leituras")


if __name__ == "__main__":
    main()

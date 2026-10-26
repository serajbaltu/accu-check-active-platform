#!/usr/bin/env python3
"""Gera um transcript de protocolo **sintético** da sessão com o aparelho.

O transcript reproduz a troca completa de APDUs (associação, config info,
atributos do MDS, GET_INFO, TRIG_XFER, segmentos, release) usando um
**dispositivo falso** que faz replay dos bytes. O código do projeto
(`src/association.py`, `src/transfer.py`, `src/device.py`) roda sem
alteração — só o backend USB é trocado.

Por que existe: as capturas reais contêm leituras de glicemia (dado de
saúde) e a série do aparelho, e por isso **não** são publicadas. Este
transcript mostra o mesmo formato de log, byte a byte comparável com o
real, sem nenhum dado pessoal.

Uso::

    python tools/make_synthetic_transcript.py
"""

from __future__ import annotations

import logging
import pathlib
import sys
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import phdc  # noqa: E402
from src.association import associate  # noqa: E402
from src.device import Device, Endpoints  # noqa: E402
from src.logging_utils import LOG_FORMAT, setup_logging  # noqa: E402
from src.transfer import read_records, release  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"
OUTPUT_DIR = REPO_ROOT / "docs" / "captures" / "exemplo-sintetico"
OUTPUT_LOG = OUTPUT_DIR / "dump-sintetico.log"

#: Config info (270 bytes) capturado no aparelho real. São **dados de
#: protocolo** — a descrição do PM-Store e das métricas —, sem nada de
#: Config info (270 bytes) capturado no aparelho real.
CONFIG_INFO_HEX = (
    "e700010a01080000010101020000ffffffff0d1c00f84040000500f20006000100"
    "040024092f0004000272700a460002f0400996000208520a55000c000200080990"
    "00080a4c00020006000200040024092f0004000271d00a460002f0400996000208"
    "520a55000c00020008099000080a4c0002000500030003001e092f0004008071d8"
    "0a460002f0400a55000c00020008099000080a660002000500040003001e092f00"
    "04008072480a460002f0480a55000c00020008099000080a490002003d00050008"
    "00460a4d0002082009430002000009410004000005dc094400040000007a095300"
    "0200000a570012001050617469656e7420526573756c7473000951000200040a63"
    "000400005dc0"
)

#: Pairing request (54 bytes) enviado pelo aparelho. Os 8 bytes do contexto
#: Pairing request (54 bytes) enviado pelo aparelho.
PAIRING_REQUEST_HEX = (
    "e2000032800000000001002a507900268000000080008000000000000000008000"
    "000008000000000000000000400001010000000000"
)

#: Resposta à ação GET_INFO (422 bytes), com os 4 segmentos do PM-Store
#: (Gluc, Ctrl, Err, Meal). As 3 marcas de tempo que aparecem فيها são
#: substituídas pelas do dataset sintético — no aparelho real elas são a
#: Resposta a GET_INFO (422 bytes) com os 4 segmentos.
ACTION_RESPONSE_HEX = (
    "e70001a201a000020207019a00050c0d01940004019000000008005e0922000200"
    "000a4e00168000000100100006000272700001000100040a4c0002095300020000"
    "099200082020010322071200098a00082023082812422600097b0004000000790a"
    "640004000138800a58000c000a504d536567476c75632000010008005e09220002"
    "00010a4e00168000000100100006000271d00002000100040a4c00020953000200"
    "00099200080000000000000000098a00080000000000000000097b000400000000"
    "0a640004000138800a58000c000a504d5365674374726c2000020008005e092200"
    "0200020a4e00168000000100100005008071d80003000100040a66000209530002"
    "0000099200082020062301314500098a00082020062301314500097b0004000000"
    "010a640004000138800a58000c000a504d5365674572726f7200030008005e0922"
    "000200030a4e00168000000100100005008072480004000100040a490002095300"
    "020000099200080000000000000000098a00080000000000000000097b00040000"
    "00000a640004000138800a58000c000a504d536567434d65616c"
)

#: Marcas de tempo reais que existem dentro do ACTION_RESPONSE_HEX e que
#: são substituídas pelas do dataset sintético.
TIMESTAMP_PATCHES = (
    ("20200103220712", "20240101074649"),  # primeira medição
    ("20230828124226", "20241129055216"),  # última medição
    ("20200623013145", "20240101074649"),  # segmento de erros
)


def _patch_timestamps(data: bytes) -> bytes:
    """Troca as marcas de tempo do ACTION_RESPONSE pelas do dataset sintético."""
    for real, fake in TIMESTAMP_PATCHES:
        old = bytes.fromhex(real)
        new = bytes.fromhex(fake)
        if old not in data:
            raise SystemExit(f"marcador {real} não encontrado na resposta")
        data = data.replace(old, new)
    return data


class FakeUsbDevice:
    """Um ``usb.core.Device`` falso que faz replay de APDUs.

    Implementa só o que :class:`src.device.Device` usa: ``read``,
    ``write`` e ``ctrl_transfer``.
    """

    def __init__(self, script: list[bytes]) -> None:
        #: Respostas que o aparelho "envia", na ordem em que são pedidas.
        self._pending: list[bytes] = list(script)
        self._chunks: list[bytes] = []
        self.written: list[bytes] = []

    # -- helpers ------------------------------------------------------------

    def _queue(self, payload: bytes) -> None:
        """Coloca uma resposta na fila, partida em pacotes de 64 bytes."""
        for start in range(0, len(payload), 64):
            self._chunks.append(payload[start : start + 64])

    def feed(self, payload: bytes) -> None:
        """Enfileira uma resposta para a próxima leitura."""
        self._queue(payload)

    # -- interface do pyusb -------------------------------------------------

    def read(self, endpoint: int, size: int, timeout: int | None = None) -> bytes:
        if not self._chunks:
            # Sem dados: o aparelho "não mandou nada". O Device real
            # levantaria USBTimeoutError; aqui devolvemos um ZLP, que é
            # o que o aparelho de verdade faz enquanto espera.
            return b""
        return self._chunks.pop(0)

    def write(self, endpoint: int, data: bytes, timeout: int | None = None) -> int:
        self.written.append(bytes(data))
        self._dispatch(bytes(data))
        return len(data)

    def ctrl_transfer(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        length: int,
        timeout: int | None = None,
    ) -> bytes:
        return b"\x00\x00"

    # -- máquina de estados do aparelho ------------------------------------

    def _dispatch(self, request: bytes) -> None:
        """Enfileira a resposta que o aparelho dá a cada pedido do host."""
        apdu_type = int.from_bytes(request[:2], "big")

        if apdu_type == phdc.APDU_TYPE_ASSOCIATION_RESPONSE:
            self.feed(bytes.fromhex(CONFIG_INFO_HEX))
            return
        if apdu_type == phdc.APDU_TYPE_ASSOCIATION_RELEASE_REQUEST:
            release = phdc.APDU_TYPE_ASSOCIATION_RELEASE_RESPONSE.to_bytes(2, "big")
            self.feed(release + b"\x00\x02\x00\x00")
            return
        if apdu_type != phdc.APDU_TYPE_PRESENTATION_APDU or len(request) < 16:
            return

        # offset 8-9: data-choice.  01 03 = GET,  01 07 = ACTION.
        data_choice = request[8:10]
        if data_choice == b"\x01\x03":
            self.feed(self._mds_response)
            return
        if data_choice == b"\x01\x07":
            # offset 14-15: action-type.
            action = int.from_bytes(request[14:16], "big")
            if action == phdc.ACTION_TYPE_MDC_ACT_SEG_GET_INFO:
                self.feed(_patch_timestamps(bytes.fromhex(ACTION_RESPONSE_HEX)))
            elif action == phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER:
                self.feed(self._trig_xfer_header)
                self.feed(self._segment_1)
                self.feed(self._segment_2)

    # -- payloads -----------------------------------------------------------

    @property
    def _mds_response(self) -> bytes:
        return bytes.fromhex(
            (FIXTURES / "mds_response.hex").read_text(encoding="utf-8").strip()
        )

    @property
    def _segment_1(self) -> bytes:
        return bytes.fromhex(
            (FIXTURES / "segment_80.hex").read_text(encoding="utf-8").strip()
        )

    @property
    def _segment_2(self) -> bytes:
        return bytes.fromhex(
            (FIXTURES / "segment_41.hex").read_text(encoding="utf-8").strip()
        )

    @property
    def _trig_xfer_header(self) -> bytes:
        """Cabeçalho de 22 bytes da resposta ao TRIG_XFER."""
        return bytes.fromhex("e7000012001000030207000a00050c1c000400000000")


def build_device() -> Device:
    """Monta o :class:`src.device.Device` por cima do backend falso."""
    fake = FakeUsbDevice([])
    dev = Device(fake, Endpoints(in_ep=0x82, out_ep=0x01), timeout_ms=5000)
    dev._fake = fake  # type: ignore[attr-defined]
    return dev


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(OUTPUT_LOG, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    setup_logging(verbose=True)
    logging.getLogger("usb.core").setLevel(logging.INFO)

    dev = build_device()
    fake: FakeUsbDevice = dev._fake  # type: ignore[attr-defined]

    # O aparelho manda o pairing request logo de cara, precedido de ZLPs
    # (é o que o Accu-Chek Active faz enquanto espera a confirmação).
    fake.feed(b"")
    fake.feed(b"")
    fake.feed(b"")
    fake.feed(b"")
    fake.feed(bytes.fromhex(PAIRING_REQUEST_HEX))

    started = datetime.now().astimezone()
    session = associate(dev)
    records = read_records(session)
    release(session)

    handler.flush()
    root.removeHandler(handler)
    handler.close()

    print(f"{OUTPUT_LOG.relative_to(REPO_ROOT)}: {len(records)} registro(s)")
    print(f"  modelo={session.info.model} série={session.info.serial}")
    print(f"  relógio do aparelho={session.info.device_time}")
    print(f"  início={started.isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Leitura dos segmentos de dados do PM-Store.

Fluxo (fases 10 a 14 do ``emogenet/accuchek``)::

    10. OUT — action request TRIG_XFER      (E7 00 … 01 07 … 0C 1C)
    11. IN  — segment stream                  (E7 00 … 02 01 … 0D 21)
    12. OUT — segment ACK                    (E7 00 … 02 01 … 0D 21 … 00 80)
    13. OUT — release request                (E4 00 + 00 00)
    14. IN  — release response               (E5 00)

O stream de segmentos é um laço: o aparelho manda um segmento, a gente
confirma com um ACK, e ele manda o próximo até o segmento final (bit ``0x40``
no byte de status do segmento).
"""

from __future__ import annotations

import logging

import usb.core

from . import phdc
from .association import ProtocolError, Session
from .parser import GlucoseRecord, parse_segment

logger = logging.getLogger(__name__)

#: Teto de segurança para o laço de segmentos (evita laço infinito).
MAX_SEGMENTS = 64


def read_records(session: Session) -> list[GlucoseRecord]:
    """Dispara a transferência e devolve todas as leituras.

    Levanta :class:`ProtocolError` em caso de resposta inesperada.
    """
    dev = session.device
    if session.pm_store_handle is None:
        raise ProtocolError("sessão sem PM-Store: associe antes de ler")

    # --- passo 10: TRIG_XFER ------------------------------------------------
    logger.info("passo 10: action request TRIG_XFER")
    dev.bulk_out(
        phdc.action_request(
            handle=session.pm_store_handle,
            action=phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER,
            action_args=phdc.ACTION_ARGS_SEG_TRIG_XFER,
            invoke_id=session.next_invoke_id(),
        )
    )

    # --- passo 10b: cabeçalho da resposta ao TRIG_XFER ----------------------
    # Antes dos segmentos, o aparelho responde ao TRIG_XFER com um APDU de
    # 22 bytes (action-type = TRIG_XFER no offset 14, data-response no 20).
    # Se o data-response for 3 ("segment is empty"), não há o que ler.
    logger.info("passo 10b: lendo o cabeçalho da resposta ao TRIG_XFER")
    header = dev.read_apdu()
    session.sync_invoke_id(header)

    if len(header) >= 22:
        data_response = phdc.be16(header, 20)
        if data_response != phdc.DATA_RESPONSE_TRANSFER_SUCCESSFUL:
            if data_response == phdc.DATA_RESPONSE_SEGMENT_EMPTY:
                logger.info("o aparelho respondeu: segmento vazio")
                return []
            raise ProtocolError(
                "falha ao recuperar o segmento: "
                f"{phdc.data_response_name(data_response)}"
            )
        action = phdc.be16(header, 14)
        if action != phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER:
            raise ProtocolError(
                f"resposta inesperada ao TRIG_XFER: action-type 0x{action:04X} "
                f"(esperado 0x{phdc.ACTION_TYPE_MDC_ACT_SEG_TRIG_XFER:04X})"
            )
    else:
        logger.warning(
            "cabeçalho do TRIG_XFER curto: %d byte(s)", len(header)
        )

    # --- passos 11 e 12: laço de segmentos --------------------------------
    records: list[GlucoseRecord] = []
    for index in range(MAX_SEGMENTS):
        logger.info("passo 11: lendo segmento %d", index)
        raw = dev.read_apdu()
        session.sync_invoke_id(raw)

        segment = parse_segment(raw)
        records.extend(segment.records)

        logger.info("passo 12: ACK do segmento %d", index)
        dev.bulk_out(
            phdc.segment_ack(
                invoke_id=session.invoke_id,
                store_handle=session.pm_store_handle,
                u0=segment.u0,
                u1=segment.u1,
                u2=segment.u2,
            )
        )

        if segment.is_last:
            logger.info(
                "segmento %d é o último (%d registro(s) no total)",
                index,
                len(records),
            )
            break
    else:
        logger.warning("limite de %d segmentos atingido", MAX_SEGMENTS)

    logger.info("total de %d registro(s) lido(s)", len(records))
    return records


def release(session: Session) -> None:
    """Encerra a associação de forma limpa (passos 13 e 14).

    Falhas aqui não invalidam os dados já lidos — só são logadas.
    """
    dev = session.device
    logger.info("passo 13: release request")
    try:
        dev.bulk_out(phdc.release_request())
    except (OSError, usb.core.USBError, RuntimeError) as exc:  # pragma: no cover
        logger.warning("falha ao enviar release request: %s", exc)
        return

    logger.info("passo 14: release response")
    try:
        dev.read_apdu()
    except (OSError, usb.core.USBError, RuntimeError) as exc:  # pragma: no cover
        logger.warning("falha ao ler release response: %s", exc)

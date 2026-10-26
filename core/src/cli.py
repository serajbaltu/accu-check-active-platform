"""Ponto de entrada do cliente — ``python -m src.cli``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import __version__
from .analysis import analyze, load_dataset
from .association import ProtocolError, Session, associate
from .device import (
    Device,
    DeviceIOError,
    DeviceNotFoundError,
    DeviceOpenError,
)
from .logging_utils import setup_logging
from .report import terminal_summary, write_report
from .transfer import read_records, release

logger = logging.getLogger("src.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Lê as leituras de glicemia do Accu-Chek Active (Roche).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="loga o hexdump de tudo que entra e sai (DEBUG)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"accuchek {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    dump = sub.add_parser("dump", help="lê as leituras e salva em JSON")
    dump.add_argument(
        "--out",
        type=Path,
        default=None,
        help="arquivo de saída (padrão: stdout)",
    )
    dump.add_argument(
        "--include-device",
        action="store_true",
        help="inclui as informações do aparelho no JSON",
    )

    info = sub.add_parser("info", help="mostra as informações do aparelho e sai")
    probe = sub.add_parser(
        "probe",
        help="Fase 2: handshake mínimo com hexdump completo (diagnóstico)",
    )

    show = sub.add_parser(
        "show",
        help="mostra o resumo estatístico de um JSON de leituras",
    )
    show.add_argument(
        "--data",
        type=Path,
        default=Path("data.json"),
        help="JSON gerado por 'dump' (padrão: data.json)",
    )

    report = sub.add_parser(
        "report",
        help="gera o relatório HTML autocontido a partir de um JSON",
    )
    report.add_argument(
        "--data",
        type=Path,
        default=Path("data.json"),
        help="JSON gerado por 'dump' (padrão: data.json)",
    )
    report.add_argument(
        "--out",
        type=Path,
        default=Path("relatorio.html"),
        help="arquivo HTML de saída (padrão: relatorio.html)",
    )
    report.add_argument(
        "--title",
        default="Relatório de glicemia",
        help="título do relatório",
    )
    report.add_argument(
        "--open",
        action="store_true",
        help="abre o relatório no navegador ao terminar",
    )

    for sub_parser in (dump, info, probe):
        sub_parser.add_argument(
            "--wait",
            type=float,
            default=0.0,
            metavar="SEGUNDOS",
            help=(
                "espera até N segundos pelo aparelho (útil para desconectar e "
                "reconectar o cabo USB enquanto o comando roda)"
            ),
        )
    return parser


def _dump_payload(records, session, include_device: bool) -> dict:
    payload: dict = {
        "device": {
            "vendor_id": 0x173A,
            "product_id": 0x21CC,
            "model": session.info.model,
            "serial": session.info.serial,
            "device_time": session.info.device_time,
        },
        "read_at": datetime.now().isoformat(),
        "count": len(records),
        "records": [r.to_dict() for r in records],
    }
    if not include_device:
        payload.pop("device")
    return payload


def cmd_dump(args: argparse.Namespace) -> int:
    """Lê o aparelho e salva as leituras em JSON."""

    def run() -> tuple[list, object]:
        with Device.open() as dev:
            session = associate(dev, deadline=_deadline(args))
            try:
                records = read_records(session)
            finally:
                release(session)
        return records, session

    records, session = _with_retry(args, run)

    payload = _dump_payload(records, session, args.include_device)
    text = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        logger.info("%d registro(s) salvos em %s", len(records), args.out)
    else:
        print(text)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Conecta, lê a identificação do aparelho e sai."""

    def run() -> Session:
        with Device.open() as dev:
            return associate(dev, deadline=_deadline(args))

    session = _with_retry(args, run)
    info = session.info
    print(f"Modelo:      {info.model or '(não informado)'}")
    print(f"Série:       {info.serial or '(não informada)'}")
    print(f"Hora do app: {info.device_time or '(não informada)'}")
    print(f"PM-Store:    handle {session.pm_store_handle}")
    print(f"Segmentos:   {session.num_segments}")
    if info.raw_attributes:
        print("\nAtributos do MDS:")
        for name, value in info.raw_attributes.items():
            print(f"  {name}: {value.hex()}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    """Fase 2: faz só o handshake e loga tudo em hexdump.

    Serve para comparar o nosso tráfego com a captura do usbmon.
    """

    def run() -> Session:
        with Device.open() as dev:
            session = associate(dev, deadline=_deadline(args))
            logger.info(
                "handshake ok: pm_store=%s segmentos=%s",
                session.pm_store_handle,
                session.num_segments,
            )
            release(session)
            return session

    _with_retry(args, run)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Imprime o resumo estatístico de um JSON de leituras."""
    analysis = analyze(load_dataset(args.data))
    print(terminal_summary(analysis))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Gera o relatório HTML autocontido."""
    analysis = analyze(load_dataset(args.data))
    target = write_report(analysis, args.out, args.title)
    logger.info("relatório escrito em %s", target)
    print(f"Relatório: {target.resolve()}")
    if args.open:
        _open_browser(target)
    return 0


def _open_browser(path: Path) -> None:
    """Abre o relatório no navegador padrão (best effort)."""
    import subprocess

    for opener in ("xdg-open", "gio", "sensible-browser"):
        try:
            subprocess.run(  # noqa: S603
                [opener, str(path)], check=False, timeout=10
            )
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.warning("nenhum navegador encontrado; abra o arquivo manualmente")


def _deadline(args: argparse.Namespace) -> float | None:
    """Instante-limite absoluto para esperar o aparelho, ou ``None``."""
    wait = getattr(args, "wait", 0.0) or 0.0
    if wait <= 0:
        return None
    return time.monotonic() + wait


def _with_retry[T](args: argparse.Namespace, run: Callable[[], T]) -> T:
    """Executa ``run``, repetindo enquanto o aparelho não estiver pronto.

    O Accu-Chek só envia o pedido de associação logo após a conexão USB.
    Com ``--wait``, o comando fica no ar esperando: cada tentativa re-abre o
    aparelho do zero, porque um reconexão do cabo muda o endereço USB dele.
    """
    deadline = _deadline(args)
    if deadline is None:
        return run()

    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return run()
        except (
            DeviceNotFoundError,
            DeviceOpenError,
            DeviceIOError,
            ProtocolError,
        ) as exc:
            last_error = exc
            logger.warning("%s — tentando de novo em 1 s", exc)
            time.sleep(1)

    raise SystemExit(f"não consegui falar com o aparelho: {last_error}")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada. Devolve o código de saída do processo."""
    args = _build_parser().parse_args(argv)
    setup_logging(args.verbose)

    handlers = {
        "dump": cmd_dump,
        "info": cmd_info,
        "probe": cmd_probe,
        "show": cmd_show,
        "report": cmd_report,
    }

    try:
        return handlers[args.command](args)
    except DeviceNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except DeviceOpenError as exc:
        logger.error("%s", exc)
        logger.error(
            "Dica: o /dev/bus/usb não é gravável pelo usuário comum — "
            "rode com sudo ou instale a regra udev 99-accuchek.rules."
        )
        return 3
    except KeyboardInterrupt:
        logger.warning("interrompido pelo usuário")
        return 130


if __name__ == "__main__":
    sys.exit(main())

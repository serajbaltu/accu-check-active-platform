"""Gráficos em SVG, gerados em Python puro.

Sem matplotlib, sem JavaScript, sem CDN: o relatório final é **um arquivo
HTML autocontido** que abre em qualquer navegador, offline, e pode ser
compartilhado por e-mail sem perder nada.

Cada função devolve uma string SVG completa (``<svg>...</svg>``). As cores
seguem a convenção clínica usual:

* verde — dentro da faixa (70-180 mg/dL)
* amarelo/laranja — acima
* vermelho — abaixo
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from typing import Final

from .analysis import (
    WEEKDAY_NAMES,
    Analysis,
    DailyPoint,
    HistogramBin,
    HourProfile,
    Reading,
    TimeInRange,
    Trend,
)

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

COLOR_BG: Final = "#0f1720"
COLOR_PANEL: Final = "#16212c"
COLOR_GRID: Final = "#24323f"
COLOR_AXIS: Final = "#5b6b7a"
COLOR_TEXT: Final = "#c8d3dc"
COLOR_TEXT_DIM: Final = "#8b9aa7"
COLOR_ACCENT: Final = "#4da3ff"
COLOR_TREND: Final = "#f5a3c7"

COLOR_VERY_LOW: Final = "#8b1e2d"
COLOR_LOW: Final = "#d4544a"
COLOR_IN_RANGE: Final = "#3fa66a"
COLOR_HIGH: Final = "#e0a33a"
COLOR_VERY_HIGH: Final = "#b5651d"

BAND_COLORS: Final = {
    "very_low": COLOR_VERY_LOW,
    "low": COLOR_LOW,
    "in_range": COLOR_IN_RANGE,
    "high": COLOR_HIGH,
    "very_high": COLOR_VERY_HIGH,
}

BAND_LABELS: Final = {
    "very_low": "Muito baixa",
    "low": "Baixa",
    "in_range": "Em faixa",
    "high": "Alta",
    "very_high": "Muito alta",
}

#: Ordem canônica das faixas do TIR.
BAND_ORDER: Final = ("very_low", "low", "in_range", "high", "very_high")

#: Largura padrão dos gráficos.
WIDTH: Final = 720
HEIGHT: Final = 320

#: Margens do desenho (esquerda, topo, direita, baixo).
MARGIN_LEFT: Final = 56
MARGIN_RIGHT: Final = 18
MARGIN_TOP: Final = 18
MARGIN_BOTTOM: Final = 38


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _text(
    x: float,
    y: float,
    content: str,
    size: int = 11,
    fill: str = COLOR_TEXT,
    anchor: str = "start",
    weight: str = "normal",
) -> str:
    """Um elemento ``<text>`` pronto para o SVG."""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}">'
        f"{escape(content)}</text>"
    )


def _line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str = COLOR_GRID,
    width: float = 1,
    dash: str = "",
) -> str:
    """Um elemento ``<line>`` pronto para o SVG."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}"{dash_attr} />'
    )


def _rect(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    opacity: float = 1.0,
    rx: float = 0,
    extra: str = "",
) -> str:
    """Um elemento ``<rect>`` pronto para o SVG."""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" fill="{fill}" opacity="{opacity}" rx="{rx}" {extra} />'
    )


def _circle(cx: float, cy: float, r: float, fill: str, extra: str = "") -> str:
    """Um elemento ``<circle>`` pronto para o SVG."""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" {extra} />'


def _nice_ceiling(value: float, step: float = 50.0) -> float:
    """Arredonda um teto de eixo para um múltiplo de ``step``."""
    if value <= 0:
        return step
    return math.ceil(value / step) * step


def _svg(body: str, width: int = WIDTH, height: int = HEIGHT) -> str:
    """Monta o elemento ``<svg>`` completo com o fundo."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" font-family="system-ui, -apple-system, '
        f'Segoe UI, Roboto, sans-serif">'
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="{COLOR_BG}" />{body}</svg>'
    )


def _empty(width: int, height: int, message: str = "sem dados") -> str:
    """SVG de fallback quando não há o que desenhar."""
    label = _text(width / 2, height / 2, message, 12, COLOR_TEXT_DIM, "middle")
    return _svg(label, width, height)


def _format_date(when: datetime | date) -> str:
    """Data curta para os rótulos do eixo X."""
    if isinstance(when, datetime):
        return when.strftime("%d/%m/%Y")
    return when.strftime("%d/%m/%Y")


def _anchor(index: int, total: int) -> str:
    """Âncora de texto para um índice de série (início, meio ou fim)."""
    if index == 0:
        return "start"
    if index == total - 1:
        return "end"
    return "middle"


def _value_color(value: float) -> str:
    """Cor de um ponto conforme a faixa-alvo."""
    if value < 70:
        return COLOR_LOW
    if value > 180:
        return COLOR_HIGH
    return COLOR_ACCENT


# ---------------------------------------------------------------------------
# 1. Série temporal
# ---------------------------------------------------------------------------


def time_series_svg(
    readings: Sequence[Reading],
    width: int = WIDTH,
    height: int = HEIGHT,
) -> str:
    """Série temporal das leituras, com as faixas-alvo coloridas ao fundo."""
    if not readings:
        return _empty(width, height)

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - MARGIN_BOTTOM
    plot_w = right - left
    plot_h = bottom - top

    y_max = _nice_ceiling(max(float(r.value_mgdl) for r in readings) * 1.05)
    total = len(readings)

    def sx(index: int) -> float:
        if total == 1:
            return (left + right) / 2
        return left + plot_w * index / (total - 1)

    def sy(value: float) -> float:
        return bottom - plot_h * value / y_max

    body: list[str] = []

    bands = (
        (0.0, 54.0, COLOR_VERY_LOW, 0.55),
        (54.0, 70.0, COLOR_LOW, 0.35),
        (70.0, 180.0, COLOR_IN_RANGE, 0.22),
        (180.0, 250.0, COLOR_HIGH, 0.30),
        (250.0, y_max, COLOR_VERY_HIGH, 0.40),
    )
    for low, high, color, opacity in bands:
        if high <= 0 or low >= y_max:
            continue
        y1 = sy(min(high, y_max))
        y2 = sy(max(low, 0.0))
        body.append(_rect(left, y1, plot_w, max(y2 - y1, 0), color, opacity))

    value = 0.0
    while value <= y_max:
        y = sy(value)
        body.append(_line(left, y, right, y, COLOR_GRID, 1))
        body.append(_text(left - 8, y + 4, f"{value:.0f}", 10, COLOR_TEXT_DIM, "end"))
        value += 50.0

    body.append(_line(left, sy(70), right, sy(70), COLOR_IN_RANGE, 1, "4 3"))
    body.append(_line(left, sy(180), right, sy(180), COLOR_IN_RANGE, 1, "4 3"))

    points = " ".join(
        f"{sx(i):.1f},{sy(r.value_mgdl):.1f}" for i, r in enumerate(readings)
    )
    body.append(
        f'<polyline points="{points}" fill="none" stroke="{COLOR_ACCENT}" '
        'stroke-width="1.4" stroke-opacity="0.65" />'
    )

    for index, reading in enumerate(readings):
        body.append(
            _circle(
                sx(index),
                sy(reading.value_mgdl),
                2.6,
                _value_color(float(reading.value_mgdl)),
                f'stroke="{COLOR_BG}" stroke-width="0.6"',
            )
        )

    body.append(_line(left, bottom, right, bottom, COLOR_AXIS, 1))
    marks = {0, total - 1}
    marks.update(range(0, total, max(total // 5, 1)))
    for index in sorted(marks):
        if not (0 <= index < total):
            continue
        body.append(
            _text(
                sx(index),
                bottom + 16,
                _format_date(readings[index].timestamp),
                9,
                COLOR_TEXT_DIM,
                _anchor(index, total),
            )
        )

    body.append(_text(left, bottom + 32, "mg/dL", 9, COLOR_TEXT_DIM))
    body.append(_text(right, top + 2, f"{total} leituras", 10, COLOR_TEXT_DIM, "end"))

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 2. Histograma
# ---------------------------------------------------------------------------


def histogram_svg(
    bins: Sequence[HistogramBin],
    width: int = WIDTH,
    height: int = HEIGHT,
) -> str:
    """Histograma da distribuição dos valores."""
    if not bins:
        return _empty(width, height)

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - MARGIN_BOTTOM
    plot_w = right - left
    plot_h = bottom - top

    max_count = max(b.count for b in bins) or 1
    bar_w = plot_w / len(bins)

    def sy(value: float) -> float:
        return bottom - plot_h * value / max_count

    body: list[str] = []

    body.append(_rect(left, sy(180), plot_w, bottom - sy(180), COLOR_IN_RANGE, 0.15))
    body.append(_line(left, sy(180), right, sy(180), COLOR_IN_RANGE, 1, "4 3"))
    body.append(_line(left, sy(70), right, sy(70), COLOR_IN_RANGE, 1, "4 3"))

    for index, bin_ in enumerate(bins):
        bar_h = plot_h * bin_.count / max_count
        x = left + index * bar_w
        color = COLOR_ACCENT
        if bin_.high <= 70:
            color = COLOR_LOW
        elif bin_.low >= 180:
            color = COLOR_HIGH
        body.append(_rect(x + 1, bottom - bar_h, bar_w - 2, bar_h, color, 0.9, 2))
        if bin_.count:
            body.append(
                _text(
                    x + bar_w / 2,
                    bottom - bar_h - 5,
                    str(bin_.count),
                    9,
                    COLOR_TEXT_DIM,
                    "middle",
                )
            )

    body.append(_line(left, bottom, right, bottom, COLOR_AXIS, 1))

    for index, bin_ in enumerate(bins):
        if index % 2 == 0 or len(bins) <= 8:
            body.append(
                _text(
                    left + index * bar_w + bar_w / 2,
                    bottom + 15,
                    f"{bin_.low:.0f}",
                    9,
                    COLOR_TEXT_DIM,
                    "middle",
                )
            )
    body.append(_text(right, bottom + 15, "mg/dL", 9, COLOR_TEXT_DIM, "end"))
    body.append(
        _text(left, bottom + 30, "faixa verde = alvo 70-180", 9, COLOR_TEXT_DIM)
    )

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 3. Boxplot por hora do dia
# ---------------------------------------------------------------------------


def boxplot_svg(
    profiles: Sequence[HourProfile],
    width: int = WIDTH,
    height: int = HEIGHT,
) -> str:
    """Boxplot das leituras por hora do dia."""
    if not profiles:
        return _empty(width, height)

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - MARGIN_BOTTOM
    plot_w = right - left
    plot_h = bottom - top

    y_max = _nice_ceiling(max(p.max for p in profiles) * 1.05)
    slot = plot_w / 24.0
    box_w = min(slot * 0.6, 22.0)

    def sy(value: float) -> float:
        return bottom - plot_h * value / y_max

    body: list[str] = []

    body.append(_rect(left, sy(180), plot_w, bottom - sy(180), COLOR_IN_RANGE, 0.15))
    body.append(_rect(left, sy(70), plot_w, sy(70) - sy(180), COLOR_LOW, 0.10))
    body.append(_line(left, sy(70), right, sy(70), COLOR_IN_RANGE, 1, "4 3"))
    body.append(_line(left, sy(180), right, sy(180), COLOR_IN_RANGE, 1, "4 3"))

    for index, profile in enumerate(profiles):
        hour = profile.slot if profile.slot is not None else index
        cx = left + slot * (hour + 0.5)
        body.append(_line(cx, sy(profile.min), cx, sy(profile.max), COLOR_AXIS, 1))
        body.append(
            _line(
                cx - box_w / 2,
                sy(profile.q1),
                cx + box_w / 2,
                sy(profile.q1),
                COLOR_ACCENT,
                1,
            )
        )
        body.append(
            _line(
                cx - box_w / 2,
                sy(profile.q3),
                cx + box_w / 2,
                sy(profile.q3),
                COLOR_ACCENT,
                1,
            )
        )
        body.append(
            _rect(
                cx - box_w / 2,
                sy(profile.q3),
                box_w,
                sy(profile.q1) - sy(profile.q3),
                COLOR_ACCENT,
                0.28,
                2,
                f'stroke="{COLOR_ACCENT}" stroke-width="1.2"',
            )
        )
        body.append(
            _circle(cx, sy(profile.median), 2.6, "#ffffff", f'stroke="{COLOR_ACCENT}"')
        )

    for hour in range(0, 24, 3):
        cx = left + slot * (hour + 0.5)
        body.append(_text(cx, bottom + 15, f"{hour:02d}h", 9, COLOR_TEXT_DIM, "middle"))

    body.append(_line(left, bottom, right, bottom, COLOR_AXIS, 1))
    body.append(_text(left, bottom + 31, "hora do dia", 9, COLOR_TEXT_DIM))
    body.append(_text(left - 8, top + 4, "mg/dL", 9, COLOR_TEXT_DIM, "end"))

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 4. Média diária + tendência
# ---------------------------------------------------------------------------


def daily_trend_svg(
    points: Sequence[DailyPoint],
    trend: Trend,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> str:
    """Média diária das leituras com a reta de tendência."""
    if not points:
        return _empty(width, height)

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - MARGIN_BOTTOM
    plot_w = right - left
    plot_h = bottom - top

    values = [p.mean for p in points]
    values += [p.min for p in points]
    values += [p.max for p in points]
    y_max = _nice_ceiling(max(values) * 1.08)
    y_min = max(0.0, math.floor(min(values) / 50.0) * 50 - 20)
    total = len(points)

    def sx(index: int) -> float:
        if total == 1:
            return (left + right) / 2
        return left + plot_w * index / (total - 1)

    def sy(value: float) -> float:
        return bottom - plot_h * (value - y_min) / (y_max - y_min)

    body: list[str] = []

    body.append(_rect(left, sy(180), plot_w, bottom - sy(180), COLOR_IN_RANGE, 0.15))
    body.append(_line(left, sy(70), right, sy(70), COLOR_IN_RANGE, 1, "4 3"))
    body.append(_line(left, sy(180), right, sy(180), COLOR_IN_RANGE, 1, "4 3"))

    value = y_min
    while value <= y_max:
        y = sy(value)
        body.append(_line(left, y, right, y, COLOR_GRID, 1))
        body.append(_text(left - 8, y + 4, f"{value:.0f}", 10, COLOR_TEXT_DIM, "end"))
        value += 50.0

    if not math.isnan(trend.slope) and not math.isnan(trend.intercept):
        y1 = trend.intercept
        y2 = trend.intercept + trend.slope * (total - 1)
        body.append(
            _line(sx(0), sy(y1), sx(total - 1), sy(y2), COLOR_TREND, 2.2, "6 4")
        )
        label = f"tendência {trend.slope:+.3f} mg/dL/dia (r²={trend.r_squared:.2f})"
        body.append(_text(right, top + 12, label, 10, COLOR_TREND, "end"))

    for index, point in enumerate(points):
        body.append(
            _line(sx(index), sy(point.min), sx(index), sy(point.max), COLOR_GRID, 1)
        )
        body.append(_circle(sx(index), sy(point.mean), 2.4, COLOR_ACCENT))

    body.append(_line(left, bottom, right, bottom, COLOR_AXIS, 1))
    for index in (0, total // 2, total - 1):
        body.append(
            _text(
                sx(index),
                bottom + 16,
                _format_date(points[index].day),
                9,
                COLOR_TEXT_DIM,
                _anchor(index, total),
            )
        )

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 5. Rosca do Tempo em Faixa
# ---------------------------------------------------------------------------


def tir_donut_svg(
    tir: TimeInRange,
    width: int = 340,
    height: int = 340,
) -> str:
    """Rosca (donut) com a distribuição do Tempo em Faixa."""
    center_x = width / 2
    center_y = height / 2 - 12
    radius = 92.0
    thickness = 30.0
    circumference = 2 * math.pi * radius

    body: list[str] = []

    if not tir.total:
        body.append(
            _text(center_x, center_y, "sem dados", 12, COLOR_TEXT_DIM, "middle")
        )
        return _svg("".join(body), width, height)

    offset = 0.0
    for key in BAND_ORDER:
        count = tir.count(key)
        if not count:
            continue
        length = circumference * count / tir.total
        body.append(
            f'<circle cx="{center_x:.1f}" cy="{center_y:.1f}" r="{radius:.1f}" '
            f'fill="none" stroke="{BAND_COLORS[key]}" stroke-width="{thickness:.1f}" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {center_x:.1f} {center_y:.1f})" />'
        )
        offset += length

    body.append(
        _text(
            center_x,
            center_y - 4,
            f"{tir.in_range_pct:.0f}%",
            30,
            COLOR_TEXT,
            "middle",
            "bold",
        )
    )
    body.append(
        _text(center_x, center_y + 18, "em faixa", 12, COLOR_TEXT_DIM, "middle")
    )
    body.append(
        _text(
            center_x,
            center_y + 38,
            f"({tir.total} leituras)",
            10,
            COLOR_TEXT_DIM,
            "middle",
        )
    )

    for index, key in enumerate(BAND_ORDER):
        y = height - 92 + index * 16
        body.append(_rect(width / 2 - 84, y - 8, 10, 10, BAND_COLORS[key], 1, 2))
        body.append(_text(width / 2 - 68, y + 1, BAND_LABELS[key], 10, COLOR_TEXT))
        body.append(
            _text(
                width / 2 + 84,
                y + 1,
                f"{tir.percentage(key):.1f}%",
                10,
                COLOR_TEXT_DIM,
                "end",
            )
        )

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 6. Mapa de calor hora × dia da semana
# ---------------------------------------------------------------------------


def heatmap_svg(
    readings: Sequence[Reading],
    width: int = WIDTH,
    height: int = 300,
) -> str:
    """Mapa de calor: hora do dia × dia da semana, cor = média em mg/dL."""
    if not readings:
        return _empty(width, height)

    left, top = 74.0, 24.0
    cell_w = (width - left - 16) / 24.0
    cell_h = (height - top - 34) / 7.0

    buckets: dict[tuple[int, int], list[float]] = {}
    for reading in readings:
        key = (reading.timestamp.weekday(), reading.timestamp.hour)
        buckets.setdefault(key, []).append(float(reading.value_mgdl))

    body: list[str] = []

    for weekday in range(7):
        for hour in range(24):
            values = buckets.get((weekday, hour))
            x = left + hour * cell_w
            y = top + weekday * cell_h
            if not values:
                body.append(_rect(x, y, cell_w - 1, cell_h - 1, COLOR_PANEL, 1, 2))
                continue
            mean = sum(values) / len(values)
            body.append(
                _rect(
                    x,
                    y,
                    cell_w - 1,
                    cell_h - 1,
                    _heat_color(mean),
                    0.9,
                    2,
                    f'stroke="{COLOR_BG}" stroke-width="0.5"',
                )
            )

    for weekday, name in enumerate(WEEKDAY_NAMES):
        body.append(
            _text(
                left - 8,
                top + weekday * cell_h + cell_h / 2 + 3,
                name[:3],
                9,
                COLOR_TEXT_DIM,
                "end",
            )
        )

    for hour in range(0, 24, 3):
        body.append(
            _text(
                left + hour * cell_w + cell_w / 2,
                top - 8,
                f"{hour:02d}",
                9,
                COLOR_TEXT_DIM,
                "middle",
            )
        )

    body.append(_text(left, height - 12, "hora do dia", 9, COLOR_TEXT_DIM))
    body.append(
        _text(width - 16, height - 12, "cor = média em mg/dL", 9, COLOR_TEXT_DIM, "end")
    )

    return _svg("".join(body), width, height)


def _heat_color(mean: float) -> str:
    """Cor da célula do mapa de calor, conforme a faixa da média."""
    if mean < 54:
        return COLOR_VERY_LOW
    if mean < 70:
        return COLOR_LOW
    if mean <= 180:
        factor = min(abs(mean - 100) / 60.0, 1.0)
        base = (63, 166, 106)
        faded = (46, 96, 74)
        rgb = tuple(
            int(faded[i] + (base[i] - faded[i]) * (1 - factor)) for i in range(3)
        )
        return "#{:02x}{:02x}{:02x}".format(*rgb)
    if mean <= 250:
        return COLOR_HIGH
    return COLOR_VERY_HIGH


# ---------------------------------------------------------------------------
# 7. Faixa horária (strip plot)
# ---------------------------------------------------------------------------


def day_strip_svg(
    readings: Sequence[Reading],
    width: int = WIDTH,
    height: int = 260,
) -> str:
    """Cada leitura como um ponto, espalhado pela hora do dia (0-24 h)."""
    if not readings:
        return _empty(width, height)

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - 52
    plot_w = right - left
    plot_h = bottom - top

    y_max = _nice_ceiling(max(float(r.value_mgdl) for r in readings) * 1.05)

    def sy(value: float) -> float:
        return bottom - plot_h * value / y_max

    body: list[str] = []

    body.append(_rect(left, sy(180), plot_w, bottom - sy(180), COLOR_IN_RANGE, 0.15))
    body.append(_line(left, sy(70), right, sy(70), COLOR_IN_RANGE, 1, "4 3"))
    body.append(_line(left, sy(180), right, sy(180), COLOR_IN_RANGE, 1, "4 3"))

    value = 0.0
    while value <= y_max:
        y = sy(value)
        body.append(_line(left, y, right, y, COLOR_GRID, 1))
        body.append(_text(left - 8, y + 4, f"{value:.0f}", 10, COLOR_TEXT_DIM, "end"))
        value += 50.0

    for reading in readings:
        hour = reading.timestamp.hour + reading.timestamp.minute / 60.0
        x = left + plot_w * hour / 24.0
        body.append(
            _circle(
                x,
                sy(reading.value_mgdl),
                3.0,
                _value_color(float(reading.value_mgdl)),
                f'fill-opacity="0.65" stroke="{COLOR_BG}" stroke-width="0.5"',
            )
        )

    body.append(_line(left, bottom, right, bottom, COLOR_AXIS, 1))
    for hour in range(0, 25, 3):
        x = left + plot_w * hour / 24.0
        body.append(
            _text(
                x,
                bottom + 16,
                f"{hour:02d}h",
                9,
                COLOR_TEXT_DIM,
                "start" if hour == 0 else "end" if hour == 24 else "middle",
            )
        )
    body.append(_text(left, bottom + 32, "mg/dL", 9, COLOR_TEXT_DIM))

    return _svg("".join(body), width, height)


# ---------------------------------------------------------------------------
# 8. Cartões de métricas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatCard:
    """Um cartão de métrica do relatório."""

    label: str
    value: str
    detail: str = ""
    accent: str = COLOR_ACCENT


def stat_cards(analysis: Analysis) -> list[StatCard]:
    """Monta os cartões de métricas principais."""
    descriptive = analysis.descriptive
    indicators = analysis.indicators
    tir = analysis.tir
    return [
        StatCard(
            "Leituras",
            f"{descriptive.n}",
            f"em {analysis.monitoring.days_with_data} dia(s) de medição",
        ),
        StatCard(
            "Média",
            f"{descriptive.mean:.0f} mg/dL",
            f"{descriptive.mean_mmol:.1f} mmol/L · mediana {descriptive.median:.0f}",
        ),
        StatCard(
            "GMI",
            f"{indicators.gmi:.1f}%",
            f"eA1c (ADAG) {indicators.ea1c_adag:.1f}%",
            COLOR_IN_RANGE if indicators.gmi < 7 else COLOR_HIGH,
        ),
        StatCard(
            "Tempo em faixa",
            f"{tir.in_range_pct:.0f}%",
            f"70-180 mg/dL · abaixo {tir.below_range_pct:.1f}%",
            COLOR_IN_RANGE if tir.in_range_pct > 70 else COLOR_HIGH,
        ),
        StatCard(
            "Variabilidade (CV)",
            f"{descriptive.cv:.1f}%",
            "abaixo de 36% = estável",
            COLOR_HIGH if descriptive.cv_high else COLOR_IN_RANGE,
        ),
        StatCard(
            "Amplitude",
            f"{descriptive.min:.0f}–{descriptive.max:.0f}",
            f"IQR {descriptive.iqr:.0f} mg/dL",
        ),
    ]

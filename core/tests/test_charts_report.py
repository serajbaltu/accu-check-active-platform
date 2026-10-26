"""Testes dos gráficos (:mod:`src.charts`) e do relatório (:mod:`src.report`).

Não conferimos o desenho pixel a pixel: verificamos que o SVG é **bem
formado** (tags balanceadas, sem ``NaN``, com coordenadas numéricas) e que o
HTML sai **autocontido** (sem ``<script>`` e sem referência externa).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from src.analysis import (
    Analysis,
    Dataset,
    Reading,
    analyze,
    daily_means,
    linear_trend,
    time_in_range,
)
from src.charts import (
    boxplot_svg,
    daily_trend_svg,
    day_strip_svg,
    heatmap_svg,
    histogram_svg,
    stat_cards,
    time_series_svg,
    tir_donut_svg,
)
from src.report import render_html, terminal_summary, write_report

SVG_OPEN = re.compile(r"<svg\b")
SVG_CLOSE = re.compile(r"</svg>")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def make_readings(values: list[int], start: datetime | None = None) -> list[Reading]:
    """Cria leituras espaçadas de 12 h a partir de ``start``."""
    base = start or datetime(2023, 1, 1, 8, 0)
    return [
        Reading(timestamp=base + timedelta(hours=12 * index), value_mgdl=value)
        for index, value in enumerate(values)
    ]


def assert_valid_svg(svg: str) -> None:
    """Verifica que a string é um SVG utilizável."""
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert len(SVG_OPEN.findall(svg)) == 1
    assert len(SVG_CLOSE.findall(svg)) == 1
    assert "viewBox" in svg
    assert "nan" not in svg.lower()
    assert "None" not in svg
    # nenhum atributo numérico deve estar vazio
    pattern = r'\b(?:x|y|x1|y1|x2|y2|cx|cy|r|width|height)="([^"]*)"'
    for value in re.findall(pattern, svg):
        assert NUMBER.fullmatch(value) or value in ("100%", "auto"), (
            f"coordenada inválida: {value!r}"
        )


@pytest.fixture
def analysis() -> Analysis:
    """Análise de um conjunto pequeno e previsível de leituras."""
    readings = make_readings([90, 110, 130, 55, 200, 105, 95, 250])
    return analyze(Dataset(readings=readings, device={"model": "2102"}))


class TestCharts:
    def test_time_series(self, analysis):
        assert_valid_svg(time_series_svg(analysis.dataset.readings))

    def test_time_series_empty(self):
        assert_valid_svg(time_series_svg([]))

    def test_histogram(self, analysis):
        assert_valid_svg(histogram_svg(analysis.histogram))

    def test_histogram_empty(self):
        assert_valid_svg(histogram_svg([]))

    def test_boxplot(self, analysis):
        assert_valid_svg(boxplot_svg(analysis.hourly))

    def test_boxplot_empty(self):
        assert_valid_svg(boxplot_svg([]))

    def test_day_strip(self, analysis):
        assert_valid_svg(day_strip_svg(analysis.dataset.readings))

    def test_heatmap(self, analysis):
        assert_valid_svg(heatmap_svg(analysis.dataset.readings))

    def test_heatmap_empty(self):
        assert_valid_svg(heatmap_svg([]))

    def test_donut(self, analysis):
        assert_valid_svg(tir_donut_svg(analysis.tir))

    def test_donut_empty(self):
        empty = Dataset()
        assert_valid_svg(tir_donut_svg(time_in_range(empty.readings)))

    def test_daily_trend(self, analysis):
        points = daily_means(analysis.dataset.readings)
        trend = linear_trend(analysis.dataset.readings)
        assert_valid_svg(daily_trend_svg(points, trend))

    def test_daily_trend_empty(self):
        assert_valid_svg(daily_trend_svg([], linear_trend([])))

    def test_donut_percentages(self, analysis):
        svg = tir_donut_svg(analysis.tir)
        assert f"{analysis.tir.in_range_pct:.0f}%" in svg

    def test_stat_cards(self, analysis):
        cards = stat_cards(analysis)
        assert len(cards) == 6
        assert all(card.value for card in cards)

    def test_svg_is_self_contained(self, analysis):
        svg = time_series_svg(analysis.dataset.readings)
        assert "<script" not in svg
        assert "http://" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
        assert "https://" not in svg


class TestReport:
    def test_html_structure(self, analysis):
        html = render_html(analysis)
        assert html.startswith("<!DOCTYPE html>")
        assert "<title>Relatório de glicemia</title>" in html
        assert html.rstrip().endswith("</html>")

    def test_html_is_self_contained(self, analysis):
        html = render_html(analysis)
        assert "<script" not in html
        assert "src=\"http" not in html
        assert "href=\"http" not in html
        assert html.count("<svg") == 7

    def test_html_sections(self, analysis):
        html = render_html(analysis)
        for section in (
            "Tempo em Faixa",
            "Distribuição dos valores",
            "Evolução no tempo",
            "Média diária e tendência",
            "Perfil por hora do dia",
            "Mapa de calor",
            "Monitorização",
            "Referências",
        ):
            assert section in html

    def test_html_escapes_content(self):
        readings = make_readings([100])
        device = {"model": "<script>x</script>"}
        analysis = analyze(Dataset(readings=readings, device=device))
        html = render_html(analysis)
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html

    def test_title_override(self, analysis):
        html = render_html(analysis, title="Meu título")
        assert "<title>Meu título</title>" in html

    def test_write_report(self, analysis, tmp_path):
        target = write_report(analysis, tmp_path / "sub" / "rel.html")
        assert target.exists()
        assert target.stat().st_size > 1000
        assert target.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    def test_terminal_summary(self, analysis):
        text = terminal_summary(analysis)
        assert "RELATÓRIO DE GLICEMIA" in text
        assert "TEMPO EM FAIXA" in text
        assert "TENDÊNCIA" in text
        assert "não é diagnóstico" in text.lower()

    def test_terminal_summary_empty(self):
        text = terminal_summary(analyze(Dataset()))
        assert "RELATÓRIO DE GLICEMIA" in text


class TestClockNote:
    """O relatório deve avisar quando o relógio interno do aparelho está errado."""

    def _html(self, device_time: str, read_at: datetime) -> str:
        readings = make_readings([100])
        dataset = Dataset(
            readings=readings,
            device={"model": "2102", "device_time": device_time},
            read_at=read_at,
        )
        return render_html(analyze(dataset))

    def test_avisa_relogio_desatualizado(self):
        html = self._html("2019-11-12T02:48:20", datetime(2026, 10, 21, 13, 54))
        assert "Relógio do aparelho dessincronizado" in html
        assert "2535 dias" in html

    def test_nao_avisa_quando_esta_sincronizado(self):
        html = self._html("2026-10-21T13:50:00", datetime(2026, 10, 21, 13, 54))
        assert "Relógio do aparelho dessincronizado" not in html

    def test_nao_avisa_sem_hora_do_aparelho(self):
        html = self._html("", datetime(2026, 10, 21, 13, 54))
        assert "Relógio do aparelho dessincronizado" not in html

    def test_ignora_hora_invalida(self):
        html = self._html("nao-e-uma-data", datetime(2026, 10, 21, 13, 54))
        assert "Relógio do aparelho dessincronizado" not in html


class TestIntegration:
    def test_real_dataset(self):
        """Gera o relatório a partir do dump real de 121 leituras."""
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "data.json"
        if not path.exists():
            pytest.skip("data.json ausente")

        from src.analysis import load_dataset

        analysis = analyze(load_dataset(path))
        assert analysis.descriptive.n == 121
        assert analysis.tir.total == 121

        html = render_html(analysis)
        assert html.count("<svg") == 7
        assert "nan" not in html.lower()

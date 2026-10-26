"""Relatório HTML autocontido.

Gera **um único arquivo ``.html``** com todos os gráficos embutidos como SVG
inline, sem JavaScript, sem CSS externo, sem imagens externas. Abre offline
em qualquer navegador e pode ser enviado por e-mail.

O mesmo módulo monta também o resumo textual para o terminal (``show``).
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

from .analysis import (
    Analysis,
    Reading,
    TimeInRange,
)
from .charts import (
    BAND_COLORS,
    BAND_LABELS,
    BAND_ORDER,
    boxplot_svg,
    daily_trend_svg,
    day_strip_svg,
    heatmap_svg,
    histogram_svg,
    stat_cards,
    time_series_svg,
    tir_donut_svg,
)

#: Texto do aviso clínico exibido no topo e no rodapé do relatório.
DISCLAIMER: Final = (
    "Este relatório é informativo e <strong>não substitui</strong> a orientação "
    "médica. Os dados vêm de um <strong>glicosímetro (SMBG)</strong>, não de um "
    "sensor contínuo (CGM): o Tempo em Faixa, o GMI e a variabilidade são "
    "<strong>aproximações</strong> e subestimam a variabilidade real."
)

#: Referências usadas nas fórmulas e nas metas.
REFERENCES: Final = (
    ("GMI", "Bergenstal et al., Diabetes Care 2018;41(11):2275-2280"),
    ("eA1c (ADAG)", "Nathan et al., Diabetes Care 2008;31(8):1571-1580"),
    ("Tempo em Faixa", "Battelino et al., Diabetes Care 2019;42(8):1593-1603"),
    ("Variabilidade (CV)", "Danne et al., Diabetes Care 2017;40(6):1591-1603"),
    ("Metas clínicas", "ADA, Standards of Care in Diabetes-2026; SBD, Ed. 2025"),
)

CSS: Final = """
:root {
  --bg: #0b1117;
  --panel: #16212c;
  --panel-2: #1c2836;
  --border: #24323f;
  --text: #c8d3dc;
  --dim: #8b9aa7;
  --accent: #4da3ff;
  --green: #3fa66a;
  --amber: #e0a33a;
  --red: #d4544a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0 0 60px;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 0 18px; }
header { padding: 34px 0 10px; }
h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: -0.3px; }
h2 {
  font-size: 16px;
  margin: 34px 0 12px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--border);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: var(--dim);
}
h3 { font-size: 14px; margin: 0 0 8px; color: var(--text); }
.sub { color: var(--dim); font-size: 13px; margin: 0; }
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  margin: 12px 0;
}
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0 4px; }
.card {
  flex: 1 1 160px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 12px 14px;
}
.card .label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--dim);
}
.card .value { font-size: 22px; font-weight: 600; margin: 3px 0 2px; }
.card .detail { font-size: 12px; color: var(--dim); }
.alert {
  background: rgba(212, 84, 74, 0.12);
  border: 1px solid rgba(212, 84, 74, 0.45);
  border-radius: 8px;
  padding: 11px 14px;
  margin: 8px 0;
  font-size: 14px;
}
.note {
  background: rgba(77, 163, 255, 0.10);
  border: 1px solid rgba(77, 163, 255, 0.35);
  border-radius: 8px;
  padding: 11px 14px;
  font-size: 13px;
  color: var(--dim);
}
.ok { border-color: rgba(63, 166, 106, 0.5); background: rgba(63, 166, 106, 0.12); }
.note.warn {
  background: rgba(224, 163, 58, 0.10);
  border-color: rgba(224, 163, 58, 0.45);
  color: var(--text);
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 6px 8px; text-align: right; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--dim); font-weight: 600; font-size: 11px; text-transform: uppercase; }
tbody tr:hover { background: var(--panel-2); }
.swatch {
  display: inline-block; width: 9px; height: 9px; border-radius: 2px;
  margin-right: 6px; vertical-align: baseline;
}
.chart { margin: 6px 0 2px; }
.chart svg { display: block; border-radius: 8px; }
.grid-2 { display: flex; flex-wrap: wrap; gap: 14px; }
.grid-2 > * { flex: 1 1 420px; }
details { margin-top: 10px; }
summary { cursor: pointer; color: var(--dim); font-size: 13px; }
footer { margin-top: 40px; color: var(--dim); font-size: 12px; }
ul.refs { padding-left: 18px; }
ul.refs li { margin: 3px 0; }
code {
  background: var(--panel-2); padding: 1px 5px; border-radius: 4px;
  font-size: 12px;
}
"""


# ---------------------------------------------------------------------------
# Blocos de HTML
# ---------------------------------------------------------------------------


def _esc(text: object) -> str:
    """Escapa texto para HTML."""
    return html.escape(str(text))


def _card_block(analysis: Analysis) -> str:
    """Cartões de métricas principais."""
    parts = ['<div class="cards">']
    for card in stat_cards(analysis):
        parts.append(
            f'<div class="card" style="border-left-color:{card.accent}">'
            f'<div class="label">{_esc(card.label)}</div>'
            f'<div class="value">{_esc(card.value)}</div>'
            f'<div class="detail">{_esc(card.detail)}</div>'
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _alerts_block(analysis: Analysis) -> str:
    """Alertas clínicos em destaque."""
    alerts = analysis.alerts
    if not alerts:
        return (
            '<div class="alert ok">Nenhum alerta automático: sem hipoglicemia '
            "grave, variabilidade dentro do alvo e TIR acima de 70%.</div>"
        )
    return "".join(f'<div class="alert">{_esc(message)}</div>' for message in alerts)


def _tir_table(tir: TimeInRange) -> str:
    """Tabela da distribuição do Tempo em Faixa."""
    rows = []
    for key in BAND_ORDER:
        rows.append(
            "<tr>"
            f'<td><span class="swatch" style="background:{BAND_COLORS[key]}"></span>'
            f"{_esc(BAND_LABELS[key])}</td>"
            f"<td>{tir.count(key)}</td>"
            f"<td>{tir.percentage(key):.1f}%</td>"
            "</tr>"
        )
    return (
        '<div class="panel"><h3>Tempo em Faixa (70-180 mg/dL)</h3>'
        "<table><thead><tr><th>Faixa</th><th>Leituras</th><th>%</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _profile_table(title: str, profiles: Sequence, key_header: str) -> str:
    """Tabela genérica de um perfil (por hora ou por dia da semana)."""
    rows = []
    for profile in profiles:
        rows.append(
            "<tr>"
            f"<td>{_esc(profile.label)}</td>"
            f"<td>{profile.count}</td>"
            f"<td>{profile.mean:.0f}</td>"
            f"<td>{profile.median:.0f}</td>"
            f"<td>{profile.min:.0f}</td>"
            f"<td>{profile.max:.0f}</td>"
            "</tr>"
        )
    return (
        f'<div class="panel"><h3>{_esc(title)}</h3>'
        f"<table><thead><tr><th>{_esc(key_header)}</th><th>n</th><th>Média</th>"
        "<th>Mediana</th><th>Mín</th><th>Máx</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _hypo_table(analysis: Analysis) -> str:
    """Tabela dos eventos de hipoglicemia."""
    events = [r for r in analysis.dataset.readings if r.value_mgdl < 70]
    if not events:
        return (
            '<div class="panel"><h3>Eventos de hipoglicemia</h3>'
            "<p class=\"sub\">Nenhuma leitura abaixo de 70 mg/dL.</p></div>"
        )
    rows = []
    for reading in events:
        flag = ""
        if reading.out_of_range:
            flag = f' <span class="sub">({_esc(reading.out_of_range)})</span>'
        rows.append(
            "<tr>"
            f"<td>{reading.timestamp.strftime('%d/%m/%Y %H:%M')}</td>"
            f"<td>{reading.value_mgdl}</td>"
            f"<td>{reading.value_mmol:.1f}</td>"
            f"<td>{flag}</td>"
            "</tr>"
        )
    return (
        '<div class="panel"><h3>Eventos de hipoglicemia (&lt; 70 mg/dL)</h3>'
        "<table><thead><tr><th>Data/hora</th><th>mg/dL</th><th>mmol/L</th>"
        f"<th>Obs.</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _readings_table(readings: Sequence[Reading]) -> str:
    """Tabela com todas as leituras (recolhida por padrão)."""
    rows = []
    for reading in reversed(readings):
        rows.append(
            "<tr>"
            f"<td>{reading.timestamp.strftime('%d/%m/%Y %H:%M')}</td>"
            f"<td>{reading.value_mgdl}</td>"
            f"<td>{reading.value_mmol:.1f}</td>"
            "</tr>"
        )
    return (
        "<details><summary>Ver todas as "
        f"{len(readings)} leituras</summary>"
        '<div class="panel"><table><thead><tr><th>Data/hora</th><th>mg/dL</th>'
        f"<th>mmol/L</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        "</details>"
    )


def _device_block(analysis: Analysis) -> str:
    """Linha de metadados do aparelho e do período."""
    device = analysis.dataset.device or {}
    first, last = analysis.dataset.period
    period = "sem leituras"
    if first and last:
        period = f"{first.strftime('%d/%m/%Y')} → {last.strftime('%d/%m/%Y')}"
    parts = [f"<p class=\"sub\">Período: <strong>{_esc(period)}</strong>"]
    for label, key in (
        ("Aparelho", "model"),
        ("Serial", "serial"),
        ("Firmware", "fw_revision"),
        ("Hora do aparelho", "device_time"),
    ):
        value = device.get(key)
        if value:
            parts.append(f" · {_esc(label)}: <strong>{_esc(value)}</strong>")
    parts.append("</p>")
    return "".join(parts)


def _clock_note(analysis: Analysis) -> str:
    """Aviso quando o relógio interno do aparelho está claramente fora da data real.

    O Active armazena os horários a partir do próprio relógio, que pode estar
    zerado (bateria removida) ou simplesmente errado. Nesses casos as
    datas absolutas ficam suspeitas — o que **não** invalida os intervalos
    entre medições, as taxas e os valores.
    """
    device_time = (analysis.dataset.device or {}).get("device_time")
    if not device_time or analysis.dataset.read_at is None:
        return ""
    try:
        device_when = datetime.fromisoformat(device_time)
    except ValueError:
        return ""
    drift = abs((analysis.dataset.read_at - device_when).total_seconds())
    if drift < 86400:
        return ""
    days = int(drift // 86400)
    return (
        '<div class="note warn">'
        "<strong>Relógio do aparelho dessincronizado.</strong> "
        f"O aparelho reporta {device_time}, mas a leitura foi feita em "
        f"{analysis.dataset.read_at.strftime('%Y-%m-%d %H:%M')} "
        f"({days} dias de diferença). As datas absolutas das medições vêm "
        "desse relógio interno e devem ser tratadas como aproximadas; "
        "os <em>intervalos</em>, as taxas de variação e os valores em mg/dL "
        "não dependem dessa sincronia."
        "</div>"
    )


# ---------------------------------------------------------------------------
# Relatório completo
# ---------------------------------------------------------------------------


def render_html(analysis: Analysis, title: str = "Relatório de glicemia") -> str:
    """Monta o relatório HTML completo (autocontido)."""
    readings = analysis.dataset.readings
    descriptive = analysis.descriptive
    indicators = analysis.indicators
    monitoring = analysis.monitoring
    trend = analysis.trend
    tir = analysis.tir

    charts = {
        "serie": time_series_svg(readings),
        "tir": tir_donut_svg(tir),
        "histograma": histogram_svg(analysis.histogram),
        "horas": boxplot_svg(analysis.hourly),
        "faixa": day_strip_svg(readings),
        "tendencia": daily_trend_svg(analysis.daily, trend),
        "mapa": heatmap_svg(readings),
    }

    ref_items = [
        f"<li><strong>{_esc(name)}</strong> — {_esc(ref)}</li>"
        for name, ref in REFERENCES
    ]

    generated = datetime.now().strftime("%d/%m/%Y às %H:%M")
    period = ""
    if analysis.dataset.period[0] and analysis.dataset.period[1]:
        period = (
            f"{analysis.dataset.period[0].strftime('%d/%m/%Y')} a "
            f"{analysis.dataset.period[1].strftime('%d/%m/%Y')}"
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>{_esc(title)}</h1>
  { _device_block(analysis) }
  <p class="sub">Gerado em {generated}</p>
</header>

<div class="note">{DISCLAIMER}</div>
{_clock_note(analysis)}

<h2>Resumo</h2>
{_card_block(analysis)}

<h2>Alertas</h2>
{_alerts_block(analysis)}

<h2>Tempo em Faixa</h2>
<div class="grid-2">
  <div class="panel chart">{charts["tir"]}</div>
  <div>{_tir_table(tir)}</div>
</div>
<p class="sub">
  Meta de referência (T1D): &gt; 70% em faixa, &lt; 4% abaixo de 70 mg/dL,
  &lt; 1% abaixo de 54 mg/dL, &lt; 25% acima de 180 mg/dL.
  {'Atingida' if analysis.tir_meets_target else 'Não atingida'} neste conjunto.
</p>

<h2>Distribuição dos valores</h2>
<div class="panel chart">{charts["histograma"]}</div>

<h2>Evolução no tempo</h2>
<div class="panel chart">{charts["serie"]}</div>

<h2>Média diária e tendência</h2>
<div class="panel chart">{charts["tendencia"]}</div>
<p class="sub">
  Inclinação: <strong>{trend.slope:+.4f} mg/dL/dia</strong>
  ({trend.slope_per_month:+.2f} mg/dL/mês) · r² = {trend.r_squared:.3f} ·
  {trend.days} dia(s) com medição. A correlação é
  {'moderada ou forte' if trend.significant else 'fraca (variação normal)'}.
</p>

<h2>Perfil por hora do dia</h2>
<div class="panel chart">{charts["horas"]}</div>

<h2>Faixa horária das medições</h2>
<div class="panel chart">{charts["faixa"]}</div>

<h2>Mapa de calor (hora × dia da semana)</h2>
<div class="panel chart">{charts["mapa"]}</div>

<h2>Tabelas</h2>
{_profile_table("Por hora do dia", analysis.hourly, "Hora")}
{_profile_table("Por dia da semana", analysis.weekday, "Dia")}
{_hypo_table(analysis)}

<h2>Monitorização</h2>
<div class="panel">
  <table>
    <tbody>
      <tr><td>Intervalo mediano entre medições</td>
          <td>{monitoring.median_interval_hours:.1f} h</td></tr>
      <tr><td>Medições por dia (dias com medição)</td>
          <td>{monitoring.measurements_per_day:.1f}</td></tr>
      <tr><td>Dias com medição</td>
          <td>{monitoring.days_with_data} de {monitoring.total_span_days}</td></tr>
      <tr><td>Cobertura do período</td>
          <td>{monitoring.coverage_pct:.1f}%</td></tr>
      <tr><td>Desvio-padrão</td>
          <td>{descriptive.sd:.1f} mg/dL</td></tr>
      <tr><td>Coeficiente de variação</td>
          <td>{descriptive.cv:.1f}%</td></tr>
      <tr><td>Quartis (Q1 / Q3)</td>
          <td>{descriptive.q1:.0f} / {descriptive.q3:.0f} mg/dL</td></tr>
      <tr><td>GMI / eA1c (ADAG)</td>
          <td>{indicators.gmi:.1f}% / {indicators.ea1c_adag:.1f}%</td></tr>
      <tr><td>Média / mediana</td>
          <td>{descriptive.mean:.0f} / {descriptive.median:.0f} mg/dL</td></tr>
    </tbody>
  </table>
</div>

{_readings_table(readings)}

<h2>Referências</h2>
<div class="panel">
  <ul class="refs">
    {"".join(ref_items)}
  </ul>
</div>

<footer>
  <p>{DISCLAIMER}</p>
  <p>
    Gerado pelo <code>accuchek</code> — leitura direta do glicosímetro
    Roche Accu-Chek Active via USB (ISO/IEEE 11073-20601 / PHDC).
    {'Período: ' + _esc(period) if period else ''}
  </p>
</footer>

</div>
</body>
</html>
"""


def write_report(
    analysis: Analysis,
    path: str | Path,
    title: str = "Relatório de glicemia",
) -> Path:
    """Escreve o relatório HTML em ``path`` e devolve o caminho."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(analysis, title), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Resumo para o terminal
# ---------------------------------------------------------------------------


def terminal_summary(analysis: Analysis) -> str:
    """Resumo em texto, para o terminal (``show``)."""
    descriptive = analysis.descriptive
    indicators = analysis.indicators
    monitoring = analysis.monitoring
    trend = analysis.trend
    tir = analysis.tir
    meals = analysis.meals
    dawn = analysis.dawn

    lines: list[str] = []
    add = lines.append

    add("=" * 62)
    add("  RELATÓRIO DE GLICEMIA — Roche Accu-Chek Active")
    add("=" * 62)

    first, last = analysis.dataset.period
    if first and last:
        add(
            f"  Período   : {first.strftime('%d/%m/%Y')} → "
            f"{last.strftime('%d/%m/%Y')}  ({descriptive.n} leituras)"
        )
    device = analysis.dataset.device or {}
    if device.get("model"):
        add(
            f"  Aparelho  : {device.get('model')}"
            + (f"  serial {device['serial']}" if device.get("serial") else "")
        )
    add("")

    add("  ESTATÍSTICAS")
    add(
        f"    média  {descriptive.mean:7.1f} mg/dL  "
        f"({descriptive.mean_mmol:.1f} mmol/L)"
    )
    add(f"    mediana{descriptive.median:7.1f} mg/dL")
    add(f"    desvio {descriptive.sd:7.1f} mg/dL   CV {descriptive.cv:.1f}%")
    add(
        f"    Q1/Q3  {descriptive.q1:.0f} / {descriptive.q3:.0f} mg/dL"
        f"   IQR {descriptive.iqr:.0f}"
    )
    add(
        f"    mín/máx {descriptive.min:.0f} / {descriptive.max:.0f} mg/dL"
        f"   amplitude {descriptive.amplitude:.0f}"
    )
    add(f"    GMI {indicators.gmi:.2f}%   eA1c (ADAG) {indicators.ea1c_adag:.2f}%")
    add("")

    add("  TEMPO EM FAIXA (70-180 mg/dL)")
    for key in BAND_ORDER:
        add(
            f"    {BAND_LABELS[key]:<12} {tir.count(key):>4}  "
            f"{tir.percentage(key):>5.1f}%"
        )
    add(
        f"    meta (> 70% em faixa): "
        f"{'ATINGIDA' if analysis.tir_meets_target else 'não atingida'}"
    )
    add("")

    add("  HIPOGLICEMIA")
    add(
        f"    < 70 mg/dL: {analysis.hypoglycemia.below_70} "
        f"({analysis.hypoglycemia.below_70_pct:.1f}%)"
    )
    add(
        f"    < 54 mg/dL: {analysis.hypoglycemia.below_54} "
        f"({analysis.hypoglycemia.below_54_pct:.1f}%)"
    )
    add(f"    maior sequência consecutiva: {analysis.hypoglycemia.longest_run}")
    add("")

    add("  MONITORIZAÇÃO")
    add(f"    intervalo mediano      {monitoring.median_interval_hours:.1f} h")
    add(f"    medições por dia       {monitoring.measurements_per_day:.1f}")
    add(
        f"    cobertura do período   {monitoring.days_with_data}/"
        f"{monitoring.total_span_days} dias"
        f" ({monitoring.coverage_pct:.1f}%)"
    )
    add("")

    add("  CONTEXTO (aproximado, sem marcadores de refeição)")
    if meals.fasting_mean is not None:
        add(
            f"    jejum (1ª do dia, < 10h)  {meals.fasting_mean:7.1f} mg/dL"
            f"  (n={len(meals.fasting)})"
        )
    if meals.postprandial_mean is not None:
        add(
            f"    pós-prandial (+1,5 a +3h) {meals.postprandial_mean:7.1f} mg/dL"
            f"  (n={len(meals.postprandial)})"
        )
    add(f"    demais leituras          {len(meals.other)}")  # noqa: E501
    if dawn.first_half_mean == dawn.first_half_mean:  # não-NaN
        add(
            f"    madrugada (0-6h) 1ª metade {dawn.first_half_mean:.1f} → "
            f"2ª metade {dawn.second_half_mean:.1f} mg/dL "
            f"(Δ {dawn.difference:+.1f})"
        )
    add("")

    add("  TENDÊNCIA")
    add(
        f"    {trend.slope:+.4f} mg/dL/dia ({trend.slope_per_month:+.2f} mg/dL/mês)"
        f"   r² = {trend.r_squared:.3f}   ({trend.days} dias)"
    )
    add("")

    if analysis.alerts:
        add("  ALERTAS")
        for message in analysis.alerts:
            add(f"    ! {message}")
        add("")

    add("-" * 62)
    add("  Aviso: dados de glicosímetro (SMBG), não de CGM. TIR, GMI e")
    add("  variabilidade são aproximações. Não é diagnóstico.")
    add("-" * 62)

    return "\n".join(lines)

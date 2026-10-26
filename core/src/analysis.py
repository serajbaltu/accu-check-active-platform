"""Estatísticas e métricas clínicas sobre as leituras de glicemia.

Este módulo é **puro**: recebe leituras (ou o JSON do ``dump``) e devolve
dataclasses com os números. Nada de I/O, nada de rede, nada de UI — o
relatório visual vive em :mod:`src.charts` e :mod:`src.report`.

⚠️ **Ressalva clínica importante.** Os dados vêm de um **glicosímetro
(SMBG)**, não de um sensor contínuo (CGM). O *Tempo em Faixa* (TIR) foi
definido para CGM de 24 h; aplicado a glicosímetro, ele é uma **aproximação**
e subestima a variabilidade real. O mesmo vale para o GMI e para a
interpretação da variabilidade. Nada aqui é diagnóstico nem orientação de
tratamento.

Referências das fórmulas (ver também ``docs/estudos.md``):

* **GMI** = ``3.31 + 0.02392 × média mg/dL``
  — Bergenstal et al., *Diabetes Care* 2018;41(11):2275-2280,
  DOI `10.2337/dc18-1581`.
* **eA1c (ADAG)** = ``(média mg/dL + 46.7) / 28.7``
  — Nathan et al., *Diabetes Care* 2008;31(8):1571-1580.
* **Faixas do TIR** — Battelino et al., *Diabetes Care* 2019;42(8):1593-1603.
* **CV** (coeficiente de variação) — instabilidade se > 36%
  (Danne et al., *Diabetes Care* 2017;40(6):1591-1603).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from statistics import fmean, median, stdev
from typing import Final

# ---------------------------------------------------------------------------
# Constantes clínicas
# ---------------------------------------------------------------------------

#: Fator de conversão de mg/dL para mmol/L.
MGDL_PER_MMOL: Final = 18.0

#: Faixas do Tempo em Faixa (Battelino 2019), em mg/dL.
TIR_BANDS: Final = (
    ("very_low", "Muito baixa", 0.0, 54.0),
    ("low", "Baixa", 54.0, 70.0),
    ("in_range", "Em faixa", 70.0, 180.0),
    ("high", "Alta", 180.0, 250.0),
    ("very_high", "Muito alta", 250.0, float("inf")),
)

#: Metas de TIR para um adulto com diabetes tipo 1 (insulina).
TIR_TARGETS_T1D: Final = {
    "very_low": 0.04,
    "low": 0.01,
    "in_range": 0.70,
    "high": 0.25,
    "very_high": 0.05,
}

#: Coeficiente de variação acima do qual se considera variabilidade alta.
CV_HIGH_THRESHOLD: Final = 36.0

#: Janela (em horas) em que se procura a leitura pós-prandial de um dia.
POSTPRANDIAL_WINDOW: Final = (1.5, 3.0)

#: Hora-limite (inclusive) para considerar uma leitura como "de manhã".
MORNING_HOUR_LIMIT: Final = 10


def mgdl_to_mmol(value_mgdl: float) -> float:
    """Converte mg/dL para mmol/L."""
    return value_mgdl / MGDL_PER_MMOL


# ---------------------------------------------------------------------------
# Modelo de dados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Reading:
    """Uma leitura de glicemia, já normalizada."""

    timestamp: datetime
    value_mgdl: int
    out_of_range: str | None = None

    @property
    def value_mmol(self) -> float:
        """Valor em mmol/L."""
        return mgdl_to_mmol(self.value_mgdl)

    @property
    def date(self) -> date:
        """Dia da leitura (sem hora)."""
        return self.timestamp.date()

    @property
    def day_index(self) -> int:
        """Dias desde 1 de janeiro de 1970 (para regressões)."""
        return (self.timestamp - datetime(1970, 1, 1)).days


@dataclass
class Dataset:
    """Um conjunto de leituras, com as informações do aparelho."""

    readings: list[Reading] = field(default_factory=list)
    device: dict = field(default_factory=dict)
    read_at: datetime | None = None

    @property
    def n(self) -> int:
        """Número de leituras."""
        return len(self.readings)

    @property
    def period(self) -> tuple[datetime | None, datetime | None]:
        """Primeira e última leitura."""
        if not self.readings:
            return (None, None)
        return (self.readings[0].timestamp, self.readings[-1].timestamp)


def reading_from_dict(data: dict) -> Reading:
    """Converte um registro do JSON do ``dump`` em :class:`Reading`."""
    stamp = data.get("timestamp")
    when = (
        datetime.fromisoformat(stamp)
        if stamp
        else datetime.fromtimestamp(data["epoch"], tz=None)
    )
    return Reading(
        timestamp=when,
        value_mgdl=int(data["mg/dL"]),
        out_of_range=data.get("out_of_range"),
    )


def dataset_from_payload(payload: dict) -> Dataset:
    """Converte o JSON do ``dump`` (dicionário) em :class:`Dataset`."""
    records = payload.get("records", [])
    readings = sorted(
        (reading_from_dict(item) for item in records),
        key=lambda r: r.timestamp,
    )
    read_at = payload.get("read_at")
    return Dataset(
        readings=readings,
        device=dict(payload.get("device", {})),
        read_at=datetime.fromisoformat(read_at) if read_at else None,
    )


def load_dataset(path: str | Path) -> Dataset:
    """Lê o JSON do ``dump`` do disco e devolve um :class:`Dataset`."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return dataset_from_payload(payload)


# ---------------------------------------------------------------------------
# Estatísticas descritivas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Descriptive:
    """Estatísticas descritivas de um conjunto de leituras."""

    n: int
    mean: float
    median: float
    sd: float
    cv: float
    q1: float
    q3: float
    iqr: float
    min: float
    max: float
    amplitude: float
    mean_mmol: float
    median_mmol: float

    @property
    def cv_high(self) -> bool:
        """True se a variabilidade for alta (CV > 36%)."""
        return self.cv > CV_HIGH_THRESHOLD

    @property
    def high_variability(self) -> bool:
        """Alias explícito de :attr:`cv_high`."""
        return self.cv_high


def _quantile(values: Sequence[float], fraction: float) -> float:
    """Quantil por interpolação linear (método 7, o mesmo do numpy)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[int(position)])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def describe(readings: Iterable[Reading]) -> Descriptive:
    """Calcula as estatísticas descritivas.

    O desvio-padrão é **amostral** (n-1) quando há 2 ou mais leituras.
    """
    values = [float(r.value_mgdl) for r in readings]
    n = len(values)
    if n == 0:
        nan = float("nan")
        return Descriptive(
            0, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan
        )

    mean = fmean(values)
    sd = stdev(values) if n > 1 else 0.0
    q1 = _quantile(values, 0.25)
    q3 = _quantile(values, 0.75)
    return Descriptive(
        n=n,
        mean=mean,
        median=median(values),
        sd=sd,
        cv=(sd / mean * 100.0) if mean else float("nan"),
        q1=q1,
        q3=q3,
        iqr=q3 - q1,
        min=min(values),
        max=max(values),
        amplitude=max(values) - min(values),
        mean_mmol=mgdl_to_mmol(mean),
        median_mmol=mgdl_to_mmol(median(values)),
    )


# ---------------------------------------------------------------------------
# Tempo em faixa (TIR)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeInRange:
    """Distribuição das leituras pelas faixas do TIR."""

    counts: dict[str, int]
    total: int

    def count(self, key: str) -> int:
        """Número de leituras numa faixa."""
        return self.counts.get(key, 0)

    def percentage(self, key: str) -> float:
        """Percentual de leituras numa faixa (0 a 100)."""
        if not self.total:
            return 0.0
        return self.counts.get(key, 0) / self.total * 100.0

    @property
    def in_range_pct(self) -> float:
        """Percentual dentro da faixa-alvo (70-180 mg/dL)."""
        return self.percentage("in_range")

    @property
    def below_range_pct(self) -> float:
        """Percentual abaixo de 70 mg/dL."""
        return self.percentage("very_low") + self.percentage("low")

    @property
    def above_range_pct(self) -> float:
        """Percentual acima de 180 mg/dL."""
        return self.percentage("high") + self.percentage("very_high")


def time_in_range(readings: Iterable[Reading]) -> TimeInRange:
    """Classifica as leituras nas faixas do TIR."""
    counts = {key: 0 for key, _, _, _ in TIR_BANDS}
    items = list(readings)
    for reading in items:
        value = float(reading.value_mgdl)
        for key, _, low, high in TIR_BANDS:
            if low <= value < high:
                counts[key] += 1
                break
    return TimeInRange(counts=counts, total=len(items))


# ---------------------------------------------------------------------------
# Indicadores glicêmicos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GlycemicIndicators:
    """GMI, eA1c e média de glicemia."""

    mean_mgdl: float
    gmi: float
    ea1c_adag: float

    @property
    def mean_mmol(self) -> float:
        """Média em mmol/L."""
        return mgdl_to_mmol(self.mean_mgdl)


def glycemic_indicators(readings: Iterable[Reading]) -> GlycemicIndicators:
    """Calcula GMI e eA1c (ADAG) a partir da média das leituras.

    O **GMI** (Glucose Management Indicator) substituiu o "eA1c" na prática
    porque a FDA proíbe o nome "eA1c" e porque o GMI não promete igualar a
    HbA1c de laboratório. As duas fórmulas são parecidas; a diferença está
    na constante.
    """
    values = [float(r.value_mgdl) for r in readings]
    if not values:
        return GlycemicIndicators(float("nan"), float("nan"), float("nan"))
    mean = fmean(values)
    return GlycemicIndicators(
        mean_mgdl=mean,
        gmi=3.31 + 0.02392 * mean,
        ea1c_adag=(mean + 46.7) / 28.7,
    )


# ---------------------------------------------------------------------------
# Hipoglicemia
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hypoglycemia:
    """Índice de hipoglicemia."""

    below_70: int
    below_54: int
    below_70_pct: float
    below_54_pct: float
    longest_run: int
    """Maior sequência de leituras consecutivas abaixo de 70 mg/dL."""
    severe_events: list[Reading] = field(default_factory=list)
    """Leituras abaixo de 54 mg/dL (eventos graves)."""

    @property
    def has_events(self) -> bool:
        """True se houve ao menos um evento abaixo de 70 mg/dL."""
        return self.below_70 > 0


def hypoglycemia_index(readings: Iterable[Reading]) -> Hypoglycemia:
    """Conta eventos de hipoglicemia e a maior sequência consecutiva.

    A sequência considera leituras **consecutivas na lista** (ordenada por
    tempo), sem olhar para o intervalo entre elas: em glicosímetro, uma
    sequência de medições baixas com 30 min de intervalo conta como um
    mesmo episódio.
    """
    items = sorted(readings, key=lambda r: r.timestamp)
    total = len(items)
    below_70 = [r for r in items if r.value_mgdl < 70]
    below_54 = [r for r in items if r.value_mgdl < 54]
    severe = [r for r in items if r.value_mgdl < 54]

    longest = 0
    current = 0
    for reading in items:
        if reading.value_mgdl < 70:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return Hypoglycemia(
        below_70=len(below_70),
        below_54=len(below_54),
        below_70_pct=(len(below_70) / total * 100.0) if total else 0.0,
        below_54_pct=(len(below_54) / total * 100.0) if total else 0.0,
        longest_run=longest,
        severe_events=severe,
    )


# ---------------------------------------------------------------------------
# Séries temporais
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyPoint:
    """Resumo de um dia de medições."""

    day: date
    count: int
    mean: float
    min: float
    max: float


def daily_means(readings: Iterable[Reading]) -> list[DailyPoint]:
    """Média, mínimo e máximo por dia, em ordem cronológica."""
    buckets: dict[date, list[float]] = {}
    for reading in readings:
        buckets.setdefault(reading.date, []).append(float(reading.value_mgdl))
    points = [
        DailyPoint(
            day=day,
            count=len(values),
            mean=fmean(values),
            min=min(values),
            max=max(values),
        )
        for day, values in buckets.items()
    ]
    return sorted(points, key=lambda p: p.day)


@dataclass(frozen=True)
class Trend:
    """Tendência linear das médias diárias."""

    slope: float
    """Variação em mg/dL por dia (positivo = glicemia subindo)."""
    intercept: float
    r_squared: float
    days: int
    first_day: date | None
    last_day: date | None

    @property
    def slope_per_month(self) -> float:
        """Variação em mg/dL por mês (30 dias)."""
        return self.slope * 30.0

    @property
    def significant(self) -> bool:
        """True se a correlação é pelo menos moderada (r² >= 0.25)."""
        return self.r_squared >= 0.25


def linear_trend(readings: Iterable[Reading]) -> Trend:
    """Regressão linear das médias diárias (x = dias desde o início).

    É a mesma forma usada nos estudos de tendência de glicemia: cada ponto é
    a média das leituras de um dia, e a reta ajustada indica a direção da
    tendência.
    """
    points = daily_means(readings)
    if len(points) < 2:
        nan = float("nan")
        return Trend(nan, nan, nan, len(points), None, None)

    origin = points[0].day
    xs = [(p.day - origin).days for p in points]
    ys = [p.mean for p in points]
    n = len(xs)

    mean_x = fmean(xs)
    mean_y = fmean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)
    )
    if sxx == 0:
        nan = float("nan")
        return Trend(nan, nan, nan, n, points[0].day, points[-1].day)

    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    syy = sum((y - mean_y) ** 2 for y in ys)
    r_squared = (sxy**2) / (sxx * syy) if syy else 0.0

    return Trend(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        days=n,
        first_day=points[0].day,
        last_day=points[-1].day,
    )


@dataclass(frozen=True)
class HourProfile:
    """Estatísticas de uma faixa horária (ou de um dia da semana)."""

    label: str
    count: int
    mean: float
    median: float
    q1: float
    q3: float
    min: float
    max: float
    slot: int | None = None
    """Posição na grade: hora do dia (0-23) ou dia da semana (0=segunda)."""


def hourly_profile(readings: Iterable[Reading]) -> list[HourProfile]:
    """Perfil por hora do dia (0-23), com o boxplot de cada hora."""
    buckets: dict[int, list[float]] = {hour: [] for hour in range(24)}
    for reading in readings:
        buckets[reading.timestamp.hour].append(float(reading.value_mgdl))

    profiles: list[HourProfile] = []
    for hour in range(24):
        values = buckets[hour]
        if not values:
            continue
        profiles.append(
            HourProfile(
                label=f"{hour:02d}h",
                count=len(values),
                mean=fmean(values),
                median=median(values),
                q1=_quantile(values, 0.25),
                q3=_quantile(values, 0.75),
                min=min(values),
                max=max(values),
                slot=hour,
            )
        )
    return profiles


#: Nomes dos dias da semana em português, segunda primeiro.
WEEKDAY_NAMES: Final = (
    "Segunda",
    "Terça",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sábado",
    "Domingo",
)


def weekday_profile(readings: Iterable[Reading]) -> list[HourProfile]:
    """Perfil por dia da semana (segunda primeiro)."""
    buckets: dict[int, list[float]] = {i: [] for i in range(7)}
    for reading in readings:
        buckets[reading.timestamp.weekday()].append(float(reading.value_mgdl))

    profiles: list[HourProfile] = []
    for weekday in range(7):
        values = buckets[weekday]
        if not values:
            continue
        profiles.append(
            HourProfile(
                label=WEEKDAY_NAMES[weekday],
                count=len(values),
                mean=fmean(values),
                median=median(values),
                q1=_quantile(values, 0.25),
                q3=_quantile(values, 0.75),
                min=min(values),
                max=max(values),
                slot=weekday,
            )
        )
    return profiles


@dataclass(frozen=True)
class MealContext:
    """Leituras agrupadas por contexto de refeição (aproximado)."""

    fasting: list[Reading]
    postprandial: list[Reading]
    other: list[Reading]

    @property
    def fasting_mean(self) -> float | None:
        """Média das leituras em jejum."""
        if not self.fasting:
            return None
        return fmean(float(r.value_mgdl) for r in self.fasting)

    @property
    def postprandial_mean(self) -> float | None:
        """Média das leituras pós-prandiais."""
        if not self.postprandial:
            return None
        return fmean(float(r.value_mgdl) for r in self.postprandial)


def classify_by_meal(readings: Iterable[Reading]) -> MealContext:
    """Separa jejum e pós-prandial **sem** marcadores de refeição.

    ⚠️ Heurística, não dado real. O aparelho tem um segmento de refeições
    (``PMSegMeal``) que ainda não é lido; enquanto isso, a classificação é:

    * **jejum**: a primeira leitura do dia, feita antes das 10h;
    * **pós-prandial**: leituras entre 1,5 h e 3 h depois dessa primeira
      leitura do dia;
    * as demais ficam como "outras".
    """
    items = sorted(readings, key=lambda r: r.timestamp)
    by_day: dict[date, list[Reading]] = {}
    for reading in items:
        by_day.setdefault(reading.date, []).append(reading)

    fasting: list[Reading] = []
    postprandial: list[Reading] = []
    other: list[Reading] = []

    for day_readings in by_day.values():
        first = day_readings[0]
        if first.timestamp.hour <= MORNING_HOUR_LIMIT:
            fasting.append(first)
        anchor = first.timestamp
        for reading in day_readings:
            if reading is first:
                continue
            delta = (reading.timestamp - anchor).total_seconds() / 3600.0
            if POSTPRANDIAL_WINDOW[0] <= delta <= POSTPRANDIAL_WINDOW[1]:
                postprandial.append(reading)
            else:
                other.append(reading)

    return MealContext(fasting=fasting, postprandial=postprandial, other=other)


@dataclass(frozen=True)
class DawnEffect:
    """Efeito "dawn phenomenon": média das leituras matinais ao longo dos dias."""

    first_half_mean: float
    second_half_mean: float
    difference: float
    n_days: int


def dawn_effect(readings: Iterable[Reading]) -> DawnEffect:
    """Compara a média das leituras matinais da 1ª e da 2ª metade do período.

    O *dawn phenomenon* é o aumento da glicemia de madrugada associado à
    liberação de hormônios contrarreguladores. Como o aparelho só tem
    leituras pontuais, usamos as leituras feitas **de madrugada/early morning**
    (00h-06h) e comparamos a primeira metade do período com a segunda.
    """
    points = daily_means(readings)
    if len(points) < 2:
        nan = float("nan")
        return DawnEffect(nan, nan, nan, len(points))

    early: list[float] = []
    for reading in readings:
        if reading.timestamp.hour < 6:
            early.append(float(reading.value_mgdl))
    if len(early) < 2:
        return DawnEffect(float("nan"), float("nan"), float("nan"), len(points))

    half = len(points) // 2
    first_days = {p.day for p in points[:half]}
    second_days = {p.day for p in points[half:]}

    first_values = [
        float(r.value_mgdl)
        for r in readings
        if r.timestamp.hour < 6 and r.date in first_days
    ]
    second_values = [
        float(r.value_mgdl)
        for r in readings
        if r.timestamp.hour < 6 and r.date in second_days
    ]

    if not first_values or not second_values:
        return DawnEffect(float("nan"), float("nan"), float("nan"), len(points))

    first_mean = fmean(first_values)
    second_mean = fmean(second_values)
    return DawnEffect(
        first_half_mean=first_mean,
        second_half_mean=second_mean,
        difference=second_mean - first_mean,
        n_days=len(points),
    )


# ---------------------------------------------------------------------------
# Monitorização
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Monitoring:
    """Como e quando o usuário mediu."""

    median_interval_hours: float
    """Intervalo mediano entre medições, em horas."""
    measurements_per_day: float
    """Média de medições por dia (somente dias com medição)."""
    days_with_data: int
    total_span_days: int
    coverage_pct: float
    """Percentual dos dias do período em que houve pelo menos uma medição."""
    hour_histogram: dict[int, int]
    """Contagem de leituras por hora do dia."""


def monitoring_profile(readings: Iterable[Reading]) -> Monitoring:
    """Resume a frequência e a cobertura das medições."""
    items = sorted(readings, key=lambda r: r.timestamp)
    if not items:
        return Monitoring(0.0, 0.0, 0, 0, 0.0, {})

    gaps = [
        (b.timestamp - a.timestamp).total_seconds() / 3600.0
        for a, b in zip(items, items[1:], strict=False)
    ]
    days = {r.date for r in items}
    if len(items) > 1:
        span = (items[-1].timestamp - items[0].timestamp).total_seconds() / 86400.0
    else:
        span = 0.0
    total_days = int(round(span)) + 1

    histogram = Counter(r.timestamp.hour for r in items)

    return Monitoring(
        median_interval_hours=median(gaps) if gaps else 0.0,
        measurements_per_day=len(items) / len(days) if days else 0.0,
        days_with_data=len(days),
        total_span_days=total_days,
        coverage_pct=(len(days) / total_days * 100.0) if total_days else 0.0,
        hour_histogram=dict(sorted(histogram.items())),
    )


# ---------------------------------------------------------------------------
# Histograma
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistogramBin:
    """Uma barra do histograma de valores."""

    low: float
    high: float
    count: int

    @property
    def label(self) -> str:
        """Rótulo "a–b" da barra."""
        if math.isinf(self.high):
            return f"≥{self.low:.0f}"
        return f"{self.low:.0f}–{self.high:.0f}"


def histogram(readings: Iterable[Reading], bins: int = 12) -> list[HistogramBin]:
    """Histograma dos valores, com larguras iguais."""
    values = [float(r.value_mgdl) for r in readings]
    if not values:
        return []

    low = min(values)
    high = max(values)
    if high == low:
        return [HistogramBin(low, high, len(values))]

    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1

    return [
        HistogramBin(low + i * width, low + (i + 1) * width, counts[i])
        for i in range(bins)
    ]


# ---------------------------------------------------------------------------
# Resumo completo
# ---------------------------------------------------------------------------


@dataclass
class Analysis:
    """Todos os resultados de uma análise, num objeto só."""

    dataset: Dataset
    descriptive: Descriptive
    tir: TimeInRange
    indicators: GlycemicIndicators
    hypoglycemia: Hypoglycemia
    trend: Trend
    daily: list[DailyPoint]
    hourly: list[HourProfile]
    weekday: list[HourProfile]
    meals: MealContext
    dawn: DawnEffect
    monitoring: Monitoring
    histogram: list[HistogramBin]

    @property
    def tir_meets_target(self) -> bool:
        """True se o TIR cumpre a meta de >70% em faixa (aproximação SMBG)."""
        return self.tir.in_range_pct > TIR_TARGETS_T1D["in_range"] * 100.0

    @property
    def alerts(self) -> list[str]:
        """Alertas clínicos curtos, para destaque no relatório."""
        messages: list[str] = []
        if self.hypoglycemia.below_54:
            messages.append(
                f"{self.hypoglycemia.below_54} leitura(s) abaixo de 54 mg/dL "
                "(hipoglicemia grave) — converse com o seu médico."
            )
        if self.hypoglycemia.below_70:
            messages.append(
                f"{self.hypoglycemia.below_70} leitura(s) abaixo de 70 mg/dL "
                f"({self.hypoglycemia.below_70_pct:.1f}% do total)."
            )
        if self.descriptive.cv_high:
            messages.append(
                f"Variabilidade alta (CV {self.descriptive.cv:.1f}% > 36%)."
            )
        if self.tir.in_range_pct < 70.0:
            messages.append(
                f"Tempo em faixa de {self.tir.in_range_pct:.1f}% "
                "(meta: > 70%) — estimativa a partir de glicosímetro."
            )
        if self.indicators.gmi >= 9.0:
            messages.append(
                f"GMI de {self.indicators.gmi:.1f}% acima da meta de 7% "
                "usada no ensaio STeP."
            )
        return messages


def analyze(dataset: Dataset) -> Analysis:
    """Roda todas as análises sobre um :class:`Dataset`."""
    readings = dataset.readings
    return Analysis(
        dataset=dataset,
        descriptive=describe(readings),
        tir=time_in_range(readings),
        indicators=glycemic_indicators(readings),
        hypoglycemia=hypoglycemia_index(readings),
        trend=linear_trend(readings),
        daily=daily_means(readings),
        hourly=hourly_profile(readings),
        weekday=weekday_profile(readings),
        meals=classify_by_meal(readings),
        dawn=dawn_effect(readings),
        monitoring=monitoring_profile(readings),
        histogram=histogram(readings),
    )

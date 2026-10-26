"""Testes do módulo de análise (:mod:`src.analysis`)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest
from src.analysis import (
    CV_HIGH_THRESHOLD,
    MGDL_PER_MMOL,
    Analysis,
    Dataset,
    Reading,
    analyze,
    classify_by_meal,
    daily_means,
    dawn_effect,
    describe,
    glycemic_indicators,
    histogram,
    hourly_profile,
    hypoglycemia_index,
    linear_trend,
    load_dataset,
    mgdl_to_mmol,
    monitoring_profile,
    time_in_range,
    weekday_profile,
)


def make_readings(values: list[int], start: datetime | None = None) -> list[Reading]:
    """Cria leituras espaçadas de 12 h a partir de ``start``."""
    base = start or datetime(2023, 1, 1, 8, 0)
    return [
        Reading(
            timestamp=base + timedelta(hours=12 * index),
            value_mgdl=value,
        )
        for index, value in enumerate(values)
    ]


class TestConversion:
    def test_mgdl_to_mmol(self):
        assert mgdl_to_mmol(180) == pytest.approx(10.0)
        assert mgdl_to_mmol(90) == pytest.approx(5.0)

    def test_factor(self):
        assert MGDL_PER_MMOL == 18.0


class TestDescribe:
    def test_empty(self):
        stats = describe([])
        assert stats.n == 0
        assert math.isnan(stats.mean)

    def test_single(self):
        stats = describe(make_readings([100]))
        assert stats.n == 1
        assert stats.mean == 100
        assert stats.sd == 0.0
        assert stats.cv == 0.0

    def test_values(self):
        stats = describe(make_readings([90, 110, 130, 150]))
        assert stats.n == 4
        assert stats.mean == pytest.approx(120)
        assert stats.median == pytest.approx(120)
        assert stats.min == 90
        assert stats.max == 150
        assert stats.amplitude == 60
        assert stats.mean_mmol == pytest.approx(120 / 18)

    def test_sd_is_sample(self):
        stats = describe(make_readings([100, 200]))
        # desvio amostral de [100, 200] = 70.71 (não 50)
        assert stats.sd == pytest.approx(70.7107, rel=1e-3)

    def test_cv_flag(self):
        low = describe(make_readings([98, 100, 102, 104]))
        high = describe(make_readings([50, 200, 60, 210]))
        assert low.cv < CV_HIGH_THRESHOLD
        assert high.cv > CV_HIGH_THRESHOLD
        assert low.cv_high is False
        assert high.cv_high is True

    def test_quantiles(self):
        stats = describe(make_readings(list(range(1, 101))))
        assert stats.q1 == pytest.approx(25.5, abs=1.0)
        assert stats.q3 == pytest.approx(75.5, abs=1.0)
        assert stats.iqr == pytest.approx(stats.q3 - stats.q1)


class TestTimeInRange:
    def test_bands(self):
        readings = make_readings([40, 60, 100, 200, 300])
        tir = time_in_range(readings)
        assert tir.total == 5
        assert tir.count("very_low") == 1
        assert tir.count("low") == 1
        assert tir.count("in_range") == 1
        assert tir.count("high") == 1
        assert tir.count("very_high") == 1

    def test_percentages(self):
        readings = make_readings([100, 100, 100, 50])
        tir = time_in_range(readings)
        assert tir.in_range_pct == pytest.approx(75.0)
        assert tir.below_range_pct == pytest.approx(25.0)
        assert tir.above_range_pct == pytest.approx(0.0)

    def test_boundaries(self):
        # 54 entra em "low", 70 entra em "in_range", 180 em "high"
        tir = time_in_range(make_readings([54, 70, 180]))
        assert tir.count("low") == 1
        assert tir.count("in_range") == 1
        assert tir.count("high") == 1

    def test_empty(self):
        tir = time_in_range([])
        assert tir.total == 0
        assert tir.in_range_pct == 0.0


class TestIndicators:
    def test_gmi_formula(self):
        indicators = glycemic_indicators(make_readings([150]))
        assert indicators.gmi == pytest.approx(3.31 + 0.02392 * 150)
        assert indicators.ea1c_adag == pytest.approx((150 + 46.7) / 28.7)

    def test_known_gmi(self):
        # média 154 mg/dL -> GMI ~7.0% (Bergenstal et al.)
        indicators = glycemic_indicators(make_readings([154, 154]))
        assert indicators.gmi == pytest.approx(6.99, abs=0.05)

    def test_empty(self):
        indicators = glycemic_indicators([])
        assert math.isnan(indicators.gmi)


class TestHypoglycemia:
    def test_counts(self):
        readings = make_readings([50, 60, 80, 45, 120])
        hypo = hypoglycemia_index(readings)
        assert hypo.below_70 == 3
        assert hypo.below_54 == 2
        assert hypo.has_events is True

    def test_longest_run(self):
        readings = make_readings([50, 60, 65, 80, 55, 58])
        hypo = hypoglycemia_index(readings)
        assert hypo.longest_run == 3

    def test_no_events(self):
        hypo = hypoglycemia_index(make_readings([100, 120]))
        assert hypo.below_70 == 0
        assert hypo.has_events is False
        assert hypo.longest_run == 0

    def test_percentages(self):
        hypo = hypoglycemia_index(make_readings([50, 100, 100, 100]))
        assert hypo.below_70_pct == pytest.approx(25.0)
        assert hypo.below_54_pct == pytest.approx(25.0)


class TestDailyAndTrend:
    def test_daily_means(self):
        readings = make_readings(
            [100, 120, 200],
            start=datetime(2023, 1, 1, 8, 0),
        )
        points = daily_means(readings)
        assert len(points) == 2
        assert points[0].day == datetime(2023, 1, 1).date()
        assert points[0].count == 2
        assert points[0].mean == pytest.approx(110)
        assert points[0].min == 100
        assert points[0].max == 120

    def test_upward_trend(self):
        base = datetime(2023, 1, 1, 8, 0)
        readings = [
            Reading(timestamp=base + timedelta(days=i), value_mgdl=100 + 5 * i)
            for i in range(20)
        ]
        trend = linear_trend(readings)
        assert trend.slope == pytest.approx(5.0)
        assert trend.r_squared == pytest.approx(1.0)
        assert trend.significant is True
        assert trend.slope_per_month == pytest.approx(150.0)

    def test_flat_trend(self):
        base = datetime(2023, 1, 1, 8, 0)
        readings = [
            Reading(timestamp=base + timedelta(days=i), value_mgdl=120)
            for i in range(10)
        ]
        trend = linear_trend(readings)
        assert trend.slope == pytest.approx(0.0)
        assert trend.r_squared == pytest.approx(0.0)
        assert trend.significant is False

    def test_insufficient_points(self):
        trend = linear_trend(make_readings([100]))
        assert math.isnan(trend.slope)


class TestProfiles:
    def test_hourly_profile(self):
        readings = make_readings([100, 200], start=datetime(2023, 1, 1, 9, 0))
        profiles = hourly_profile(readings)
        assert len(profiles) == 2
        assert profiles[0].label == "09h"
        assert profiles[0].slot == 9
        assert profiles[0].count == 1
        assert profiles[1].slot == 21

    def test_weekday_profile(self):
        # 2023-01-02 é uma segunda-feira
        readings = make_readings([100], start=datetime(2023, 1, 2, 8, 0))
        profiles = weekday_profile(readings)
        assert len(profiles) == 1
        assert profiles[0].label == "Segunda"
        assert profiles[0].slot == 0


class TestMealContext:
    def test_classification(self):
        base = datetime(2023, 1, 1, 7, 0)
        readings = [
            Reading(timestamp=base, value_mgdl=100),  # jejum
            # pós-prandial
            Reading(timestamp=base + timedelta(hours=2), value_mgdl=140),
            Reading(timestamp=base + timedelta(hours=5), value_mgdl=120),  # outra
        ]
        meals = classify_by_meal(readings)
        assert len(meals.fasting) == 1
        assert len(meals.postprandial) == 1
        assert len(meals.other) == 1
        assert meals.fasting_mean == pytest.approx(100)
        assert meals.postprandial_mean == pytest.approx(140)


class TestDawnEffect:
    def test_comparison(self):
        base = datetime(2023, 1, 1, 2, 0)
        readings = [
            Reading(timestamp=base + timedelta(days=i), value_mgdl=100 + 10 * i)
            for i in range(10)
        ]
        dawn = dawn_effect(readings)
        assert dawn.n_days == 10
        assert not math.isnan(dawn.difference)
        assert dawn.second_half_mean > dawn.first_half_mean

    def test_not_enough_data(self):
        dawn = dawn_effect(make_readings([100], start=datetime(2023, 1, 1, 2, 0)))
        assert math.isnan(dawn.difference)


class TestMonitoring:
    def test_profile(self):
        readings = make_readings([100] * 5, start=datetime(2023, 1, 1, 8, 0))
        monitoring = monitoring_profile(readings)
        assert monitoring.median_interval_hours == pytest.approx(12.0)
        assert monitoring.days_with_data == 3
        assert monitoring.measurements_per_day == pytest.approx(5 / 3)

    def test_empty(self):
        monitoring = monitoring_profile([])
        assert monitoring.days_with_data == 0
        assert monitoring.total_span_days == 0
        assert monitoring.median_interval_hours == 0.0


class TestHistogram:
    def test_counts(self):
        bins = histogram(make_readings([10, 20, 30, 40]), bins=2)
        assert len(bins) == 2
        assert sum(b.count for b in bins) == 4

    def test_constant_values(self):
        bins = histogram(make_readings([100, 100]), bins=6)
        assert len(bins) == 1
        assert bins[0].count == 2

    def test_labels(self):
        bins = histogram(make_readings([0, 100]), bins=2)
        assert "–" in bins[0].label


class TestAnalyze:
    def test_full_analysis(self):
        dataset = Dataset(readings=make_readings([100, 120, 60, 200]))
        result = analyze(dataset)
        assert isinstance(result, Analysis)
        assert result.descriptive.n == 4
        assert result.tir.total == 4
        assert result.alerts  # 60 mg/dL dispara alerta de hipoglicemia
        assert result.daily
        assert result.histogram

    def test_tir_target(self):
        dataset = Dataset(readings=make_readings([100] * 10))
        result = analyze(dataset)
        assert result.tir_meets_target is True
        assert result.alerts == []

    def test_empty_dataset(self):
        result = analyze(Dataset())
        assert result.descriptive.n == 0
        assert result.tir.total == 0
        assert result.tir_meets_target is False


class TestDatasetIO:
    def test_load_dataset(self, tmp_path):
        payload = (
            '{"device": {"model": "2102"}, "read_at": "2023-05-01T10:00:00", '
            '"count": 2, "records": ['
            '{"timestamp": "2023-05-01T08:00:00", "mg/dL": 100},'
            '{"timestamp": "2023-05-02T08:00:00", "mg/dL": 130, '
            '"out_of_range": "high"}]}'
        )
        path = tmp_path / "data.json"
        path.write_text(payload, encoding="utf-8")

        dataset = load_dataset(path)
        assert dataset.n == 2
        assert dataset.device["model"] == "2102"
        assert dataset.readings[0].value_mgdl == 100
        assert dataset.readings[1].out_of_range == "high"
        assert dataset.period[0] < dataset.period[1]

    def test_reading_from_dict_with_epoch(self, tmp_path):
        payload = '{"records": [{"epoch": 1672531200, "mg/dL": 99}], "count": 1}'
        path = tmp_path / "epoch.json"
        path.write_text(payload, encoding="utf-8")

        dataset = load_dataset(path)
        assert dataset.n == 1
        assert dataset.readings[0].value_mgdl == 99
        assert dataset.readings[0].timestamp == datetime.fromtimestamp(1672531200)

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_dataset(tmp_path / "nao-existe.json")

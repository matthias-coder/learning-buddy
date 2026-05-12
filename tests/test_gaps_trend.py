from school_test_engine.grading.gaps import (
    TREND_ARROW,
    TopicStat,
    _trend_from_history,
    apply_trend,
)


class TestTrendFromHistory:
    def test_no_history(self):
        assert _trend_from_history([]) == "none"

    def test_single_attempt(self):
        assert _trend_from_history([75.0]) == "none"

    def test_clearly_up(self):
        assert _trend_from_history([50.0, 70.0]) == "up"

    def test_clearly_down(self):
        assert _trend_from_history([90.0, 60.0]) == "down"

    def test_flat_when_change_small(self):
        assert _trend_from_history([70.0, 72.0]) == "flat"
        assert _trend_from_history([70.0, 65.5]) == "flat"

    def test_uses_last_two_only(self):
        # Trend looks at the latest delta, not overall direction
        assert _trend_from_history([50.0, 80.0, 60.0]) == "down"


class TestApplyTrend:
    def test_attaches_history_and_trend(self):
        stats = [TopicStat("A", 6, 10, 60.0, 2)]
        rows = [
            {"topic": "A", "earned": 4, "possible": 10},
            {"topic": "A", "earned": 8, "possible": 10},
        ]
        out = apply_trend(stats, rows)
        assert out[0].history == [40.0, 80.0]
        assert out[0].trend == "up"

    def test_ignores_unknown_topics(self):
        stats = [TopicStat("A", 5, 10, 50.0, 1)]
        rows = [{"topic": "B", "earned": 5, "possible": 10}]
        out = apply_trend(stats, rows)
        assert out[0].trend == "none"
        assert out[0].history == []


class TestTrendArrow:
    def test_all_directions(self):
        assert TREND_ARROW["up"] == "↑"
        assert TREND_ARROW["down"] == "↓"
        assert TREND_ARROW["flat"] == "→"
        assert TREND_ARROW["none"] == ""

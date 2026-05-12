from school_test_engine.grading.scoring import score_multi, score_short, score_single


class TestSingleChoice:
    def test_correct(self):
        r = score_single(correct_ids=["b"], response=["b"], points=2)
        assert r.points_earned == 2.0
        assert r.is_correct is True

    def test_wrong(self):
        r = score_single(correct_ids=["b"], response=["a"], points=2)
        assert r.points_earned == 0.0
        assert r.is_correct is False

    def test_empty_response(self):
        r = score_single(correct_ids=["b"], response=[], points=2)
        assert r.points_earned == 0.0
        assert r.is_correct is False

    def test_multiple_response_treated_as_wrong(self):
        r = score_single(correct_ids=["b"], response=["a", "b"], points=2)
        assert r.points_earned == 0.0
        assert r.is_correct is False


class TestMultiChoicePartial:
    def test_all_correct(self):
        r = score_multi(correct_ids=["a", "b", "d"], response=["a", "b", "d"], points=3)
        assert r.points_earned == 3.0
        assert r.is_correct is True

    def test_two_correct_one_wrong(self):
        # 2 correct - 1 wrong = 1, / 3 total = 1/3, * 4 points = 1.33
        r = score_multi(correct_ids=["a", "b", "d"], response=["a", "b", "c"], points=4)
        assert r.points_earned == round(4 * (1 / 3), 2)
        assert r.is_correct is False

    def test_all_wrong(self):
        r = score_multi(correct_ids=["a", "b"], response=["c", "d"], points=4)
        assert r.points_earned == 0.0
        assert r.is_correct is False

    def test_more_wrong_than_right_clamped_to_zero(self):
        r = score_multi(correct_ids=["a", "b"], response=["b", "c", "d"], points=4)
        # 1 correct - 2 wrong = -1 → clamped to 0
        assert r.points_earned == 0.0

    def test_empty_response(self):
        r = score_multi(correct_ids=["a", "b"], response=[], points=4)
        assert r.points_earned == 0.0


class TestMultiChoiceAllOrNothing:
    def test_full(self):
        r = score_multi(
            correct_ids=["a", "b"], response=["a", "b"], points=3, scoring="all_or_nothing"
        )
        assert r.points_earned == 3.0
        assert r.is_correct is True

    def test_partial_gives_zero(self):
        r = score_multi(
            correct_ids=["a", "b"], response=["a"], points=3, scoring="all_or_nothing"
        )
        assert r.points_earned == 0.0
        assert r.is_correct is False


class TestShortAnswer:
    def test_exact_match(self):
        r = score_short(accepted_answers=["wrote"], response="wrote", points=1)
        assert r.points_earned == 1.0
        assert r.is_correct is True

    def test_case_insensitive_by_default(self):
        r = score_short(accepted_answers=["wrote"], response="Wrote", points=1)
        assert r.is_correct is True

    def test_case_sensitive_mode(self):
        r = score_short(
            accepted_answers=["Berlin"], response="berlin", points=1, case_sensitive=True
        )
        assert r.is_correct is False

    def test_trim_whitespace(self):
        r = score_short(accepted_answers=["19"], response="  19  ", points=1)
        assert r.is_correct is True

    def test_no_trim_whitespace(self):
        r = score_short(
            accepted_answers=["19"], response="  19  ", points=1, trim_whitespace=False
        )
        assert r.is_correct is False

    def test_multiple_accepted_variants(self):
        r = score_short(
            accepted_answers=["19", "x=19", "x = 19"], response="x = 19", points=1
        )
        assert r.is_correct is True

    def test_umlauts_not_normalized(self):
        # "Schueler" should NOT match "Schüler" — umlauts matter
        r = score_short(accepted_answers=["Schüler"], response="Schueler", points=1)
        assert r.is_correct is False

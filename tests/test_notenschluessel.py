from school_test_engine.grading.notenschluessel import DEFAULT_REALSCHULE, percent_to_note


class TestDefaultNotenschluessel:
    def test_perfect_score(self):
        assert percent_to_note(100.0) == 1

    def test_just_above_one_cutoff(self):
        assert percent_to_note(92.0) == 1

    def test_just_below_one_cutoff(self):
        assert percent_to_note(91.9) == 2

    def test_zero(self):
        assert percent_to_note(0.0) == 6

    def test_below_lowest_cutoff(self):
        assert percent_to_note(10.0) == 6

    def test_each_boundary(self):
        for note, cutoff in DEFAULT_REALSCHULE.items():
            assert percent_to_note(float(cutoff)) == note

    def test_just_below_each_boundary(self):
        # Just below note N's cutoff should give note N+1 (except for note 6 which is the floor)
        for note in (1, 2, 3, 4, 5):
            cutoff = DEFAULT_REALSCHULE[note]
            assert percent_to_note(cutoff - 0.1) == note + 1


class TestCustomNotenschluessel:
    def test_custom_table(self):
        # Stricter schluessel (z.B. Gymnasium-Stil)
        strict = {1: 96, 2: 85, 3: 70, 4: 55, 5: 30, 6: 0}
        assert percent_to_note(95.0, strict) == 2
        assert percent_to_note(96.0, strict) == 1

from school_test_engine.util.shuffle import shuffled


class TestShuffle:
    def test_deterministic_same_seed(self):
        items = list(range(10))
        a = shuffled(items, seed=42)
        b = shuffled(items, seed=42)
        assert a == b

    def test_different_seeds_differ(self):
        items = list(range(20))
        a = shuffled(items, seed=1)
        b = shuffled(items, seed=2)
        assert a != b

    def test_input_not_mutated(self):
        items = list(range(5))
        shuffled(items, seed=1)
        assert items == [0, 1, 2, 3, 4]

    def test_same_seed_different_salt_differs(self):
        items = list(range(20))
        a = shuffled(items, seed=42, salt="questions")
        b = shuffled(items, seed=42, salt="choices:q1")
        assert a != b

    def test_preserves_elements(self):
        items = list(range(20))
        result = shuffled(items, seed=99)
        assert sorted(result) == items

    def test_empty_list(self):
        assert shuffled([], seed=42) == []

    def test_single_element(self):
        assert shuffled([7], seed=42) == [7]

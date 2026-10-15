from app.tools.scoring import match_amounts


def test_counts_each_correct_amount_once():
    assert match_amounts([610_000, 610_000, 20_000], [610_000, 20_000]) == 2


def test_order_does_not_matter_and_unreadable_values_are_ignored():
    assert match_amounts([None, 20_000, 2_100_000], [2_100_000, 20_000, 75_000]) == 2


def test_allows_one_percent_tolerance():
    assert match_amounts([1_205_000], [1_200_000]) == 1
    assert match_amounts([1_700_000], [1_200_000]) == 0

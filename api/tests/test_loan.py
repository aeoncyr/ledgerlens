"""Loan arithmetic: the instalment and the schedule are whole rupiah and always add up."""

import pytest

from app.loan import instalment, make_offer, round_rp, schedule
from app.tools.policy import monthly_installment


def test_a_level_instalment_repays_the_loan_with_interest():
    # 15 million over 12 months at 6% a year: 0.5% a month, the KUR micro rate the policy uses.
    assert instalment(15_000_000, 12, 6) == 1_290_996
    assert instalment(15_000_000, 12, 6) == monthly_installment(15_000_000, 12, 0.005)


def test_without_interest_the_amount_is_split_evenly():
    rows = schedule(10_000_000, 12, 0)

    assert instalment(10_000_000, 12, 0) == 833_333
    assert {r.interest_rp for r in rows} == {0}
    assert rows[-1].principal_rp == 10_000_000 - 11 * 833_333  # the last month takes the rounding
    assert sum(r.principal_rp for r in rows) == 10_000_000


@pytest.mark.parametrize(
    ("amount", "months", "rate"),
    [(15_000_000, 12, 6), (5_000_000, 6, 24), (50_000_000, 60, 13.5), (1_000_000, 1, 18)],
)
def test_the_schedule_always_adds_up(amount, months, rate):
    rows = schedule(amount, months, rate)
    payment = instalment(amount, months, rate)

    assert [r.month for r in rows] == list(range(1, months + 1))
    assert sum(r.principal_rp for r in rows) == amount
    assert rows[-1].balance_rp == 0
    assert all(r.instalment_rp == r.principal_rp + r.interest_rp for r in rows)
    assert all(r.instalment_rp == payment for r in rows[:-1])
    assert abs(rows[-1].instalment_rp - payment) <= months  # rounding drift stays tiny
    assert all(isinstance(r.balance_rp, int) for r in rows)


def test_interest_falls_as_the_balance_is_repaid():
    rows = schedule(15_000_000, 12, 6)

    assert rows[0].interest_rp == 75_000
    assert all(a.interest_rp > b.interest_rp for a, b in zip(rows, rows[1:], strict=False))


def test_an_offer_is_within_policy_only_below_the_policy_limit():
    assert make_offer(15_000_000, 12, 6, max_installment=1_300_000).within_policy
    assert not make_offer(15_000_000, 12, 6, max_installment=1_000_000).within_policy
    # With too little evidence the policy sets no limit, so nothing is "within" it.
    assert not make_offer(15_000_000, 12, 6, max_installment=None).within_policy


def test_an_offer_totals_every_instalment():
    offer = make_offer(15_000_000, 12, 6, max_installment=None)

    assert offer.total_rp == sum(r.instalment_rp for r in offer.schedule)
    assert offer.total_rp > offer.amount_rp
    dumped = offer.model_dump(by_alias=True)
    assert {"amountRp", "tenorMonths", "annualRatePct", "instalmentRp", "totalRp"} <= set(dumped)
    assert set(dumped["schedule"][0]) == {
        "month",
        "instalmentRp",
        "interestRp",
        "principalRp",
        "balanceRp",
    }


def test_rounding_matches_the_web_preview():
    # JavaScript's Math.round rounds halves up; Python's round() would round 2.5 to 2.
    assert (round_rp(2.5), round_rp(3.5), round_rp(2.4999)) == (3, 4, 2)

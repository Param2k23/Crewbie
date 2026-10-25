import pytest

from crewbie.domain.budget import BudgetBand, bands_compatible, most_constrained


def test_fr_mat_02_low_and_high_are_incompatible_adjacent_bands_are_fine() -> None:
    assert not bands_compatible(BudgetBand.LOW, BudgetBand.HIGH)
    assert not bands_compatible(BudgetBand.HIGH, BudgetBand.LOW)
    assert bands_compatible(BudgetBand.LOW, BudgetBand.MID)
    assert bands_compatible(BudgetBand.HIGH, BudgetBand.HIGH)


def test_most_constrained_is_lowest_band() -> None:
    assert most_constrained([BudgetBand.HIGH, BudgetBand.LOW, BudgetBand.MID]) is BudgetBand.LOW
    assert most_constrained([]) is None


def test_parse_and_label() -> None:
    assert BudgetBand.parse("mid") is BudgetBand.MID
    assert BudgetBand.HIGH.label == "high"
    with pytest.raises(ValueError):
        BudgetBand.parse("luxury")

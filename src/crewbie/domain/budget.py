"""Budget bands and their ordering (low < mid < high)."""

from collections.abc import Iterable
from enum import IntEnum


class BudgetBand(IntEnum):
    LOW = 0
    MID = 1
    HIGH = 2

    @classmethod
    def parse(cls, value: str) -> "BudgetBand":
        try:
            return cls[value.upper()]
        except KeyError:
            raise ValueError(f"unknown budget band: {value!r}") from None

    @property
    def label(self) -> str:
        return self.name.lower()


def bands_compatible(a: BudgetBand, b: BudgetBand) -> bool:
    """FR-MAT-02: bands more than one step apart must not share a room."""
    return abs(a - b) <= 1


def most_constrained(bands: Iterable[BudgetBand]) -> BudgetBand | None:
    return min(bands, default=None)

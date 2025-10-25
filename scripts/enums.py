"""Enumerations for the immunization pipeline."""

from enum import Enum


class BatchStrategy(Enum):
    """Batch grouping strategy."""

    SIZE = "size"
    SCHOOL = "school"
    BOARD = "board"

    @classmethod
    def from_string(cls, value: str | None) -> "BatchStrategy | None":
        """Convert string to BatchStrategy. Defaults to SIZE if None."""
        if value is None:
            return cls.SIZE

        value_lower = value.lower()
        for strategy in cls:
            if strategy.value == value_lower:
                return strategy

        raise ValueError(
            f"Unknown batch strategy: {value}. "
            f"Valid options: {', '.join(s.value for s in cls)}"
        )


class BatchType(Enum):
    """Type descriptor for batch operation."""

    SIZE_BASED = "size_based"
    SCHOOL_GROUPED = "school_grouped"
    BOARD_GROUPED = "board_grouped"

    @classmethod
    def from_strategy(cls, strategy: "BatchStrategy") -> "BatchType":
        """Convert BatchStrategy to corresponding BatchType."""
        mapping = {
            BatchStrategy.SIZE: cls.SIZE_BASED,
            BatchStrategy.SCHOOL: cls.SCHOOL_GROUPED,
            BatchStrategy.BOARD: cls.BOARD_GROUPED,
        }
        return mapping[strategy]

"""Enumerations for the immunization pipeline."""

from enum import Enum


class BatchStrategy(Enum):
    """Batch grouping strategy."""

    SIZE = "size"
    SCHOOL = "school"
    BOARD = "board"

    @classmethod
    def from_string(cls, value: str | None) -> "BatchStrategy":
        """Convert string to BatchStrategy.

        Parameters
        ----------
        value : str | None
            Batch strategy name ('size', 'school', 'board'), or None for default.

        Returns
        -------
        BatchStrategy
            Corresponding BatchStrategy enum, defaults to SIZE if value is None.

        Raises
        ------
        ValueError
            If value is not a valid strategy name.
        """
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
        """Convert BatchStrategy to corresponding BatchType.

        Maps the grouping strategy to the batch type descriptor used in batch
        manifest records and filenames.

        Parameters
        ----------
        strategy : BatchStrategy
            Batch strategy enum value.

        Returns
        -------
        BatchType
            Corresponding batch type descriptor.
        """
        mapping = {
            BatchStrategy.SIZE: cls.SIZE_BASED,
            BatchStrategy.SCHOOL: cls.SCHOOL_GROUPED,
            BatchStrategy.BOARD: cls.BOARD_GROUPED,
        }
        return mapping[strategy]

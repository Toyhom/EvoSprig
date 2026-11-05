"""Optional selection-set stopping criteria, independent of release validation."""

from pydantic import Field

from evosprig.core.spec import Contract


class EvolutionGoal(Contract):
    score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    patience: int | None = Field(default=None, ge=1, le=100)
    min_delta: float = Field(default=0.001, ge=0, le=1, allow_inf_nan=False)


class GoalReached(Exception):
    """Leave search, then run the normal paired release/test checks."""

    def __init__(self, reason, selected, score):
        self.reason, self.selected, self.score = reason, selected, score
        super().__init__(reason)

"""Release validation is independent from an optimizer's search-time selection."""

from pydantic import Field

from evosprig.core.spec import Contract


class ReleaseGate(Contract):
    min_gain: float = Field(default=0.0, ge=0, le=1)
    max_regression: float = Field(default=0.0, ge=0, le=1)
    min_samples: int = Field(default=2, ge=1)
    max_mean_tokens: int = Field(default=8192, ge=1)
    require_all_succeeded: bool = True

    def assess(self, baseline, candidate):
        reasons = []
        if (
            baseline["suite_id"] != candidate["suite_id"]
            or baseline["split"] != "release"
            or candidate["split"] != "release"
        ):
            raise ValueError("gate requires paired reports on the same release-validation split")
        if [sample["sample_id"] for sample in baseline["samples"]] != [
            sample["sample_id"] for sample in candidate["samples"]
        ]:
            raise ValueError("gate requires the same ordered samples")
        count = candidate["count"]
        if count < self.min_samples:
            reasons.append("insufficient release-validation samples")
        gain = candidate["score"] - baseline["score"] if count else None
        if gain is None or gain < self.min_gain:
            reasons.append("quality gain below threshold")
        for tag, score in baseline["tags"].items():
            if candidate["tags"].get(tag, 0) < score - self.max_regression:
                reasons.append("regression in task group: " + tag)
        if (
            count
            and (candidate["input_tokens"] + candidate["output_tokens"]) / count
            > self.max_mean_tokens
        ):
            reasons.append("mean inference token use exceeds limit")
        if self.require_all_succeeded and any(
            sample["run"]["status"] != "succeeded" for sample in candidate["samples"]
        ):
            reasons.append("candidate has failed validation runs")
        return {
            "passed": not reasons,
            "gain": gain,
            "reasons": reasons,
            "config": self.model_dump(),
            "baseline_report": baseline["report_id"],
            "candidate_report": candidate["report_id"],
            "sample_count": count,
            "automatic_release": False,
        }

"""Application-facing comparisons without internal traces or optimizer conversations."""

import json


def comparison_record(baseline, selected, *, method, task_model, judge_model=None):
    if baseline["suite_id"] != selected["suite_id"] or baseline["split"] != selected["split"]:
        raise ValueError("comparison requires the same frozen evaluation split")
    if [s["sample_id"] for s in baseline["samples"]] != [
        s["sample_id"] for s in selected["samples"]
    ]:
        raise ValueError("comparison needs paired ordered inputs")
    cases = []
    for before, after in zip(baseline["samples"], selected["samples"]):
        cases.append(
            {
                "input": before["input"],
                "baseline": {
                    "output": before["run"]["output"],
                    "score": before["score"],
                    "status": before["run"]["status"],
                },
                "evolved": {
                    "output": after["run"]["output"],
                    "score": after["score"],
                    "status": after["run"]["status"],
                },
            }
        )
    return {
        "method": method,
        "task_model": task_model,
        "judge_model": judge_model,
        "sample_count": len(cases),
        "split": baseline["split"],
        "baseline_version": baseline["version_id"],
        "evolved_version": selected["version_id"],
        "candidate_changed": baseline["version_id"] != selected["version_id"],
        "baseline_score": baseline["score"],
        "evolved_score": selected["score"],
        "gain": (
            selected["score"] - baseline["score"]
            if baseline["version_id"] != selected["version_id"]
            else 0.0
        )
        if cases
        else None,
        "validation_reused": baseline.get("report_id") == selected.get("report_id"),
        "cases": cases,
    }


def markdown_comparison(record):
    def formatted(value):
        return (
            str(value)
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, indent=2)
        )

    lines = [
        "# Before and after",
        "",
        f"{record['method']} · {record['task_model']} · {record['sample_count']} paired {record['split']} tasks",
        "",
        "| | Baseline | Evolved |",
        "| --- | ---: | ---: |",
        f"| Task score | {record['baseline_score']:.3f} | {record['evolved_score']:.3f} |",
        "",
    ]
    if record.get("judge_model"):
        lines += [
            f"Scored by {record['judge_model']} against the same fixed rubric. These are example-run results, not a guarantee of improvement on other tasks.",
            "",
        ]
    if record.get("candidate_changed") is False:
        lines += [
            (
                "The search retained the baseline version. Its validation result is reused in both columns; no evolution gain is claimed."
                if record.get("validation_reused")
                else "The search retained the baseline version. These are reruns of the same version; a score difference is run variability, not evolution gain."
            ),
            "",
        ]
    for i, case in enumerate(record["cases"], 1):
        lines += [f"## Task {i}", "", "```json", formatted(case["input"]), "```", ""]
        for key, title in [("baseline", "Baseline"), ("evolved", "Evolved")]:
            lines += [f"### {title}", "", "````text", formatted(case[key]["output"]), "````", ""]
    return "\n".join(lines)

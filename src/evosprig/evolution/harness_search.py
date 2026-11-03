"""Archive, attributed-edit, cost-aware and modular harness searches.

Mechanisms follow AHE (2604.25850), Meta-Harness (2603.28052), RRSI
(2609.24972), ADAS (2408.08435) and ModularRSI (2609.14857).
"""

import math
import statistics

from evosprig.core.protocols import BudgetExceeded

from .harness_common import (
    HarnessOptions,
    HarnessSearch,
    ask,
    changed,
    measure,
    pareto,
    public_measure,
    review,
)
from .space import replace_targets, targets


async def manifest(context, parent, candidate, task_ids, *, budget=32):
    edits = changed(parent, candidate)
    response = await ask(
        context,
        "Describe independent mechanisms in this actual diff. Return an array of {id,hypothesis,targets,predicted_fixes,at_risk}. Targets must cover every changed target exactly once. Predicted fixes and at-risk lists contain search task IDs. Group a mechanism and its wiring together.",
        {"diff": edits, "task_ids": task_ids, "mechanism_budget": budget},
    )
    if not isinstance(response, list) or not 0 < len(response) <= budget:
        raise ValueError("invalid mechanism manifest")
    seen, identifiers = [], set()
    for item in response:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "hypothesis",
            "targets",
            "predicted_fixes",
            "at_risk",
        }:
            raise ValueError("invalid mechanism entry")
        if (
            any(
                not isinstance(item[k], str) or not item[k].strip() or len(item[k]) > 4000
                for k in ("id", "hypothesis")
            )
            or item["id"] in identifiers
        ):
            raise ValueError("mechanisms need unique IDs and a hypothesis")
        identifiers.add(item["id"])
        for key in ("targets", "predicted_fixes", "at_risk"):
            if not isinstance(item[key], list) or any(not isinstance(v, str) for v in item[key]):
                raise ValueError("manifest references must be string lists")
        if not item["targets"] or set(item["predicted_fixes"] + item["at_risk"]) - set(task_ids):
            raise ValueError("manifest task reference is outside the search split")
        seen.extend(item["targets"])
    if set(seen) != set(edits) or len(seen) != len(set(seen)):
        raise ValueError("manifest must cover every edit exactly once")
    return response


def attribute(entries, parent, candidate):
    delta = {task: candidate[task] - score for task, score in parent.items()}
    return [
        {
            **entry,
            "fixed": [t for t in entry["predicted_fixes"] if delta[t] > 1e-12],
            "regressed": [t for t, gain in delta.items() if gain < -1e-12],
            "keep": (
                not entry["predicted_fixes"]
                or any(delta[t] > 1e-12 for t in entry["predicted_fixes"])
            )
            and not any(
                gain < -1e-12 and task not in entry["at_risk"] for task, gain in delta.items()
            ),
        }
        for entry in entries
    ]


async def ahe(context, *, config):
    run, verdicts, current = HarnessSearch(context, "ahe"), [], None
    try:
        current = await run.evaluate(context.seed)
        for step in range(config.rounds):
            try:
                diagnosis = await ask(
                    context,
                    'Diagnose reusable harness failure causes from task trajectories. Return {"tasks":[{"task_id":string,"cause":string}],"summary":string}.',
                    {"feedback": run.feedback(current), "previous_verdicts": verdicts[-3:]},
                )
                proposal = await run.propose(
                    current,
                    "Implement a small set of diagnosed harness mechanisms.",
                    diagnosis=diagnosis,
                )
                declarations = await manifest(
                    context,
                    current["resources"],
                    proposal,
                    [s["id"] for s in context.view["search"]],
                )
                if not await review(context, current["resources"], proposal):
                    continue
                item = await run.evaluate(
                    proposal, parents=[current["version_id"]], operator="diagnosed_edit"
                )

                def outcomes(row):
                    return {s["sample_id"]: s["score"] for s in run.feedback(row)["trajectories"]}

                verdict = attribute(declarations, outcomes(current), outcomes(item))
                rollback = {
                    t: targets(current["resources"])[t]
                    for v in verdict
                    if not v["keep"]
                    for t in v["targets"]
                }
                if rollback:
                    repaired = replace_targets(proposal, rollback)
                    item = await run.evaluate(
                        repaired, parents=[item["version_id"]], operator="attributed_rollback"
                    )
                verdicts.append({"version_id": item["version_id"], "verdicts": verdict})
                current = item
                run.select(current)
                run.checkpoint(step, diagnosis=diagnosis, verdicts=verdicts)
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    if current:
        run.select(current)
    return run.result(verdicts=verdicts)


async def adas(context, *, config):
    run, designs = HarnessSearch(context, "adas"), []
    try:
        best = await run.evaluate(context.seed)
        for step in range(config.rounds):
            try:
                design = await ask(
                    context,
                    'Invent a new agent design using the archive. Explain how it differs, then critique feasibility and refine the design. Return {"name":string,"design":string,"critique":string,"revision":string}.',
                    {
                        "archive": designs,
                        "best": run.feedback(best),
                        "targets": list(targets(context.seed)),
                    },
                )
                if not isinstance(design, dict) or any(
                    not isinstance(design.get(k), str)
                    for k in ("name", "design", "critique", "revision")
                ):
                    raise ValueError("invalid design description")
                proposal = await run.propose(
                    best,
                    "Implement the refined agent design as an executable application candidate.",
                    design=design,
                )
                if not await review(context, best["resources"], proposal):
                    continue
                item = await run.evaluate(
                    proposal, parents=[best["version_id"]], operator="archive_design"
                )
                designs.append(
                    {
                        **design,
                        "version_id": item["version_id"],
                        "score": item["selection_score"],
                        "candidate": proposal,
                    }
                )
                if item["selection_score"] > best["selection_score"]:
                    best = item
                run.checkpoint(step, designs=designs)
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(designs=designs)


async def meta_harness(context, *, config):
    run = HarnessSearch(context, "meta_harness")
    try:
        seed = await run.evaluate(context.seed)
        for step in range(config.rounds):
            try:
                archive = [
                    {
                        "candidate": item["resources"],
                        "version_id": item["version_id"],
                        "score": item["search_score"],
                        "tokens": run.search_cost(item),
                        "traces": run.feedback(item)["trajectories"],
                    }
                    for item in run.history
                ]
                proposal = await run.propose(
                    seed,
                    "Start from the seed or reuse any archived implementation. Diagnose historical traces, combine successful mechanisms and improve the quality/token tradeoff.",
                    archive=archive,
                    frontier=[p["version_id"] for p in pareto(run.history, run)],
                )
                await run.evaluate(
                    proposal,
                    parents=[item["version_id"] for item in run.history],
                    operator="history_synthesis",
                )
                run.checkpoint(step, frontier=[p["version_id"] for p in pareto(run.history, run)])
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(frontier=[p["version_id"] for p in pareto(run.history, run)])


def rrsi_admit(candidate, parent, best_score, options, delta, novelty):
    if parent["cost"] <= 0 or candidate["cost"] <= 0:
        return False
    ds = candidate["score"] - parent["score"]
    dc = (candidate["cost"] - parent["cost"]) / parent["cost"]
    if candidate["score"] < best_score - delta:
        return False
    if ds > delta:
        return dc <= options.beta0 + options.beta1 * ds
    return (
        options.score_weight * ds - options.cost_weight * dc + options.novelty_weight * novelty > 0
    )


async def rrsi(context, *, config):
    options = HarnessOptions.model_validate(config.options)
    if options.min_edits > options.max_edits or (options.delta is None and options.repetitions < 2):
        raise ValueError(
            "RRSI needs ordered edit bounds and repeated calibration or an explicit delta"
        )
    run, ledger, won, current = HarnessSearch(context, "rrsi"), [], set(), context.seed
    current_score = None
    try:
        measured = await measure(context, current, repetitions=options.repetitions)
        if measured["cost"] <= 0:
            raise ValueError("RRSI requires reported positive task token cost")
        delta = options.delta
        if delta is None:
            delta = math.sqrt(2) * statistics.stdev(r["score"] for r in measured["reports"])
        best_score = measured["score"]
        for step in range(config.rounds):
            choices = []
            edit_budget = math.ceil(
                options.min_edits
                + (options.max_edits - options.min_edits)
                * (1 + math.cos(math.pi * step / config.rounds))
                / 2
            )
            diagnosis = await ask(
                context,
                'Compare low-scoring failures and high-scoring successes. Return {"failure_modes":[],"success_habits":[],"prune":[],"explore":[]}; use reusable mechanisms and use edit history to avoid repeating ineffective additions.',
                {"trials": measured["reports"], "history": ledger[-10:]},
            )
            for attempt in range(options.proposals):
                try:
                    candidate = await context.json_proposal(
                        {
                            "current": current,
                            "diagnosis": diagnosis,
                            "history": ledger[-10:],
                            "mechanism_budget": edit_budget,
                            "instruction": "Propose a regularized revision. Prefer small general mechanisms; remove stale mechanisms and explore untried components.",
                        }
                    )
                    entries = await manifest(
                        context, current, candidate, list(measured["per_task"]), budget=edit_budget
                    )
                    if not await review(context, current, candidate):
                        continue
                    scored = await measure(context, candidate, repetitions=options.repetitions)
                    touched = set(changed(current, candidate))
                    novelty = len(touched - won) / max(1, len(touched))
                    admitted = rrsi_admit(scored, measured, best_score, options, delta, novelty)
                    record = {
                        "step": step,
                        "attempt": attempt,
                        "candidate": candidate,
                        "measurement": public_measure(scored),
                        "manifest": entries,
                        "attribution": attribute(entries, measured["per_task"], scored["per_task"]),
                        "admissible": admitted,
                        "accepted": False,
                        "diff": changed(current, candidate),
                    }
                    ledger.append(record)
                    if admitted:
                        choices.append((candidate, scored, record, touched))
                except (ValueError, TypeError, KeyError) as exc:
                    run.reject(step, exc)
            if choices:
                current, measured, winner, touched = max(
                    choices, key=lambda choice: choice[1]["score"]
                )
                winner["accepted"] = True
                best_score = max(best_score, measured["score"])
                won.update(touched)
            run.best = current
            run.checkpoint(step, delta=delta, edit_budget=edit_budget, ledger=ledger)
        selection = await context.evaluate(current, "selection")
        current_score = selection["score"]
    except BudgetExceeded:
        run.status = "budget_exhausted"
    run.best, run.best_score = current, current_score if current_score is not None else -1.0
    return run.result(ledger=ledger, winning_targets=sorted(won))


async def modular_rsi(context, *, config):
    options = HarnessOptions.model_validate(config.options)
    if not context.search_space or not context.search_space.modules:
        raise ValueError("ModularRSI requires explicit module ownership in search_space.modules")
    if options.repetitions < 2:
        raise ValueError("ModularRSI contrastive diagnosis requires at least two trials")
    run, branches, combined = HarnessSearch(context, "modular_rsi"), {}, context.seed
    try:
        for module, owned in context.search_space.modules.items():
            current, history = context.seed, []
            for step in range(config.rounds):
                try:
                    trials = await measure(context, current, repetitions=options.repetitions)
                    grouped = {
                        task: [
                            next(s for s in r["samples"] if s["sample_id"] == task)
                            for r in trials["reports"]
                        ]
                        for task in trials["per_task"]
                    }
                    diagnosis = await ask(
                        context,
                        'Contrast successful and failed runs of each same task, identify recurring causes in this module, and return {"findings":[],"changes":[]}.',
                        {
                            "module": module,
                            "owned_targets": owned,
                            "trials_by_task": grouped,
                            "history": history,
                        },
                    )
                    proposal = await context.json_proposal(
                        {
                            "current": current,
                            "diagnosis": diagnosis,
                            "owned_targets": owned,
                            "instruction": "Change only this module's targets. Preserve all other values exactly.",
                        }
                    )
                    if not await review(context, current, proposal, module=owned):
                        continue
                    check = await measure(context, proposal)
                    if check["finished"]:
                        history.append(
                            {
                                "diff": changed(current, proposal),
                                "measurement": public_measure(check),
                            }
                        )
                        current = proposal
                    run.checkpoint(step, module=module, branch=current, branch_history=history)
                except (ValueError, TypeError, KeyError) as exc:
                    run.reject(step, exc)
            branches[module] = {"candidate": current, "history": history}
        # Disjoint target ownership makes integration deterministic. Interactions
        # are then exercised by the complete application and refined jointly.
        for module, branch in branches.items():
            owned = context.search_space.modules[module]
            combined = replace_targets(
                combined, {t: targets(branch["candidate"])[t] for t in owned}
            )
        context.version(combined)
        initial = await measure(context, combined)
        fallback = combined if initial["finished"] else context.seed
        for step in range(options.integration_rounds):
            try:
                proposal = await context.json_proposal(
                    {
                        "current": combined,
                        "branches": branches,
                        "trials": initial["reports"],
                        "instruction": "Resolve cross-module interactions and remove redundant mechanisms while preserving each module's useful behavior.",
                    }
                )
                if proposal == combined:
                    continue
                if await review(
                    context,
                    combined,
                    proposal,
                    module=[t for ts in context.search_space.modules.values() for t in ts],
                ):
                    checked = await measure(context, proposal)
                    if checked["finished"]:
                        combined, initial = proposal, checked
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
        final = await measure(context, combined)
        combined = combined if final["finished"] else fallback
        run.best = combined
    except BudgetExceeded:
        run.status = "budget_exhausted"
        # Independent partial branches have not passed joint validation.
        run.best = context.seed
    return run.result(branches=branches)

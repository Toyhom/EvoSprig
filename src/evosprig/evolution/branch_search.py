"""DarwinX preserve-and-extend populations and Arbor hypothesis trees.

Sources: arxiv.org/abs/2608.07545; github.com/RUC-NLPIR/Arbor.
"""

import random

from evosprig.core.protocols import BudgetExceeded

from .harness_common import HarnessOptions, HarnessSearch, ask, measure, public_measure


def preservation(candidate, parents, invariants, options, *, screen=False):
    scores, primary = candidate["per_task"], parents[0]["per_task"]
    delta = {task: score - primary[task] for task, score in scores.items()}
    regression = sum(
        max(max(parent["per_task"][task] for parent in parents) - value, 0)
        for task, value in scores.items()
    )
    lost = sorted(task for task in invariants if scores.get(task, 0) < options.solved_threshold)
    accepted = (
        (
            any(value > 1e-12 for value in delta.values())
            and regression <= options.screen_regression_tolerance + 1e-12
        )
        if screen
        else (
            sum(delta.values()) > 1e-12
            and regression <= options.regression_tolerance + 1e-12
            and not lost
        )
    )
    return {
        "accepted": accepted,
        "gain": sum(delta.values()),
        "regression_mass": regression,
        "lost_invariant": lost,
        "delta": delta,
    }


async def darwinx(context, *, config):
    options = HarnessOptions.model_validate(config.options)
    run, archive, lessons, attempted = HarnessSearch(context, "darwinx"), [], [], set()
    rng = random.Random(config.seed)
    try:
        measured = await measure(context, context.seed, repetitions=options.repetitions)
        seed = {
            "candidate": context.seed,
            "version_id": context.base.version_id,
            "measurement": public_measure(measured),
            "admitted": True,
            "confirmed": True,
            "invariants": sorted(
                t for t, s in measured["per_task"].items() if s >= options.solved_threshold
            ),
            "parents": [],
            "cumulative_gain": 0.0,
        }
        archive.append(seed)
        for step in range(config.rounds):
            try:
                eligible = [item for item in archive if item["admitted"]]
                parent = (
                    rng.choice(eligible)
                    if rng.random() < options.exploration_probability
                    else max(
                        eligible, key=lambda p: (p["cumulative_gain"], p["measurement"]["score"])
                    )
                )
                parents = [parent]
                if options.merge_every and (step + 1) % options.merge_every == 0:
                    pairs = []
                    for i, left in enumerate(archive):
                        for right in archive[i + 1 :]:
                            key = tuple(sorted([left["version_id"], right["version_id"]]))
                            if key in attempted or not left["confirmed"] or not right["confirmed"]:
                                continue
                            a, b = set(left["invariants"]), set(right["invariants"])
                            if a - b and b - a:
                                pairs.append(
                                    (
                                        len(a | b),
                                        min(
                                            left["measurement"]["score"],
                                            right["measurement"]["score"],
                                        ),
                                        left,
                                        right,
                                    )
                                )
                    if pairs:
                        pair = max(pairs, key=lambda p: p[:2])
                        parents = sorted(
                            pair[2:], key=lambda p: p["measurement"]["score"], reverse=True
                        )
                        parent = parents[0]
                        attempted.add(tuple(sorted(p["version_id"] for p in parents)))
                candidate = await context.json_proposal(
                    {
                        "current": parent["candidate"],
                        "parents": parents,
                        "archive": archive[-12:],
                        "lessons": lessons[-10:],
                        "instruction": "Recombine the complementary mechanisms of both parents."
                        if len(parents) == 2
                        else "Extend the parent's abilities while preserving every solved task.",
                    }
                )
                version = context.version(candidate)
                if any(row["version_id"] == version.version_id for row in archive):
                    continue
                tasks = rng.sample(
                    context.view["search"], min(options.screen_size, len(context.view["search"]))
                )
                fresh_parents = [
                    await measure(context, p["candidate"], samples=tasks) for p in parents
                ]
                screened = await measure(context, candidate, samples=tasks)
                invariants = set().union(*(set(p["invariants"]) for p in parents))
                verdict = preservation(screened, fresh_parents, invariants, options, screen=True)
                confirmed = verdict["accepted"]
                if confirmed:
                    fresh_parents = [
                        await measure(context, p["candidate"], repetitions=options.repetitions)
                        for p in parents
                    ]
                    screened = await measure(context, candidate, repetitions=options.repetitions)
                    verdict = preservation(screened, fresh_parents, invariants, options)
                solved = {
                    t
                    for t, score in screened["per_task"].items()
                    if score >= options.solved_threshold
                }
                entry = {
                    "candidate": candidate,
                    "version_id": version.version_id,
                    "measurement": public_measure(screened),
                    "admitted": confirmed and verdict["accepted"],
                    "confirmed": confirmed,
                    "invariants": sorted(invariants | solved)
                    if verdict["accepted"] and confirmed
                    else sorted(solved),
                    "parents": [p["version_id"] for p in parents],
                    "cumulative_gain": parent["cumulative_gain"] + verdict["gain"],
                    "verdict": verdict,
                }
                archive.append(entry)
                insight = await ask(
                    context,
                    'Summarize reusable lessons from this branch experiment. Return {"lesson":string}.',
                    {"experiment": entry, "trials": screened["reports"]},
                )
                if not isinstance(insight, dict) or not isinstance(insight.get("lesson"), str):
                    raise ValueError("invalid branch lesson")
                lessons.append(insight["lesson"][:8000])
                best = max(
                    (p for p in archive if p["admitted"]), key=lambda p: p["measurement"]["score"]
                )
                run.best = best["candidate"]
                run.checkpoint(step, archive=archive, lessons=lessons)
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    if archive:
        run.best = max(
            (p for p in archive if p["admitted"]), key=lambda p: p["measurement"]["score"]
        )["candidate"]
    return run.result(archive=archive, lessons=lessons)


def descendants(tree, root):
    children = [key for key, node in tree.items() if node["parent"] == root]
    return children + [child for key in children for child in descendants(tree, key)]


async def arbor(context, *, config):
    options = HarnessOptions.model_validate(config.options)
    run = HarnessSearch(context, "arbor")
    tree = {
        "ROOT": {
            "parent": None,
            "hypothesis": "Improve application task performance",
            "depth": 0,
            "status": "open",
            "insight": "",
        }
    }
    trunk = None
    try:
        trunk = await run.evaluate(context.seed)
        for cycle in range(config.rounds):
            selected, done = None, False
            for _ in range(options.coordinator_actions):
                try:
                    action = await ask(
                        context,
                        'Coordinate a hypothesis tree. Return {"action":"expand","node":id,"hypotheses":[string,...]} (1–3 children), {"action":"select","node":id}, {"action":"prune","node":id}, or {"action":"stop"}. Expand ROOT into directions, then directions into runnable experiments. Select only untested leaves at depth >=2. Use ancestor insights and prune weak directions.',
                        {
                            "tree": tree,
                            "trunk_version": trunk["version_id"],
                            "max_depth": options.max_depth,
                            "feedback": run.feedback(trunk),
                        },
                    )
                    if not isinstance(action, dict):
                        raise ValueError("tree action must be an object")
                    kind = action.get("action")
                    if kind == "stop":
                        done = True
                        break
                    key = action.get("node")
                    if key not in tree or tree[key]["status"] == "pruned":
                        raise ValueError("unknown or pruned hypothesis")
                    node = tree[key]
                    if kind == "expand":
                        hypotheses = action.get("hypotheses")
                        if (
                            node["depth"] >= options.max_depth
                            or not isinstance(hypotheses, list)
                            or not 1 <= len(hypotheses) <= 3
                        ):
                            raise ValueError("tree expansion exceeds bounds")
                        if any(
                            not isinstance(h, str) or not h.strip() or len(h) > 4000
                            for h in hypotheses
                        ):
                            raise ValueError("invalid hypothesis")
                        for hypothesis in hypotheses:
                            tree["H" + str(len(tree))] = {
                                "parent": key,
                                "hypothesis": hypothesis,
                                "depth": node["depth"] + 1,
                                "status": "open",
                                "insight": "",
                            }
                    elif kind == "prune" and key != "ROOT":
                        for child in [key, *descendants(tree, key)]:
                            tree[child]["status"] = "pruned"
                    elif (
                        kind == "select"
                        and node["depth"] >= 2
                        and node["status"] == "open"
                        and not descendants(tree, key)
                    ):
                        selected = key
                        break
                    else:
                        raise ValueError("invalid tree action")
                except (ValueError, TypeError, KeyError) as exc:
                    run.reject(cycle, exc)
            if done:
                break
            if selected is None:
                run.status = "coordinator_limit"
                break
            node = tree[selected]
            node["base_version"] = trunk["version_id"]
            try:
                candidate = await run.propose(
                    trunk,
                    "Implement this experiment from the current trunk.",
                    hypothesis=node,
                    insights=tree,
                )
                item = await run.evaluate(
                    candidate, parents=[trunk["version_id"]], operator="hypothesis_experiment"
                )
                accepted = (
                    item["search_score"] > trunk["search_score"]
                    and item["selection_score"] > trunk["selection_score"]
                )
                node.update(
                    status="done",
                    version_id=item["version_id"],
                    search_score=item["search_score"],
                    selection_score=item["selection_score"],
                    accepted=accepted,
                )
                if accepted:
                    trunk = item
                run.select(trunk)
                result = await ask(
                    context,
                    'Explain what this experiment teaches about its hypothesis. Return {"insight":string}.',
                    {"hypothesis": node, "traces": run.feedback(item)},
                )
                if not isinstance(result, dict) or not isinstance(result.get("insight"), str):
                    raise ValueError("invalid hypothesis insight")
                node["insight"] = result["insight"][:8000]
                parent = node["parent"]
                while parent is not None:
                    siblings = [n for n in tree.values() if n["parent"] == parent]
                    synthesis = await ask(
                        context,
                        'Synthesize child experiment insights into reusable guidance for their parent direction. Return {"insight":string}.',
                        {"parent": tree[parent], "children": siblings},
                    )
                    if not isinstance(synthesis, dict) or not isinstance(
                        synthesis.get("insight"), str
                    ):
                        raise ValueError("invalid ancestor insight")
                    tree[parent]["insight"] = synthesis["insight"][:8000]
                    parent = tree[parent]["parent"]
            except (ValueError, TypeError, KeyError) as exc:
                if node["status"] != "done":
                    node["status"] = "needs_retry"
                run.reject(cycle, exc)
            run.checkpoint(cycle, tree=tree, trunk_version=trunk["version_id"])
    except BudgetExceeded:
        run.status = "budget_exhausted"
    if trunk:
        run.select(trunk)
    return run.result(tree=tree)

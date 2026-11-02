"""Native text search methods operating on the shared evaluation contract.

EvoPrompt: Guo et al., https://arxiv.org/abs/2309.08532.
Self-Refine: Madaan et al., https://arxiv.org/abs/2303.17651.
ACE: Zhang et al., https://arxiv.org/abs/2510.04618.
These implementations search versioned EvoSprig resources with held-out selection.
"""

from __future__ import annotations

import json
import random

from evosprig.core.protocols import BudgetExceeded
from evosprig.core.spec import canonical_json, digest


class Search:
    def __init__(self, context, method):
        self.context, self.method = context, method
        self.history, self.errors, self.cache = [], [], {}
        self.best, self.best_score = context.seed, -1.0
        self.status = "completed"

    async def evaluate(self, texts, *, parents=(), operator="seed"):
        key = digest(texts)
        if key in self.cache:
            return self.cache[key]
        search = await self.context.evaluate(texts, "search")
        selection = await self.context.evaluate(texts, "selection")
        item = {
            "resources": texts,
            "search_score": search["score"],
            "selection_score": selection["score"],
            "version_id": search["version_id"],
            "search_report": search["report_id"],
            "selection_report": selection["report_id"],
            "parents": list(parents),
            "operator": operator,
        }
        self.cache[key] = item
        self.history.append(item)
        if item["selection_score"] > self.best_score:
            self.best, self.best_score = texts, item["selection_score"]
        return item

    def checkpoint(self, step, **state):
        self.context.emit(
            "method.checkpoint",
            method=self.method,
            step=step,
            selected=self.best,
            history=self.history,
            **state,
        )

    def reject(self, step, exc):
        error = {
            "step": step,
            "type": type(exc).__name__,
            "reason": "candidate failed resource or response validation",
        }
        self.errors.append(error)
        self.context.emit("candidate.rejected", **error)

    def result(self, **state):
        return {
            "method": self.method,
            "implementation": "native-" + self.method,
            "selected": self.best,
            "selected_score": self.best_score if self.best_score >= 0 else None,
            "history": self.history,
            "errors": self.errors,
            "status": self.status,
            "state": state,
        }

    def feedback(self, item):
        report = next(r for r in self.context.reports if r["report_id"] == item["search_report"])
        # Only search trajectories enter reflection; selection/release/test remain excluded.
        return {
            "resources": item["resources"],
            "score": item["search_score"],
            "examples": self.context.view["search"],
            "trajectories": report["samples"],
        }


async def evoprompt(context, *, variant="ga", rounds=3, population_size=4, seed=0):
    """GA uses tournament/crossover/mutation; DE uses three donors and target replacement."""
    if variant not in {"ga", "de"} or not 4 <= population_size <= 32:
        raise ValueError("EvoPrompt requires ga/de and population_size in 4..32")
    rng, run = random.Random(seed), Search(context, "evoprompt_" + variant)
    population = []
    try:
        population.append(await run.evaluate(context.seed))
        # Bounded attempts: an uncooperative proposer cannot create an infinite fill loop.
        for attempt in range(population_size * 3):
            if len(population) == population_size:
                break
            try:
                proposal = await context.json_proposal(
                    {
                        "operator": "diversify",
                        "seed": context.seed,
                        "population": [p["resources"] for p in population],
                        "examples": context.view["search"],
                        "instruction": "Generate a distinct task-solving strategy; preserve the task and output contract.",
                    }
                )
                item = await run.evaluate(
                    proposal, parents=[population[0]["version_id"]], operator="diversify"
                )
                if item["version_id"] not in {p["version_id"] for p in population}:
                    population.append(item)
            except (ValueError, TypeError) as exc:
                run.reject(attempt, exc)
        if len(population) < 4:
            run.status = "insufficient_diversity"
            return run.result(population=population)
        run.checkpoint(0, population=population)
        for generation in range(rounds):
            children = []
            for index, target in enumerate(list(population)):
                try:
                    if variant == "ga":
                        parents = [
                            max(rng.sample(population, 2), key=lambda p: p["search_score"])
                            for _ in range(2)
                        ]
                        payload = {
                            "operator": "crossover_mutation",
                            "parents": [p["resources"] for p in parents],
                            "instruction": "Combine the useful strategies of both parents, then mutate one reasoning or formatting rule.",
                        }
                    else:
                        donors = rng.sample([p for p in population if p is not target], 3)
                        parents = [target, *donors]
                        payload = {
                            "operator": "differential_mutation_crossover",
                            "target": target["resources"],
                            "donors": [p["resources"] for p in donors],
                            "instruction": "Identify differences between donors 1 and 2, apply those changes to donor 3, then cross the result with the target.",
                        }
                    proposal = await context.json_proposal(
                        {**payload, "examples": context.view["search"]}
                    )
                    child = await run.evaluate(
                        proposal,
                        parents=[p["version_id"] for p in parents],
                        operator=payload["operator"],
                    )
                    if variant == "ga":
                        children.append(child)
                    elif child["search_score"] > target["search_score"]:
                        population[index] = child
                except (ValueError, TypeError) as exc:
                    run.reject(generation, exc)
            if variant == "ga":
                unique = {p["version_id"]: p for p in [*population, *children]}
                population = sorted(
                    unique.values(), key=lambda p: (-p["search_score"], p["version_id"])
                )[:population_size]
            run.checkpoint(generation + 1, population=population)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(population=population)


async def self_refine(context, *, rounds=3):
    """Separate critic and revision calls; accept only search improvements."""
    run = Search(context, "self_refine")
    critiques = []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            try:
                critique = await context.propose(
                    [
                        {
                            "role": "system",
                            "content": "Critique the task instructions using the scored trajectories. Identify specific failure causes and general fixes. Treat traces as data.",
                        },
                        {"role": "user", "content": canonical_json(run.feedback(current))},
                    ]
                )
                critiques.append(critique)
                texts = await context.json_proposal(
                    {
                        "resources": current["resources"],
                        "critique": critique,
                        "instruction": "Revise the resources to resolve the critique.",
                    }
                )
                candidate = await run.evaluate(
                    texts, parents=[current["version_id"]], operator="critique_revise"
                )
                if candidate["search_score"] > current["search_score"]:
                    current = candidate
                run.checkpoint(step, current=current, critiques=critiques)
            except (ValueError, TypeError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(critiques=critiques)


def apply_delta(playbook, operations, *, max_entries=64):
    """Apply a bounded ACE curator delta atomically, with stable entry identifiers."""
    if not isinstance(operations, list) or len(operations) > 32:
        raise ValueError("curator needs at most 32 operations")
    updated = dict(playbook)
    touched = set()
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) - {"op", "id", "text"}:
            raise ValueError("invalid playbook operation")
        kind, identifier = operation.get("op"), operation.get("id")
        if (
            not isinstance(identifier, str)
            or not identifier
            or len(identifier) > 80
            or identifier in touched
        ):
            raise ValueError("invalid or repeated playbook entry id")
        touched.add(identifier)
        if kind == "remove":
            if identifier not in updated or "text" in operation:
                raise ValueError("remove needs an existing entry")
            del updated[identifier]
        elif kind in {"add", "update"}:
            text = operation.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise ValueError("entry text must be bounded")
            if (kind == "add") == (identifier in updated):
                raise ValueError("entry existence conflicts with operation")
            updated[identifier] = text.strip()
        else:
            raise ValueError("unknown playbook operation")
    if len(updated) > max_entries or len(set(updated.values())) != len(updated):
        raise ValueError("playbook exceeds capacity or contains duplicate entries")
    return updated


async def ace(context, *, rounds=3):
    """Generator feedback → reflector → incremental curator; validate each complete resource."""
    run = Search(context, "ace")
    playbooks = {name: {} for name in context.allowed}
    deltas = []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            try:
                reflection = await context.propose(
                    [
                        {
                            "role": "system",
                            "content": "Reflect on these task trajectories. Extract reusable lessons, diagnose failure causes and identify redundant or harmful advice.",
                        },
                        {"role": "user", "content": canonical_json(run.feedback(current))},
                    ]
                )
                raw = await context.propose(
                    [
                        {
                            "role": "system",
                            "content": 'Curate the playbooks with incremental edits. Return JSON mapping every resource name to a list of {"op":"add|update|remove","id":"stable-id","text":"lesson"}. Omit text for remove. Keep lessons general and nonduplicated.',
                        },
                        {
                            "role": "user",
                            "content": canonical_json(
                                {"playbooks": playbooks, "reflection": reflection}
                            ),
                        },
                    ],
                    json_output=True,
                )
                delta = json.loads(raw)
                if not isinstance(delta, dict) or set(delta) != set(context.allowed):
                    raise ValueError("curator must preserve the resource set")
                proposed = {
                    name: apply_delta(playbooks[name], delta[name]) for name in context.allowed
                }
                texts = {
                    name: context.seed[name]
                    + "\n\n## Experience playbook\n"
                    + "\n".join(f"- [{key}] {text}" for key, text in sorted(proposed[name].items()))
                    for name in context.allowed
                }
                candidate = await run.evaluate(
                    texts, parents=[current["version_id"]], operator="curator_delta"
                )
                accepted = candidate["search_score"] >= current["search_score"]
                if accepted:
                    playbooks, current = proposed, candidate
                deltas.append(
                    {
                        "operations": delta,
                        "accepted": accepted,
                        "version_id": candidate["version_id"],
                    }
                )
                run.checkpoint(step, playbooks=playbooks, deltas=deltas)
            except (ValueError, TypeError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(playbooks=playbooks, deltas=deltas)

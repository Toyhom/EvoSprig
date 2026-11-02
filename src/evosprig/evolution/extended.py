"""Training-free instruction, demonstration, population and experience search.

Native resource adaptations, not upstream benchmark implementations. GEPA remains
an official library adapter. Sources and exact variant boundaries are documented.
"""

import json
import random

from evosprig.core.protocols import BudgetExceeded
from evosprig.core.spec import canonical_json

from .search import Search


def training_report(context, item):
    return next(
        report for report in context.reports if report["report_id"] == item["search_report"]
    )


def appended(context, heading, text):
    return {
        name: context.seed[name] + "\n\n## " + heading + "\n" + text for name in context.allowed
    }


async def ape(context, *, rounds=3, seed=0):
    """Induce a candidate pool from task examples, then resample the best neighborhood."""
    run, pool = Search(context, "ape"), []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            for draw in range(3):
                try:
                    payload = {
                        "operator": "induce_instruction"
                        if step == 0
                        else "instruction_neighborhood",
                        "editable_resources": list(context.allowed),
                        "seed": context.seed,
                        "examples": context.view["search"],
                        "draw": draw,
                        "instruction": "Infer a concise, general instruction that solves these task types. Preserve tools and output contracts. Do not enumerate answers.",
                    }
                    if step:
                        payload["neighborhood_center"] = current["resources"]
                    proposal = await context.json_proposal(payload)
                    pool.append(
                        await run.evaluate(
                            proposal, parents=[current["version_id"]], operator=payload["operator"]
                        )
                    )
                except (ValueError, TypeError) as exc:
                    run.reject(step, exc)
            if pool:
                current = max([current, *pool], key=lambda item: item["search_score"])
            run.checkpoint(step, pool=pool, center=current["version_id"])
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(pool=pool)


async def protesgi(context, *, rounds=3, seed=0):
    """Failure minibatches produce textual gradients; a bounded beam retains candidates."""
    run, gradients, beam = Search(context, "protesgi"), [], []
    rng = random.Random(seed)
    try:
        beam = [await run.evaluate(context.seed)]
        for step in range(rounds):
            children = []
            for parent in beam:
                failures = [
                    s for s in training_report(context, parent)["samples"] if s["score"] < 1
                ]
                batch = (
                    rng.sample(failures, min(4, len(failures)))
                    if failures
                    else training_report(context, parent)["samples"][:4]
                )
                gradient = await context.propose(
                    [
                        {
                            "role": "system",
                            "content": "Compute a textual gradient: identify how the current instructions caused errors on this minibatch, and state the semantic direction that would reduce them. Use only supplied failures, never invent labels.",
                        },
                        {
                            "role": "user",
                            "content": canonical_json(
                                {"resources": parent["resources"], "minibatch": batch}
                            ),
                        },
                    ]
                )
                gradients.append(
                    {
                        "parent": parent["version_id"],
                        "sample_ids": [s["sample_id"] for s in batch],
                        "gradient": gradient,
                    }
                )
                for direction in range(2):
                    try:
                        proposal = await context.json_proposal(
                            {
                                "operator": "textual_gradient_step",
                                "resources": parent["resources"],
                                "gradient": gradient,
                                "direction": direction,
                                "instruction": "Revise the instruction in the direction that fixes these errors. Use a different concise implementation for each direction.",
                            }
                        )
                        children.append(
                            await run.evaluate(
                                proposal,
                                parents=[parent["version_id"]],
                                operator="textual_gradient_step",
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        run.reject(step, exc)
            unique = {item["version_id"]: item for item in [*beam, *children]}
            beam = sorted(
                unique.values(), key=lambda item: (-item["search_score"], item["version_id"])
            )[:2]
            run.checkpoint(step, beam=beam, gradients=gradients)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(
        beam=beam, gradients=gradients, variant="full-score beam; no UCB approximation"
    )


async def bootstrap(context, *, rounds=3, seed=0, random_search=False):
    """Harvest passing training executions; select demonstrations without rewriting labels."""
    run = Search(context, "fewshot_search" if random_search else "bootstrap_fewshot")
    rng, pool, selections = random.Random(seed), {}, []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            for sample in training_report(context, current)["samples"]:
                if sample["score"] >= 0.75 and sample["run"]["status"] == "succeeded":
                    demo = {"input": sample["input"], "output": sample["run"]["output"]}
                    if len(canonical_json(demo)) <= 12000:
                        pool[sample["sample_id"]] = demo
            if not pool:
                run.status = "no_passing_demonstrations"
                break
            for draw in range(3 if random_search else 1):
                ids = sorted(pool)
                chosen = (
                    rng.sample(ids, rng.randint(1, min(4, len(ids)))) if random_search else ids[:4]
                )
                proposal = appended(
                    context, "Worked examples", canonical_json([pool[key] for key in chosen])
                )
                item = await run.evaluate(
                    proposal,
                    parents=[current["version_id"]],
                    operator="demo_subset" if random_search else "bootstrap_traces",
                )
                selections.append({"version_id": item["version_id"], "demonstration_ids": chosen})
                if item["search_score"] >= current["search_score"]:
                    current = item
            run.checkpoint(step, demonstrations=pool, selections=selections)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(demonstrations=pool, selections=selections)


async def promptbreeder(context, *, rounds=3, population_size=4, seed=0):
    """Coevolve task instructions and the mutation instructions that generate them."""
    rng, run = random.Random(seed), Search(context, "promptbreeder")
    mutations = [
        {"text": text, "fitness": 0.0, "uses": 0}
        for text in [
            "Make the task procedure explicit and remove ambiguous instructions.",
            "Add checks for unsupported assumptions and missing information.",
            "Simplify redundant advice while preserving all task constraints.",
            "Improve the tool-use strategy and verification of tool results.",
        ]
    ]
    population, mutator_history = [], []
    try:
        population = [await run.evaluate(context.seed)]
        for attempt in range(population_size * 2):
            if len(population) >= population_size:
                break
            mutator = mutations[attempt % len(mutations)]
            try:
                texts = await context.json_proposal(
                    {
                        "operator": "task_mutation",
                        "mutation_instruction": mutator["text"],
                        "parent": context.seed,
                        "examples": context.view["search"],
                    }
                )
                item = await run.evaluate(
                    texts, parents=[population[0]["version_id"]], operator="task_mutation"
                )
                if item["version_id"] not in {p["version_id"] for p in population}:
                    population.append(item)
            except (ValueError, TypeError) as exc:
                run.reject(attempt, exc)
        for step in range(rounds):
            for _ in range(len(population)):
                parent = max(
                    rng.sample(population, min(2, len(population))), key=lambda p: p["search_score"]
                )
                mutator = max(
                    rng.sample(mutations, 2), key=lambda m: m["fitness"] / max(1, m["uses"])
                )
                try:
                    texts = await context.json_proposal(
                        {
                            "operator": "task_mutation",
                            "mutation_instruction": mutator["text"],
                            "parent": parent["resources"],
                            "feedback": run.feedback(parent),
                        }
                    )
                    child = await run.evaluate(
                        texts, parents=[parent["version_id"]], operator="task_mutation"
                    )
                    mutator["fitness"] += child["search_score"] - parent["search_score"]
                    mutator["uses"] += 1
                    unique = {item["version_id"]: item for item in [*population, child]}
                    population = sorted(
                        unique.values(), key=lambda p: (-p["search_score"], p["version_id"])
                    )[:population_size]
                except (ValueError, TypeError) as exc:
                    run.reject(step, exc)
            instruction = await context.propose(
                [
                    {
                        "role": "system",
                        "content": "Evolve a mutation instruction for improving task prompts. Return only one short reusable mutation instruction, not the task prompt. Use the fitness history to improve the mutation strategy.",
                    },
                    {"role": "user", "content": canonical_json({"mutation_population": mutations})},
                ]
            )
            if not instruction.strip() or len(instruction) > 4000:
                run.reject(step, ValueError("mutation instruction is unbounded"))
                continue
            worst = min(
                range(len(mutations)),
                key=lambda i: mutations[i]["fitness"] / max(1, mutations[i]["uses"]),
            )
            mutator_history.append({"replaced": dict(mutations[worst]), "new": instruction})
            mutations[worst] = {"text": instruction, "fitness": 0.0, "uses": 0}
            run.checkpoint(step, population=population, mutation_population=mutations)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(
        population=population, mutation_population=mutations, mutator_history=mutator_history
    )


async def reflexion(context, *, rounds=3, seed=0):
    """Keep bounded episodic reflections across retries, without changing the base policy."""
    run, episodes = Search(context, "reflexion"), []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            failed = [
                sample
                for sample in training_report(context, current)["samples"]
                if sample["score"] < 1
            ]
            if not failed:
                break
            reflection = await context.propose(
                [
                    {
                        "role": "system",
                        "content": "Reflect on the failed agent trials and their environment feedback. State a specific mistake, its cause and a general action for the next attempt. Do not copy answers or assume a successful action without a receipt.",
                    },
                    {
                        "role": "user",
                        "content": canonical_json(
                            {"trials": failed, "prior_reflections": episodes[-5:]}
                        ),
                    },
                ]
            )
            episodes.append(
                {
                    "trial": step,
                    "sample_ids": [s["sample_id"] for s in failed],
                    "reflection": reflection[:6000],
                }
            )
            texts = appended(
                context,
                "Reflections from prior work",
                "\n".join(item["reflection"] for item in episodes[-5:]),
            )
            current = await run.evaluate(
                texts, parents=[current["version_id"]], operator="episodic_reflection"
            )
            run.checkpoint(step, episodes=episodes, current=current["version_id"])
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(episodes=episodes)


async def expel(context, *, rounds=3, seed=0):
    """Contrast observed successful/failed experiences and maintain rules linked to observations."""
    run, rules, experiences = Search(context, "expel"), {}, []
    try:
        current = await run.evaluate(context.seed)
        for step in range(rounds):
            experiences.extend(training_report(context, current)["samples"])
            successful = [s for s in experiences if s["score"] >= 0.75]
            failed = [s for s in experiences if s["score"] < 0.75]
            allowed = {s["sample_id"] for s in experiences}
            raw = await context.propose(
                [
                    {
                        "role": "system",
                        "content": 'Extract reusable insights by contrasting successful and failed agent experiences. Return JSON {"rules":[{"id":"stable-id","text":"general rule","sources":["sample-id"]}]}. Revise or remove existing rules when the observations contradict them. At most 16 rules, each grounded in supplied sample IDs. Do not copy answers.',
                    },
                    {
                        "role": "user",
                        "content": canonical_json(
                            {
                                "successful": successful[-8:],
                                "failed": failed[-8:],
                                "existing_rules": rules,
                            }
                        ),
                    },
                ],
                json_output=True,
            )
            try:
                entries = json.loads(raw)["rules"]
                if not isinstance(entries, list) or len(entries) > 16:
                    raise ValueError("rules exceed bounds")
                proposed = {}
                for item in entries:
                    if (
                        set(item) != {"id", "text", "sources"}
                        or not isinstance(item["text"], str)
                        or not 1 <= len(item["text"]) <= 2000
                        or not isinstance(item["id"], str)
                        or not 1 <= len(item["id"]) <= 80
                        or item["id"] in proposed
                    ):
                        raise ValueError("invalid rule")
                    if (
                        not isinstance(item["sources"], list)
                        or not item["sources"]
                        or not set(item["sources"]) <= allowed
                    ):
                        raise ValueError("rule must cite observed training experiences")
                    proposed[item["id"]] = item
                texts = appended(
                    context,
                    "Experience-based rules",
                    "\n".join(f"- {item['text']}" for item in proposed.values()),
                )
                candidate = await run.evaluate(
                    texts, parents=[current["version_id"]], operator="contrast_experiences"
                )
                if candidate["search_score"] >= current["search_score"]:
                    rules, current = proposed, candidate
                run.checkpoint(step, rules=rules, experience_count=len(experiences))
            except (ValueError, TypeError, KeyError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(rules=rules, experience_count=len(experiences))

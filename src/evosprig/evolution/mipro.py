"""Joint instruction/demo search over resources, following MIPRO (2406.11695).

Uses grounded instruction proposals, passing component traces and a categorical
TPE sampler. This native variant evaluates full frozen splits and uses independent
categorical densities; it does not depend on the DSPy program representation.
"""

import itertools
import math
import random
import re

from evosprig.core.protocols import BudgetExceeded
from evosprig.core.spec import ResourceRef, canonical_json

from .search import Search


def resource_uses(spec, allowed):
    uses = {name: [] for name in allowed}

    def visit(graph, prefix):
        for name, node in graph.nodes.items():
            path = prefix + "/" + re.escape(name)
            names = list(node.skills)
            if isinstance(node.instructions, ResourceRef):
                names.append(node.instructions.resource)
            for resource in names:
                if resource in uses:
                    uses[resource].append({
                        "path": path, "type": node.type,
                        "inputs": list(node.inputs), "output_schema": node.output_schema,
                    })
            if node.body:
                suffix = r"/item-\d+" if node.type == "map" else r"/iteration-\d+"
                visit(node.body, path + suffix)
            for branch, body in node.branches.items():
                visit(body, path + "/" + re.escape(branch))

    visit(spec.graph, "graph")
    return uses


def demonstrations(samples, uses, threshold):
    """Only passing search executions supply actual per-node input/output pairs."""
    pools = {name: [] for name in uses}
    for sample in samples:
        if sample["score"] < threshold or sample["run"]["status"] != "succeeded":
            continue
        observed = sample["observations"]
        for name, nodes in uses.items():
            for path, output in observed.get("nodes", {}).items():
                if path not in observed.get("node_inputs", {}) or not any(
                    re.fullmatch(node["path"], path) for node in nodes
                ):
                    continue
                demo = {
                    "sample_id": sample["sample_id"], "node": path,
                    "input": observed["node_inputs"][path], "output": output,
                }
                if len(canonical_json(demo)) <= 12000:
                    pools[name].append(demo)
    return pools


def choose_trial(sizes, history, seen, rng):
    """Maximize l(x)/g(x), with Laplace-smoothed categorical Parzen densities."""
    total = math.prod(sizes)
    if len(seen) >= total:
        return None
    if total <= 1024:
        available = [x for x in itertools.product(*(range(n) for n in sizes)) if x not in seen]
    else:
        available = []
    if len(history) < 4:
        if available:
            return rng.choice(available)
        for _ in range(256):
            choice = tuple(rng.randrange(n) for n in sizes)
            if choice not in seen:
                return choice
        return None
    ranked = sorted(history, key=lambda item: item[1], reverse=True)
    split = max(1, math.ceil(len(ranked) * 0.25))
    good, bad = ranked[:split], ranked[split:]
    densities = []
    for dimension, size in enumerate(sizes):
        def density(items):
            counts = [1.0] * size
            for choice, _ in items:
                counts[choice[dimension]] += 1
            return [n / (len(items) + size) for n in counts]
        densities.append((density(good), density(bad)))
    if not available:
        for _ in range(128):
            candidate = tuple(
                rng.choices(range(size), weights=densities[i][0])[0]
                for i, size in enumerate(sizes)
            )
            if candidate not in seen:
                available.append(candidate)
        # Uniform exploration keeps unobserved combinations reachable.
        available.extend(
            candidate for _ in range(128)
            if (candidate := tuple(rng.randrange(n) for n in sizes)) not in seen
        )
    return max(
        available,
        key=lambda choice: sum(math.log(g[i]) - math.log(b[i]) for i, (g, b) in zip(choice, densities)),
        default=None,
    )


async def optimize(context, *, rounds=3, seed=0, instruction_candidates=3,
                   demo_candidates=3, max_demos=2, demo_threshold=0.8):
    rng, run = random.Random(seed), Search(context, "mipro")
    names = list(context.allowed)
    instructions = {name: [context.seed[name]] for name in names}
    demo_sets = {name: [[]] for name in names}
    trials, pools = [], {}
    try:
        baseline = await run.evaluate(context.seed)
        feedback = run.feedback(baseline)
        uses = resource_uses(context.base.spec, names)
        pools = demonstrations(feedback["trajectories"], uses, demo_threshold)
        for name in names:
            limit = min(max_demos, len(pools[name]))
            for _ in range(demo_candidates * 8):
                if not limit or len(demo_sets[name]) >= demo_candidates:
                    break
                subset = rng.sample(pools[name], rng.randint(1, limit))
                if subset not in demo_sets[name]:
                    demo_sets[name].append(subset)
        for index in range(instruction_candidates - 1):
            try:
                proposal = await context.json_proposal({
                    "operator": "grounded_instruction_proposal",
                    "resources": context.seed, "resource_uses": uses,
                    "task_examples": context.view["search"],
                    "feedback": feedback, "passing_component_traces": pools,
                    "proposal_index": index,
                    "instruction": "Propose a distinct instruction strategy for each editable resource, grounded in the task, component role and observed outputs. Preserve tool and output contracts. Return instructions only; demonstrations are selected separately. Do not list task-specific answers.",
                })
                for name, value in proposal.items():
                    if value not in instructions[name]:
                        instructions[name].append(value)
            except (ValueError, TypeError) as exc:
                run.reject(index, exc)
        sizes = [size for name in names for size in (len(instructions[name]), len(demo_sets[name]))]
        origin = tuple(0 for _ in sizes)
        seen, history = {origin}, [(origin, baseline["search_score"])]
        for step in range(rounds * 4):
            choice = choose_trial(sizes, history, seen, rng)
            if choice is None:
                break
            seen.add(choice)
            texts = {}
            selected_demos = {}
            for index, name in enumerate(names):
                text = instructions[name][choice[index * 2]]
                demos = demo_sets[name][choice[index * 2 + 1]]
                if demos:
                    text += "\n\n## Component examples\n" + canonical_json([
                        {k: v for k, v in demo.items() if k != "sample_id"} for demo in demos
                    ])
                texts[name] = text
                selected_demos[name] = [d["sample_id"] for d in demos]
            try:
                item = await run.evaluate(texts, parents=[baseline["version_id"]], operator="joint_instruction_demo_trial")
                history.append((choice, item["search_score"]))
                trials.append({"choice": choice, "version_id": item["version_id"],
                               "search_score": item["search_score"], "demonstrations": selected_demos})
                run.checkpoint(step, trials=trials)
            except (ValueError, TypeError) as exc:
                run.reject(step, exc)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    return run.result(instruction_candidates=instructions, demonstration_candidates=demo_sets,
                      trials=trials, sampler="categorical-tpe", bootstrap_samples=pools)

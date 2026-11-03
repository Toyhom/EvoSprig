"""SkillOpt bounded fast/slow edits and Evo-Harness task-stream compilation.

Sources: arxiv.org/abs/2605.23904 and arxiv.org/abs/2608.15071.
"""

import copy
import json
import random

from pydantic import Field

from evosprig.core.protocols import BudgetExceeded
from evosprig.core.spec import Contract, canonical_json

from .harness_common import ask
from .search import Search

START, END = "<!-- SLOW_UPDATE_START -->", "<!-- SLOW_UPDATE_END -->"


class SkillOptions(Contract):
    edit_budget: int = Field(default=4, ge=1, le=32)
    edit_chars: int = Field(default=2000, ge=1, le=12000)
    slow_every: int = Field(default=2, ge=2, le=20)
    batch_size: int = Field(default=4, ge=1, le=100)
    success_threshold: float = Field(default=1.0, ge=0, le=1)
    general_min_tasks: int = Field(default=2, ge=2, le=100)
    max_skills: int = Field(default=40, ge=1, le=100)


def skill_resources(context):
    if any(context.base.spec.resources[n].role != "skill" for n in context.allowed):
        raise ValueError("this method requires attached skill resources")


def apply_patch(texts, edits, *, budget, max_chars):
    if not isinstance(edits, list) or not 0 < len(edits) <= budget:
        raise ValueError("skill patch exceeds its edit budget")
    result, size = dict(texts), 0
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) - {"resource", "op", "old", "text"}:
            raise ValueError("invalid skill edit")
        name, kind = edit.get("resource"), edit.get("op")
        old, text = edit.get("old", ""), edit.get("text", "")
        if name not in result or not isinstance(old, str) or not isinstance(text, str):
            raise ValueError("invalid skill target")
        if any(marker in old + text for marker in (START, END)):
            raise ValueError("fast edits cannot alter protected guidance")
        current = result[name]
        protected = ""
        if START in current:
            start, end = current.index(START), current.index(END) + len(END)
            protected = current[start:end]
            if old and old in protected:
                raise ValueError("fast edits cannot alter protected guidance")
        if kind == "append":
            current += "\n" + text
        elif kind in {"replace", "delete", "insert_after"} and old and current.count(old) == 1:
            replacement = "" if kind == "delete" else old + text if kind == "insert_after" else text
            current = current.replace(old, replacement, 1)
        else:
            raise ValueError("edit needs a unique anchor and a supported operation")
        if protected and protected not in current:
            raise ValueError("protected guidance changed")
        size += len(old) + len(text)
        result[name] = current
    if size > max_chars:
        raise ValueError("skill patch exceeds its textual step size")
    return result


async def skillopt(context, *, config):
    skill_resources(context)
    options = SkillOptions.model_validate(config.options)
    run, rejected, snapshots, meta = Search(context, "skillopt"), [], [], ""
    current = None
    rng = random.Random(config.seed)
    try:
        current = await run.evaluate(context.seed)
        for epoch in range(config.rounds):
            tasks = list(context.view["search"])
            rng.shuffle(tasks)
            for offset in range(0, len(tasks), options.batch_size):
                try:
                    report = await context.evaluate(
                        current["resources"], "search", tasks[offset : offset + options.batch_size]
                    )
                    outcomes = {"success": [], "failure": []}
                    for sample in report["samples"]:
                        key = (
                            "success"
                            if sample["score"] >= options.success_threshold
                            and sample["run"]["status"] == "succeeded"
                            else "failure"
                        )
                        outcomes[key].append(sample)
                    edits = await ask(
                        context,
                        "Propose bounded edits to reusable skills. Return an array of {resource,op,old,text}; op is append,replace,delete,insert_after. Anchors must be unique. Never change protected slow guidance. Fix recurring failures and preserve successful procedures.",
                        {
                            "skills": current["resources"],
                            "outcomes": outcomes,
                            "rejected": rejected[-5:],
                            "meta": meta,
                            "edit_budget": options.edit_budget,
                            "max_changed_chars": options.edit_chars,
                        },
                    )
                    proposal = apply_patch(
                        current["resources"],
                        edits,
                        budget=options.edit_budget,
                        max_chars=options.edit_chars,
                    )
                    item = await run.evaluate(
                        proposal, parents=[current["version_id"]], operator="fast_patch"
                    )
                    accepted = item["selection_score"] > current["selection_score"]
                    if accepted:
                        current = item
                    else:
                        rejected.append({"edits": edits, "score": item["selection_score"]})
                    context.emit(
                        "skillopt.decision",
                        phase="fast",
                        accepted=accepted,
                        version_id=item["version_id"],
                    )
                except (ValueError, TypeError) as exc:
                    run.reject(epoch, exc)
            snapshots.append(current)
            if (epoch + 1) % options.slow_every == 0:
                try:
                    comparison = [
                        await context.evaluate(
                            item["resources"], "search", tasks[: options.batch_size]
                        )
                        for item in (snapshots[-options.slow_every], current)
                    ]
                    slow = await ask(
                        context,
                        'Compare earlier and current skill trajectories. Return {"meta":string,"guidance":{resource:string}}. Meta advises future optimizer edits; guidance is concise reusable procedure for the target agent.',
                        {
                            "comparison": comparison,
                            "skills": current["resources"],
                            "rejected": rejected[-5:],
                        },
                    )
                    if (
                        not isinstance(slow.get("meta"), str)
                        or len(slow["meta"]) > 8000
                        or set(slow["guidance"]) != set(context.allowed)
                    ):
                        raise ValueError("invalid slow update")
                    meta, proposal = slow["meta"], dict(current["resources"])
                    for name, guidance in slow["guidance"].items():
                        if (
                            not isinstance(guidance, str)
                            or len(guidance) > options.edit_chars
                            or START in guidance
                            or END in guidance
                        ):
                            raise ValueError("invalid slow guidance")
                        text = proposal[name]
                        if START in text:
                            text = text[: text.index(START)] + text[text.index(END) + len(END) :]
                        proposal[name] = text.rstrip() + f"\n{START}\n{guidance}\n{END}"
                    item = await run.evaluate(
                        proposal, parents=[current["version_id"]], operator="slow_guidance"
                    )
                    accepted = item["selection_score"] > current["selection_score"]
                    if accepted:
                        current = item
                    context.emit(
                        "skillopt.decision",
                        phase="slow",
                        accepted=accepted,
                        version_id=item["version_id"],
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    run.reject(epoch, exc)
            run.checkpoint(epoch, meta=meta, rejected=rejected[-5:])
    except BudgetExceeded:
        run.status = "budget_exhausted"
    if current:
        run.best, run.best_score = current["resources"], current["selection_score"]
    return run.result(meta=meta, rejected=rejected, snapshots=[s["version_id"] for s in snapshots])


async def evo_harness(context, *, config):
    skill_resources(context)
    options = SkillOptions.model_validate(config.options)
    run = Search(context, "evo_harness")
    current, memories, online, libraries = dict(context.seed), [], [], {}
    for name, text in current.items():
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        libraries[name] = (
            parsed
            if isinstance(parsed, dict) and parsed.get("evosprig_skill_library") == 1
            else {"evosprig_skill_library": 1, "base": text, "entries": []}
        )
    try:
        for step in range(config.rounds):
            batch = context.view["search"][
                step * options.batch_size : (step + 1) * options.batch_size
            ]
            if not batch:
                break
            report = await context.evaluate(current, "search", batch)
            online.extend(s["score"] for s in report["samples"])
            usable = []
            for sample in report["samples"]:
                if (
                    sample["score"] >= options.success_threshold
                    and sample["run"]["status"] == "succeeded"
                ):
                    continue
                try:
                    memory = await ask(
                        context,
                        'Extract a reusable procedure from this failed task. Return {"trigger":string,"lesson":string} or {"skip":true}.',
                        sample,
                    )
                    if memory.get("skip") is True:
                        continue
                    if any(
                        not isinstance(memory.get(k), str)
                        or not memory[k].strip()
                        or len(memory[k]) > 4000
                        for k in ("trigger", "lesson")
                    ):
                        raise ValueError("invalid task memory")
                    usable.append({**memory, "task_id": sample["sample_id"]})
                except (ValueError, TypeError, AttributeError) as exc:
                    run.reject(step, exc)
            memories.extend(usable)
            if not usable:
                continue
            for level in ("topic", "general"):
                try:
                    updates = await ask(
                        context,
                        "Compile task memories into skill-library changes. Return an array of {resource,id,trigger,body,sources,op}; op is upsert or remove. Sources must be task IDs from this batch. Change only the requested level. General skills need the specified minimum distinct sources.",
                        {
                            "level": level,
                            "libraries": libraries,
                            "memories": usable,
                            "general_min_tasks": options.general_min_tasks,
                        },
                    )
                    if not isinstance(updates, list) or len(updates) > options.max_skills:
                        raise ValueError("invalid library changes")
                    proposed = copy.deepcopy(libraries)
                    for edit in updates:
                        if not isinstance(edit, dict) or set(edit) != {
                            "resource",
                            "id",
                            "trigger",
                            "body",
                            "sources",
                            "op",
                        }:
                            raise ValueError("invalid library operation")
                        name, identifier = edit["resource"], edit["id"]
                        if (
                            name not in proposed
                            or not isinstance(identifier, str)
                            or not identifier
                            or len(identifier) > 80
                        ):
                            raise ValueError("invalid skill identity")
                        sources = edit["sources"]
                        if (
                            not isinstance(sources, list)
                            or not sources
                            or any(not isinstance(s, str) for s in sources)
                            or set(sources) - {m["task_id"] for m in usable}
                        ):
                            raise ValueError("skill sources must belong to current task memories")
                        if level == "general" and len(set(sources)) < options.general_min_tasks:
                            raise ValueError("general guidance needs multiple source tasks")
                        old = next(
                            (e for e in proposed[name]["entries"] if e["id"] == identifier), None
                        )
                        if old and old["level"] != level:
                            raise ValueError("skill curator cannot change another level")
                        proposed[name]["entries"] = [
                            e for e in proposed[name]["entries"] if e["id"] != identifier
                        ]
                        if edit["op"] == "upsert":
                            if any(
                                not isinstance(edit[k], str)
                                or not edit[k].strip()
                                or len(edit[k]) > 4000
                                for k in ("trigger", "body")
                            ):
                                raise ValueError("invalid skill content")
                            proposed[name]["entries"].append(
                                {
                                    "id": identifier,
                                    "trigger": edit["trigger"],
                                    "body": edit["body"],
                                    "sources": sorted(set(sources)),
                                    "level": level,
                                }
                            )
                        elif edit["op"] != "remove" or old is None:
                            raise ValueError("invalid skill removal")
                    if any(
                        len(lib["entries"]) > options.max_skills or len(canonical_json(lib)) > 48000
                        for lib in proposed.values()
                    ):
                        raise ValueError("skill library exceeds capacity")
                    candidate = {n: canonical_json(lib) for n, lib in proposed.items()}
                    context.archive(candidate)
                    libraries, current = proposed, candidate
                    context.emit(
                        "skill_library.updated",
                        level=level,
                        entries=sum(len(v["entries"]) for v in libraries.values()),
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    run.reject(step, exc)
            run.checkpoint(step, libraries=libraries, memories=memories)
    except BudgetExceeded:
        run.status = "budget_exhausted"
    # Online accumulation returns the latest compiled library. The study performs
    # independent release validation before it can become the deployed version.
    run.best, run.best_score = current, -1.0
    return run.result(
        libraries=libraries,
        online_tasks=len(online),
        online_score=sum(online) / len(online) if online else None,
    )

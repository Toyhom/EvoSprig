"""Lightweight OPRO baseline: score-history-conditioned instruction proposals.

Method attribution: Yang et al., Large Language Models as Optimizers (2023),
https://arxiv.org/abs/2309.03409. Independent implementation for resource text;
this is not the authors' experimental harness or a reproduction of their results.
"""

from evosprig.core.protocols import BudgetExceeded


async def optimize(context, *, rounds=3):
    history = []
    best = context.seed
    best_score = -1.0
    status = "completed"
    errors = []
    for step in range(rounds + 1):
        try:
            if step == 0:
                texts = context.seed
            else:
                texts = await context.json_proposal(
                    {
                        "method": "OPRO score-history baseline",
                        "editable_resources": list(context.allowed),
                        "history": sorted(history, key=lambda item: item["search_score"])[-10:],
                        "search_examples": context.view["search"],
                        "instruction": "Propose an instruction set that improves the search score. Generalize the task rules rather than listing sample answers.",
                    }
                )
            search = await context.evaluate(texts, "search")
            selection = await context.evaluate(texts, "selection")
            history.append(
                {
                    "resources": texts,
                    "search_score": search["score"],
                    "selection_score": selection["score"],
                    "version_id": search["version_id"],
                    "search_report": search["report_id"],
                    "selection_report": selection["report_id"],
                }
            )
            if selection["score"] > best_score:
                best, best_score = texts, selection["score"]
            context.emit(
                "method.checkpoint", method="opro", step=step, history=history, selected=best
            )
        except BudgetExceeded:
            status = "budget_exhausted"
            break
        except (ValueError, TypeError) as exc:
            # Invalid edits are rejected and the current release stays untouched.
            error = {
                "step": step,
                "type": type(exc).__name__,
                "reason": "candidate failed resource or response validation",
            }
            errors.append(error)
            context.emit("candidate.rejected", **error)
    return {
        "method": "opro",
        "implementation": "native-score-history-baseline",
        "selected": best,
        "selected_score": best_score if best_score >= 0 else None,
        "history": history,
        "errors": errors,
        "status": status,
    }

"""Official GEPA 0.1.4 driver with an EvoSprig evaluation/trace adapter."""

from __future__ import annotations

import asyncio

from evosprig.core.protocols import BudgetExceeded


class Adapter:
    propose_new_texts = None

    def __init__(self, context):
        self.context = context

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch

        if not batch:
            return EvaluationBatch(
                outputs=[], scores=[], trajectories=[] if capture_traces else None
            )
        search_ids = {sample["id"] for sample in self.context.view["search"]}
        split = "search" if batch[0]["id"] in search_ids else "selection"
        report = self.context.sync(self.context.evaluate(candidate, split, batch))
        samples = report["samples"]
        return EvaluationBatch(
            outputs=[sample["run"]["output"] for sample in samples],
            scores=[sample["score"] for sample in samples],
            trajectories=samples if capture_traces else None,
        )

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        from evosprig.evaluation.evidence import model_evidence

        if eval_batch.trajectories is None:
            raise ValueError("GEPA reflection requires captured trajectories")
        feedback = [
            {
                "Inputs": sample["input"],
                "Generated Outputs": sample["run"]["output"],
                "Feedback": {
                    "score": sample["score"],
                    "expected": sample["expected"],
                    "reason": sample["feedback"],
                    "error": sample["run"]["error"],
                },
                "Execution Trace": sample["run"]["events"],
            }
            for sample in eval_batch.trajectories
        ]
        return {component: model_evidence(feedback) for component in components_to_update}


class EventLogger:
    def __init__(self, context):
        self.context = context

    def log(self, message):
        # Keep method diagnostics, without duplicating full candidate/example text in logs.
        self.context.emit("method.progress", method="gepa", message=str(message)[:1000])


async def optimize(context, *, max_metric_calls=30, seed=0):
    try:
        import gepa
    except ImportError:
        raise ValueError("install evosprig[evolution] for the official GEPA adapter") from None
    adapter = Adapter(context)

    def reflection(prompt):
        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
        return context.sync(context.propose(messages))

    def stop(state):
        try:
            context.meter.check()
        except BudgetExceeded:
            return True
        return context.meter.state["candidates"] >= context.meter.limits.max_candidates

    def run():
        # No pickle checkpoints are loaded. The returned algorithm archive is JSON,
        # and candidates/reports/checkpoint events persist through EvoSprig stores.
        return gepa.optimize(
            seed_candidate=context.seed,
            trainset=context.view["search"],
            valset=context.view["selection"],
            adapter=adapter,
            reflection_lm=reflection,
            max_metric_calls=max_metric_calls,
            reflection_minibatch_size=min(3, len(context.view["search"])),
            candidate_selection_strategy="pareto",
            skip_perfect_score=False,
            use_merge=False,
            seed=seed,
            stop_callbacks=stop,
            logger=EventLogger(context),
            display_progress_bar=False,
            raise_on_exception=True,
        )

    try:
        result = await asyncio.to_thread(run)
        archive = result.to_dict()
        context.emit("method.checkpoint", method="gepa", state=archive)
        return {
            "method": "gepa",
            "implementation": "official-gepa-0.1.4",
            "selected": result.best_candidate,
            "selected_score": result.val_aggregate_scores[result.best_idx],
            "state": archive,
            "status": "completed",
        }
    except BudgetExceeded:
        reports = [report for report in context.reports if report["split"] == "selection"]
        best = max(reports, key=lambda report: report["score"], default=None)
        selected = (
            context.seed
            if best is None
            else {
                name: context.store.get(context.scope, best["version_id"]).resources[name]
                for name in context.allowed
            }
        )
        return {
            "method": "gepa",
            "implementation": "official-gepa-0.1.4",
            "selected": selected,
            "selected_score": best["score"] if best else None,
            "status": "budget_exhausted",
        }

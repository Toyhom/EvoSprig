"""Turn task inputs into frozen, disjoint evaluation partitions."""

import random

from .suite import EvalSuite


def suite_from_inputs(inputs, *, name="my-tasks", rubric="", seed=0):
    if not 4 <= len(inputs) <= 10000 or any(not isinstance(item, dict) for item in inputs):
        raise ValueError("provide 4..10000 distinct JSON task inputs")
    samples = [{"id": f"task-{i + 1:04d}", "input": item} for i, item in enumerate(inputs)]
    random.Random(seed).shuffle(samples)
    count = len(samples)
    test_count = max(1, count // 5) if count >= 6 else 0
    selection_count = max(1, count // 5)
    release_count = max(2, count // 5)
    search_count = count - test_count - selection_count - release_count
    return EvalSuite.model_validate(
        {
            "id": name,
            "metric": {"kind": "llm_judge", "output_path": "", "rubric": rubric},
            "search": samples[:search_count],
            "selection": samples[search_count : search_count + selection_count],
            "release": samples[
                search_count + selection_count : count - test_count if test_count else count
            ],
            "test": samples[count - test_count :] if test_count else [],
        }
    )

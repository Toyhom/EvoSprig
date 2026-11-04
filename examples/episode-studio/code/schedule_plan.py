def run(inputs):
    plan = inputs["plan"]
    shots = plan["shots"]
    target = inputs["brief"]["target_seconds"]
    language = inputs["brief"]["language"].lower()
    chinese = language.startswith("zh") or "chinese" in language or "中文" in language or "普通话" in language
    speech = ["".join([line["text"] for line in shot["dialogue"]]) + shot["narration"] for shot in shots]
    floors = [max(3, (len(text) + 4) // 5) if chinese else max(3, (len(text.split()) + 2) // 3) for text in speech]
    durations = [max(floors[i], shots[i]["duration_seconds"]) for i in range(len(shots))]
    # Impossible timelines remain available for the script editor's structural
    # feedback; no words, shots or story events are discarded to force a fit.
    if max(floors) > 15 or sum(floors) > target or 15 * len(shots) < target:
        return plan
    if abs(sum(durations) - target) > max(3, target * 0.15):
        remaining = target
        durations = []
        for i in range(len(shots)):
            seconds = max(floors[i], remaining - 15 * (len(shots) - i - 1),
                min(15, remaining - sum(floors[i + 1:]), (remaining + len(shots) - i - 1) // (len(shots) - i)))
            durations = durations + [seconds]
            remaining = remaining - seconds
    return dict(plan.items() + [["shots", [dict(shots[i].items() + [["duration_seconds", durations[i]]]) for i in range(len(shots))]]])

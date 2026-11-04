def run(inputs):
    plan = inputs["output"]
    context = inputs.get("input", inputs)
    issues = []
    characters = [c["id"] for c in plan["characters"]]
    locations = [p["id"] for p in plan["locations"]]
    shots = [s["id"] for s in plan["shots"]]
    identifiers = characters + locations + shots
    language = context["brief"]["language"].lower()
    chinese_language = language.startswith("zh") or "chinese" in language or "中文" in language or "普通话" in language
    source = context.get("source")
    if source:
        expected = dict([[c["id"], c["name"]] for c in source["characters"]])
        actual = dict([[c["id"], c["name"]] for c in plan["characters"]])
        if actual != expected:
            issues = issues + ["Use the source reader's character IDs and names exactly, including unnamed roles. Update all shot and dialogue references. Required cast: " + str(expected)]
    if any([identifiers.count(key) > 1 for key in identifiers]):
        issues = issues + ["Give every character, location and shot a distinct ID."]
    if plan["shots"][0]["transition"] != "cut":
        issues = issues + ["The first shot must use cut; there is no preceding shot to continue."]
    target = context["brief"]["target_seconds"]
    total = sum([shot["duration_seconds"] for shot in plan["shots"]])
    if abs(total - target) > max(3, target * 0.15):
        count = len(plan["shots"])
        timing = ("The " + str(count) + " shots total " + str(total)
                + " seconds; the requested total is " + str(target) + ". Change the total by "
                + str(target - total) + " seconds. Keep each shot between 3 and 15 seconds, with at most 24 shots. "
                + "Use reaction beats and establishing shots where needed.")
        floors = [max(3, (len("".join([line["text"] for line in shot["dialogue"]]) + shot["narration"]) + 4) // 5)
                  if chinese_language else 3 for shot in plan["shots"]]
        if max(floors) <= 15 and sum(floors) <= target <= 15 * count:
            remaining = target
            durations = []
            for i in range(count):
                seconds = max(floors[i], remaining - 15 * (count - i - 1),
                              min(15, remaining - sum(floors[i + 1:]), (remaining + count - i - 1) // (count - i)))
                durations = durations + [seconds]
                remaining = remaining - seconds
            timing = timing + " A feasible duration_seconds assignment is " + str(dict([[shots[i], durations[i]] for i in range(count)]))
            timing = timing + ". These numbers total " + str(target) + "; use them, or return another assignment with the same total. Preserve the story and spoken lines."
        elif target > 15 * count:
            timing = timing + " Include at least " + str((target + 14) // 15) + " shots to fit this duration."
        issues = issues + [timing]
    for shot in plan["shots"]:
        if shot["location"] not in locations or any([c not in characters for c in shot["characters"]]):
            issues = issues + ["Shot " + shot["id"] + " refers to an undeclared character or location."]
        if any([line["speaker"] not in characters for line in shot["dialogue"]]):
            issues = issues + ["Dialogue speakers must use declared character IDs; put the narrator's words in narration."]
        if source:
            for line in shot["dialogue"]:
                matches = [original["speaker"] for original in source["dialogue"]
                           if line["text"] in original["text"] or original["text"] in line["text"]]
                if matches and all([speaker == matches[0] for speaker in matches]) and line["speaker"] != matches[0]:
                    issues = issues + ["Shot " + shot["id"] + ": assign this source dialogue to " + matches[0] + ": " + line["text"]]
        speech = "".join([line["text"] for line in shot["dialogue"]]) + shot["narration"]
        chinese = len(speech) if chinese_language else 0
        if chinese > shot["duration_seconds"] * 5:
            issues = issues + ["Shot " + shot["id"] + " has too much dialogue. Split it at a natural pause; allow at most five Chinese characters per second."]
    return {"valid": not issues, "feedback": "\n".join(issues[:12])}

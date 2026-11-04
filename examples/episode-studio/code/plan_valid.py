def run(inputs):
    plan = inputs["output"]
    issues = []
    characters = [c["id"] for c in plan["characters"]]
    locations = [p["id"] for p in plan["locations"]]
    shots = [s["id"] for s in plan["shots"]]
    identifiers = characters + locations + shots
    language = inputs["input"]["brief"]["language"].lower()
    chinese_language = language.startswith("zh") or "chinese" in language or "中文" in language or "普通话" in language
    source = inputs["input"].get("source")
    if source:
        expected = dict([[c["id"], c["name"]] for c in source["characters"]])
        actual = dict([[c["id"], c["name"]] for c in plan["characters"]])
        if actual != expected:
            issues = issues + ["Use the source reader's character IDs and names exactly, including unnamed roles. Update all shot and dialogue references. Required cast: " + str(expected)]
    if any([identifiers.count(key) > 1 for key in identifiers]):
        issues = issues + ["Give every character, location and shot a distinct ID."]
    if plan["shots"][0]["transition"] != "cut":
        issues = issues + ["The first shot must use cut; there is no preceding shot to continue."]
    target = inputs["input"]["brief"]["target_seconds"]
    total = sum([shot["duration_seconds"] for shot in plan["shots"]])
    if abs(total - target) > max(3, target * 0.15):
        issues = issues + ["The " + str(len(plan["shots"])) + " shots total " + str(total)
                + " seconds; the requested total is " + str(target) + ". Change the total by "
                + str(target - total) + " seconds. Keep each shot between 3 and 15 seconds, with at most 24 shots. "
                + "Use reaction beats and establishing shots where needed. Sum every duration before returning the complete plan."]
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

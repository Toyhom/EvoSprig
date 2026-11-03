def run(inputs):
    controls = inputs["output"]
    if "duration" in controls or "seed" in controls:
        return {"valid": False, "feedback": "The timeline supplies duration and seed; omit them from your controls."}
    errors = schema_errors(inputs["input"]["render_profile"]["controls"], controls)  # noqa: F821 — runtime builtin
    if errors:
        return {"valid": False, "feedback": " ".join(errors)}
    shot = inputs["input"]["shot"]
    prompt = controls["prompt"]
    for line in shot["dialogue"]:
        if line["text"].strip() and line["text"] not in prompt:
            errors = errors + ["Include the exact audible dialogue for " + line["speaker"] + ": " + line["text"]]
    narration = shot["narration"]
    if narration.strip() and narration not in prompt:
        errors = errors + ["Include this exact audible voiceover narration: " + narration]
    return {"valid": not errors, "feedback": " ".join(errors)}

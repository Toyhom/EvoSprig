def run(inputs):
    item = inputs["item"]
    attempt = inputs["attempt"]
    if item["kind"] == "character":
        composition = "One person shown once, full body, neutral pose, plain background. No panels, inset portraits, other people or scenery."
    else:
        composition = "One continuous wide environment view. No people, silhouettes, portraits or panels."
    prompt = item["prompt"] + "\n\nComposition: " + composition
    if inputs["feedback"]:
        prompt = prompt + "\n\nCorrect this problem in the new image: " + inputs["feedback"]
    return {"prompt": prompt, "attempt": attempt + 1,
            "options": {"width": 1344, "height": 768, "steps": 40,
                        "seed": 63000 + inputs["index"] * 100 + attempt}}

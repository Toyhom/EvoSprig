def run(inputs):
    plan = inputs["input"]["plan"]
    voices = inputs["output"]["voices"]
    speakers = []
    for shot in plan["shots"]:
        speakers = speakers + [line["speaker"] for line in shot["dialogue"]] + (["narrator"] if shot["narration"] else [])
    expected = list(dict([[speaker, True] for speaker in speakers]).keys())
    actual = [voice["id"] for voice in voices]
    valid = len(actual) == len(list(dict([[speaker, True] for speaker in actual]).keys())) and sorted(actual) == sorted(expected)
    return {"valid": valid, "feedback": "Return one voice for each speaking identity: " + ", ".join(expected) if not valid else ""}

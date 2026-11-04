def run(inputs):
    panel = inputs["panel"]
    entries = [entry for entry in inputs["catalog"]["assets"] if entry["character_id"] in panel["characters"]]
    return {"panel": panel, "style": inputs["style"], "references": [entry["asset"] for entry in entries],
            "reference_ids": [entry["character_id"] for entry in entries], "seed": 42 + inputs["index"], "options": {"seed": 42 + inputs["index"]}, "attempt": 0, "feedback": ""}

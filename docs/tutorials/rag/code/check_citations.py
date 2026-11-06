def run(inputs):
    text = inputs["output"]["text"]
    labels = [item["citation"] for item in inputs["input"]["citations"]]
    used = ["[" + part.split("]")[0] + "]" for part in text.split("[")[1:] if "]" in part]
    invalid = [label for label in used if label not in labels]
    valid = not invalid and (not labels or bool(used))
    return {"valid": valid, "feedback": "Use these exact source labels: " + ", ".join(labels) + ". Do not invent page numbers or citation labels."}

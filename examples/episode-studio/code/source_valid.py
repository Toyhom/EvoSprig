def run(inputs):
    source = inputs["input"]["source_text"]
    result = inputs["output"]
    ids = [character["id"] for character in result["characters"]]
    if any([ids.count(key) > 1 for key in ids]):
        return {"valid": False, "feedback": "Give each visible person a unique ID."}
    prior = inputs["input"].get("cast", [])
    for character in result["characters"]:
        matches = [c for c in prior if c["name"] == character["name"]]
        if matches and character["id"] != matches[0]["id"]:
            return {"valid": False, "feedback": "Keep the established character ID " + matches[0]["id"] + " for " + character["name"]}
        if character["source_quote"] not in source:
            return {"valid": False, "feedback": "For " + character["id"] + ", copy source_quote exactly from the supplied text."}
    for line in result["dialogue"]:
        if line["speaker"] not in ids:
            return {"valid": False, "feedback": "Every dialogue speaker must refer to a visible character ID."}
        if line["text"] not in source:
            return {"valid": False, "feedback": "Copy dialogue exactly from the source, without enclosing quotation marks. Incorrect line: " + line["text"]}
    return {"valid": True, "feedback": ""}

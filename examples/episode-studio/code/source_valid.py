def run(inputs):
    source = inputs["input"]["source_text"]
    result = inputs["output"]
    ids = [character["id"] for character in result["characters"]]
    if any([ids.count(key) > 1 for key in ids]):
        return {"valid": False, "feedback": "Give each visible person a unique ID."}
    for character in result["characters"]:
        if character["source_quote"] not in source:
            return {"valid": False, "feedback": "For " + character["id"] + ", copy source_quote exactly from the supplied text."}
    for line in result["dialogue"]:
        if line["speaker"] not in ids:
            return {"valid": False, "feedback": "Every dialogue speaker must refer to a visible character ID."}
        if line["text"] not in source:
            return {"valid": False, "feedback": "Copy dialogue exactly from the source, without enclosing quotation marks. Incorrect line: " + line["text"]}
    return {"valid": True, "feedback": ""}

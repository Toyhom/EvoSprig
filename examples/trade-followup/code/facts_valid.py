def run(inputs):
    request = inputs["input"]["request"]
    output = inputs["output"]
    ids = [fact["id"] for fact in request["product_facts"]]
    for claim in output["claims"]:
        if claim["fact_id"] not in ids:
            return {"valid": False, "feedback": "Use only product fact IDs present in the input."}
        if claim["sentence"] not in output["body"]:
            return {"valid": False, "feedback": "Each claim sentence must be an exact excerpt from the corrected email body."}
    source = request["conversation"] + " " + " ".join([fact["text"] for fact in request["product_facts"]])
    available = " "
    token = ""
    for char in source + " ":
        if char in "0123456789":
            token = token + char
        else:
            if token:
                available = available + token + " "
            token = ""
    token = ""
    for char in output["body"] + " ":
        if char in "0123456789":
            token = token + char
        else:
            if token and " " + token + " " not in available:
                return {"valid": False, "feedback": "The draft contains an unsupported number: " + token + ". Use only values from the conversation and product facts."}
            token = ""
    return {"valid": True, "feedback": ""}

def run(inputs):
    direction = inputs["output"]
    if direction["mode"] == "idea" and len(direction["expanded_story"].strip()) < 60:
        return {"valid": False, "feedback": "Expand the idea into a complete filmable story with a beginning, a change and an ending. Include concrete actions and any spoken lines."}
    return {"valid": True, "feedback": ""}

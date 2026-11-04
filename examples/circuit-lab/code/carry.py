def run(inputs):
    state = inputs["state"]
    result = inputs["simulation"]
    return {"request": state["request"], "analysis": state["analysis"], "target": state["target"],
            "previous": inputs["design"], "feedback": result, "accepted": result.get("ok", False) and result.get("accepted", False),
            "attempts": state["attempts"] + 1}

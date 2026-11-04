def run(inputs):
    output = inputs["output"]
    text = output["summary"] + " " + " ".join(output["recommendations"])
    allowed = ["revenue", "cost", "profit", "orders", "margin_pct", "periods", "best_period"]
    for key in allowed:
        text = text.replace("{{" + key + "}}", "")
    if "{{" in text or "}}" in text:
        return {"valid": False, "feedback": "Use only the seven metric placeholders listed in the reporting skill."}
    if any([char in "0123456789" for char in text]):
        return {"valid": False, "feedback": "Replace numeric claims in summary and recommendations with metric placeholders so all files use the calculated ledger."}
    return {"valid": True, "feedback": ""}

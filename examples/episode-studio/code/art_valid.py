def run(inputs):
    plan = inputs["input"]["plan"]
    expected = ["character:" + c["id"] for c in plan["characters"]] + ["location:" + p["id"] for p in plan["locations"]]
    actual = [a["kind"] + ":" + a["id"] for a in inputs["output"]["assets"]]
    valid = sorted(expected) == sorted(actual)
    return {"valid": valid, "feedback": "" if valid else "Provide exactly one reference asset for each planned character and location, using the exact ID and kind. Required: " + ", ".join(expected)}

def run(inputs):
    state = inputs["state"]
    checks = inputs["checks"]
    patch = inputs["patch"]
    review = inputs["review"]
    accepted = checks["passed"] and checks["patch_sha256"] == patch["sha256"] and review["accepted"]
    return {"request": state["request"], "workspace": state["workspace"], "plan": state["plan"],
            "check": state["check"], "accepted": accepted, "checks": checks, "patch": patch,
            "summary": inputs["summary"], "review": review,
            "feedback": review["feedback"] + "\nChecks:\n" + checks["output"]}

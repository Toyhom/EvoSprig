def run(inputs):
    state = inputs["state"]
    review = inputs["review"]
    checks = inputs["checks"]
    feedback = checks["issues"] + review["factual_issues"] + review["reader_feedback"] + review["edits"]
    accepted = checks["passed"] and review["accepted"] and len(review["factual_issues"]) == 0
    return {
        "request": state["request"], "brief": state["brief"], "previous": inputs["post"],
        "accepted": accepted, "feedback": feedback[:12], "rounds": state["rounds"] + 1,
        "changes": state["changes"] + [{"round": state["rounds"] + 1, "post": inputs["post"],
                                          "checks": checks, "review": review}]
    }

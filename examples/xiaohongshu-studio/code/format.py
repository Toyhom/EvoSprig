def run(inputs):
    state = inputs["state"]
    post = state["previous"]
    parts = [post["title"], post["body"]] + state["request"]["links"]
    tags = []
    for tag in post["tags"]:
        if tag not in tags:
            tags = tags + [tag]
    parts = parts + [" ".join(["#" + tag for tag in tags])]
    return {"text": "\n\n".join(parts), "post": post, "ready": state["accepted"],
            "feedback": state["feedback"], "rounds": state["rounds"], "changes": state["changes"]}

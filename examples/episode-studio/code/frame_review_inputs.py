def run(inputs):
    context = inputs["context"]
    assets = [inputs["frame"]] + context["references"]
    labels = ["candidate first frame"] + context["reference_labels"]
    if context["shot"]["transition"] == "continue" and context["previous"].get("last_frame"):
        assets = assets + [context["previous"]["last_frame"]]
        labels = labels + ["previous shot end"]
    return {"assets": assets, "labels": labels}

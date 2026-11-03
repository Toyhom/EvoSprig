def run(inputs):
    context = inputs["context"]
    previous = context["previous"]
    transition = inputs["transition"] if previous.get("last_frame") else "cut"
    if context.get("previous_shot") and context["previous_shot"]["location"] != context["shot"]["location"]:
        transition = "cut"
    shot = dict(context["shot"].items() + [["transition", transition]])
    references = context["references"]
    if transition == "continue":
        references = [previous["last_frame"]] + references
    video = [previous["tail"]] if transition == "continue" and previous.get("tail") else []
    adjusted = dict(context.items() + [["shot", shot], ["image_references", references], ["video_references", video]])
    return {"prompt": "Visual style: " + context["style"] + "\n\n" + inputs["prompt"],
            "options": {"width": 1664, "height": 928, "steps": 40,
                        "seed": inputs["context"]["seed"] + inputs["attempt"]},
            "attempt": inputs["attempt"] + 1, "context": adjusted}

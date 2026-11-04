def run(inputs):
    state = inputs["state"]
    return {"panel": state["panel"], "style": state["style"], "references": state["references"],
            "reference_ids": state["reference_ids"], "seed": state["seed"] + 100, "options": {"seed": state["seed"] + 100}, "attempt": state["attempt"] + 1,
            "feedback": inputs["review"]["feedback"], "accepted": inputs["review"]["accepted"], "image": inputs["image"]}

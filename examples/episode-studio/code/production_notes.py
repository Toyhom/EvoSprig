def run(inputs):
    notes = []
    for reference in inputs["references"]:
        review = reference.get("review", {})
        if review and not review["accepted"]:
            notes = notes + [{"stage": "reference", "id": reference["id"], "feedback": review["feedback"]}]
    for shot in inputs["shots"]:
        if not shot.get("frame_accepted", True):
            notes = notes + [{"stage": "first_frame", "id": shot["shot_id"], "feedback": shot.get("frame_feedback", "")}]
        if not shot["take"]["accepted"]:
            notes = notes + [{"stage": "video", "id": shot["shot_id"], "feedback": shot["take"]["review"]["feedback"]}]
    return {"notes": notes}

def run(inputs):
    shot = inputs["shot"]
    context = inputs["context"]
    catalog = context["assets"]
    characters = [a for a in catalog if a["kind"] == "character" and a["id"] in shot["characters"]]
    locations = [a for a in catalog if a["kind"] == "location" and a["id"] == shot["location"]]
    references = [a["asset"] for a in characters + locations]
    previous = inputs["previous"]
    previous_frame = previous.get("last_frame")
    image_references = references
    if shot["transition"] == "continue" and previous_frame:
        image_references = [previous_frame] + references
    voice_references = previous.get("voice_references", {})
    speakers = list(dict([[d["speaker"], True] for d in shot["dialogue"]] + ([["narrator", True]] if shot["narration"] else [])).keys())
    audio_references = [{"speaker": speaker, "asset": voice_references[speaker]}
                        for speaker in speakers if speaker in voice_references][:3]
    video_references = [previous["tail"]] if shot["transition"] == "continue" and previous.get("tail") else []
    return {"shot": shot, "style": context["art"]["style"], "references": references,
            "previous_shot": context["plan"]["shots"][inputs["index"] - 1] if inputs["index"] else None,
            "render_profile": context["render_profile"],
            "reference_labels": [a["id"] for a in characters + locations],
            "image_references": image_references,
            "audio_references": audio_references, "video_references": video_references,
            "cast": [c for c in context["plan"]["characters"] if c["id"] in shot["characters"]],
            "previous": {"last_frame": previous_frame, "tail": previous.get("tail"), "continuity": previous.get("continuity", {}),
                         "shot_id": previous.get("shot_id", ""), "voice_references": voice_references},
            "seed": 42000 + inputs["index"] * 100}

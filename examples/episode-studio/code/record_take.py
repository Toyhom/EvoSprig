def run(inputs):
    inspection = inputs["inspection"]
    review = inputs["review"]
    context = inputs["context"]
    shot = context["shot"]
    requires_audio = bool(shot["dialogue"] or shot["narration"])
    duration_ok = abs(inspection["duration_seconds"] - shot["duration_seconds"]) < 1
    audio_ok = not requires_audio or inspection["has_audio"]
    audio = inspection.get("audio")
    audible = audio is None or (audio["rms_dbfs"] > -55 and audio["audible_fraction"] > 0.01)
    audio_ok = audio_ok and (not requires_audio or audible)
    speech = inspection.get("speech")
    if requires_audio and speech is not None and not speech["text"].strip():
        audio_ok = False
    accepted = review["accepted"] and duration_ok and audio_ok
    feedback = review["feedback"]
    if not duration_ok:
        feedback = feedback + " Correct the clip duration to the planned duration."
    if not audio_ok:
        feedback = feedback + " Dialogue or narration is required; generate clearly audible speech with the planned lines."
    voices = dict(context["previous"].get("voice_references", {}))
    speakers = list(dict([[line["speaker"], True] for line in shot["dialogue"]] + ([["narrator", True]] if shot["narration"] else [])).keys())
    # Save only single-speaker takes as timbre references. A conversation's
    # mixed track cannot identify which voice belongs to which character.
    if accepted and len(speakers) == 1 and inspection.get("audio_asset") and speakers[0] not in voices:
        voices = dict(voices.items() + [[speakers[0], inspection["audio_asset"]]])
    return {"context": context, "accepted": accepted, "feedback": feedback,
            "attempt": inputs["attempt"] + 1,
            "take": {"shot": shot, "clip": inspection["clip"], "last_frame": inspection["last_frame"],
                     "tail": inspection.get("tail"), "voice_references": voices,
                     "continuity": review["continuity"], "review": review,
                     "controls": inputs["controls"], "duration_seconds": inspection["duration_seconds"],
                     "frame": inputs["frame"], "accepted": accepted}}

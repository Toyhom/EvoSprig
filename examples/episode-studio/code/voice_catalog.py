def run(inputs):
    voices = dict([[entry["id"], entry["asset"]] for entry in inputs["supplied"]])
    for shot in inputs["shots"]:
        voices = dict(voices.items() + shot.get("voice_references", {}).items())
    return {"voices": [{"id": name, "asset": voices[name]} for name in voices]}

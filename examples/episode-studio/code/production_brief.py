def run(inputs):
    request = inputs["request"]
    direction = inputs["direction"]
    return {
        "source_text": request["source_text"] if direction["mode"] == "story" else direction["expanded_story"],
        "style": request.get("style") or direction["style"],
        "language": request.get("language") or direction["language"],
        "target_seconds": request.get("target_seconds", direction["target_seconds"]),
    }

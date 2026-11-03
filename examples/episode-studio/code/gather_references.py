def run(inputs):
    context = inputs["context"]
    audio = context["audio_references"]
    return {"assets": [inputs["frame"]] + context["references"] + context["video_references"] + [r["asset"] for r in audio],
            "labels": {"pictures": ["shot first frame"] + context["reference_labels"],
                       "videos": ["previous shot ending"] if context["video_references"] else [],
                       "audio": [r["speaker"] + " voice reference" for r in audio]}}

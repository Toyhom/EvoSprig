def run(inputs):
    return {"images": [item["filename"] for item in inputs["items"] if item["media_type"].startswith("image/")],
            "audio": [item["filename"] for item in inputs["items"] if item["media_type"].startswith("audio/")],
            "videos": [item["filename"] for item in inputs["items"] if item["media_type"].startswith("video/")]}

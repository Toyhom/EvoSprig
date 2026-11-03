def run(inputs):
    clips = [item["asset"] for item in inputs["assets"] if item["asset"]["media_type"] == "video/mp4"]
    return clips[0]

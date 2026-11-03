def run(inputs):
    assets = [inputs["frame"]] + inputs["inspection"]["frames"]
    labels = ["planned first frame", "video beginning", "video middle", "video end"]
    if inputs["previous"].get("last_frame"):
        assets = assets + [inputs["previous"]["last_frame"]]
        labels = labels + ["previous shot end"]
    return {"assets": assets, "labels": labels}

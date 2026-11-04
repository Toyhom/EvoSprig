def run(inputs):
    supplied = dict([[item["kind"] + ":" + item["id"], item] for item in inputs["supplied"]])
    pending = []
    reused = []
    for item in inputs["assets"]:
        key = item["kind"] + ":" + item["id"]
        if key in supplied:
            reused = reused + [supplied[key]]
        else:
            pending = pending + [item]
    return {"pending": pending, "reused": reused}

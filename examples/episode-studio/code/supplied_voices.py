def run(inputs):
    voices = dict([[v["id"], v] for v in inputs["series"] + inputs["voices"]])
    return {"voices": list(voices.values())}

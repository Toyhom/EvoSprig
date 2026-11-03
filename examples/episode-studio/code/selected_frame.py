def run(inputs):
    selected = inputs["approved"] or inputs["reviewed"]
    return selected["frame"]

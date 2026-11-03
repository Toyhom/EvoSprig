def run(inputs):
    chosen = inputs["approved"] or inputs["reviewed"]
    return chosen["take"]

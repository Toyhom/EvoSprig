def run(inputs):
    return {"prompt": "Visual style: " + inputs["style"] + "\n\n" + inputs["asset"]["prompt"]}

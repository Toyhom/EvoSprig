def run(inputs):
    return {"clips": [shot["clip"] for shot in inputs["shots"]]}

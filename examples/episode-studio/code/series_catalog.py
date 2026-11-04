def run(inputs):
    return {"characters": inputs["plan"]["characters"], "locations": inputs["plan"]["locations"],
            "style": inputs["style"], "voices": inputs["voices"],
            "references": [{"id": item["id"], "kind": item["kind"], "asset": item["asset"]} for item in inputs["references"]]}

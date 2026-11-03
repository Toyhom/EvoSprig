def run(inputs):
    controls = inputs["output"]
    if "duration" in controls or "seed" in controls:
        return {"valid": False, "feedback": "The timeline supplies duration and seed; omit them from your controls."}
    errors = schema_errors(inputs["input"]["render_profile"]["controls"], controls)  # noqa: F821 — runtime builtin
    return {"valid": not errors, "feedback": " ".join(errors)}

def run(inputs):
    controls = inputs["controls"]
    context = inputs["context"]
    return dict(controls.items() + [["duration", context["shot"]["duration_seconds"]],
                                    ["seed", context["seed"] + inputs["attempt"]]])

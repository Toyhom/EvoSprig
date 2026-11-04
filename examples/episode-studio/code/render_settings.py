def run(inputs):
    controls = inputs["controls"]
    context = inputs["context"]
    defaults = context["render_profile"].get("defaults", {})
    changes = [[key, controls[key]] for key in controls
               if key == "prompt" or key not in defaults or controls[key] != defaults[key]]
    return dict(changes + [["action", context["shot"]["action_scene"]],
                                    ["duration", context["shot"]["duration_seconds"]],
                                    ["seed", context["seed"] + inputs["attempt"]]])

"""Connect the episode team to a model server, media service and render recipe."""

import argparse
import json
import os
from pathlib import Path

import yaml
from build_agent import ANY, ASSET, ASSETS, STRING, TEXT, obj

from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool


def profile(recipe, *, model_url, model_name, media_url, comfy_url, model_timeout_seconds=1200,
            model_connections=None):
    config = ComfyRecipeConfig.model_validate(recipe)
    if config.name != "film.recipe":
        raise ValueError("the recipe binding must be named film.recipe")
    comfy_recipe_tool(config)
    expected = {"prompt", "action", "steps", "scheduler", "shift_video", "shift_audio", "duration", "seed"}
    if expected - config.parameters.keys():
        raise ValueError("recipe controls missing: " + ", ".join(sorted(expected - config.parameters.keys())))
    if len(config.reference_slots) < 6:
        raise ValueError("the episode recipe needs at least six reference slots")
    if len(config.audio_slots) < 3 or not config.video_slots:
        raise ValueError("the episode recipe needs three audio reference slots and a video slot")
    model = {"base_url": model_url, "model": model_name, "api_key_env": "LOCAL_MODEL_API_KEY",
             "capabilities": ["text", "structured_output", "tool_calling", "vision"],
             "timeout_seconds": model_timeout_seconds, "json_mode": "without_tools",
             "options": {"chat_template_kwargs": {"enable_thinking": False}}}
    bindings = {"film.recipe": config.model_dump(mode="json"),
                "film.settings": {**config.model_dump(mode="json"), "kind": "comfy_recipe_info", "name": "film.settings"},
                "film.render": {"kind": "comfy_job", "name": "film.render", "base_url": comfy_url,
                                "dedicated": True, "job_timeout_seconds": 14400}}
    contracts = {
        "generate_image": ("generate-image", obj(prompt=TEXT, references=ASSETS, options=ANY), ASSET),
        "generate_voice": ("generate-voice", obj(text=TEXT, speaker={"enum": ["Chelsie", "Ethan", "Aiden"]},
                            direction=TEXT, seed={"type": "integer", "minimum": 0, "maximum": 2147483647},
                            max_seconds={"type": "number", "minimum": 1, "maximum": 30}), ASSET),
        "stage_reference": ("stage-reference", obj(asset=ASSET), obj(filename=TEXT, asset=ASSET)),
        "ingest_comfy": ("ingest-comfy", obj(outputs=ANY), obj(assets={"type": "array", "items": ANY})),
        "inspect_video": ("inspect-video", obj(asset=ASSET), ANY),
        "compose": ("compose", obj(clips=ASSETS, preserve_audio={"type": "boolean"}), ASSET),
    }
    for name, (path, inputs, outputs) in contracts.items():
        key = "media." + name
        bindings[key] = {"kind": "external_http", "name": key, "description": "Media: " + name,
                         "endpoint": media_url.rstrip("/") + "/" + path,
                         "input_schema": inputs, "output_schema": outputs,
                         "side_effect": "write", "idempotent": True}
    bindings["media.vision"] = {"kind": "http", "name": "media.vision", "description": "Read image previews",
                                "endpoint": media_url.rstrip("/") + "/vision", "method": "POST",
                                "input_schema": obj(assets=ASSETS),
                                "output_schema": obj(images={"type": "array", "items": STRING}),
                                "side_effect": "read_only", "max_response_bytes": 10000000}
    bindings["media.frame_vision"] = {**bindings["media.vision"], "name": "media.frame_vision",
                                     "input_schema": obj(asset=ASSET)}
    models = {"main": model, "vision": dict(model)}
    if model_connections is not None:
        from evosprig.plugins.openai_compatible import Connection

        if set(model_connections) - {"main", "vision"} or "main" not in model_connections:
            raise ValueError("model connections require main and optionally vision")
        models = {name: Connection.model_validate(value).model_dump(mode="json")
                  for name, value in model_connections.items()}
        models.setdefault("vision", dict(models["main"]))
        for name in ("main", "vision"):
            required = {"text", "structured_output"} | ({"vision"} if name == "vision" else set())
            if required - set(models[name]["capabilities"]):
                raise ValueError(name + " is missing capabilities: " + ", ".join(sorted(required - set(models[name]["capabilities"]))))
    return {"models": models, "tools": bindings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--model-url", default="http://127.0.0.1:18882/v1")
    parser.add_argument("--model-name", default="Qwen3.8-Flash-Next")
    parser.add_argument("--media-url", default="http://127.0.0.1:18880")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:18884")
    parser.add_argument("--model-timeout-seconds", type=float, default=1200)
    parser.add_argument("--model-config", type=Path, help="JSON connections: main and optional vision; keys stay in environment variables")
    parser.add_argument("--reuse-connections", type=Path, help="Preserve connections edited in an existing deployment")
    parser.add_argument("--check-model-keys", action="store_true", help="Check the effective connections before loading models")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = profile(json.loads(args.recipe.read_text()), model_url=args.model_url, model_name=args.model_name,
                     media_url=args.media_url, comfy_url=args.comfy_url, model_timeout_seconds=args.model_timeout_seconds,
                     model_connections=json.loads(args.model_config.read_text()) if args.model_config else None)
    if args.reuse_connections and args.reuse_connections.is_file():
        saved = yaml.safe_load(args.reuse_connections.read_text())
        result["models"].update(saved.get("models", {}))
        if saved.get("services"):
            result["services"] = saved["services"]
    if args.check_model_keys:
        for name in ("main", "vision"):
            key = result["models"][name]["api_key_env"]
            if key != "LOCAL_MODEL_API_KEY" and not os.environ.get(key):
                parser.error("set the model credential environment variable: " + key)
    with args.out.open("x") as target:
        yaml.safe_dump(result, target, sort_keys=False)

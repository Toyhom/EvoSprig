"""Install, download and supervise an Episode Studio production session."""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def command(argv, **kwargs):
    subprocess.run([str(part) for part in argv], check=True, **kwargs)


def python(env_root, name):
    return str(Path(env_root) / name / "bin/python")


def verify_weight(path, expected):
    path = Path(path)
    if path.stat().st_size != expected["size"]:
        raise RuntimeError("incomplete download: " + path.name)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected["sha256"]:
        raise RuntimeError("checksum mismatch: " + path.name)


def service_environment(config, role, state):
    env = {**os.environ, "LOCAL_MODEL_API_KEY": "local", "HF_HUB_OFFLINE": "1",
           "HF_HOME": str(state / "cache/huggingface"), "PYTHONPATH": str(ROOT / "src"),
           "FLASHINFER_WORKSPACE_BASE": str(state / "cache/flashinfer"),
           "VLLM_CACHE_ROOT": str(state / "cache/vllm"), "TRITON_CACHE_DIR": str(state / "cache/triton")}
    prefix = Path(config["env_root"]) / ("episode-core" if role == "app" else "episode-" + role)
    sites = sorted(prefix.glob("lib/python*/site-packages"))
    libraries = [str(p) for site in sites for p in sorted(site.glob("nvidia/*/lib"))]
    if libraries:
        env["LD_LIBRARY_PATH"] = ":".join(libraries + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else []))
    if role == "director":
        toolkit = next((site / "nvidia/cu13" for site in sites if (site / "nvidia/cu13/bin/nvcc").is_file()), None)
        if toolkit:
            env["CUDA_HOME"] = str(toolkit)
            env["PATH"] = str(toolkit / "bin") + os.pathsep + env.get("PATH", "")
    if role == "media":
        env["EVOSPRIG_MEDIA_ATTENTION"] = "sdpa"
        env["EVOSPRIG_VOICE_LOAD_STRATEGY"] = config.get("voice_load_strategy", "auto")
        env["EVOSPRIG_IMAGE_LOAD_STRATEGY"] = config.get("image_load_strategy", "auto")
    return env


def download(args):
    # Set the endpoint before importing huggingface_hub.
    if args.mirror:
        os.environ["HF_ENDPOINT"] = args.mirror.rstrip("/")
    os.environ["HF_HOME"] = str(args.state / "cache/huggingface")
    from huggingface_hub import hf_hub_download, snapshot_download

    manifest = json.loads((APP / "models.json").read_text())
    args.model_dir.mkdir(parents=True, exist_ok=True)
    receipt = args.state / "downloads.json"
    completed = json.loads(receipt.read_text()) if receipt.exists() else {}
    for role, model in manifest["models"].items():
        target = args.model_dir / model["repo"]
        print("Downloading", role, model["repo"], flush=True)
        snapshot_download(repo_id=model["repo"], revision=model["revision"], local_dir=target,
                          max_workers=4, ignore_patterns=["assets/*", ".gitattributes"])
        completed[role] = {**model, "directory": str(target), "completed_at": time.time()}
        write(receipt, completed)
    for weight in manifest["render_weights"]:
        path = hf_hub_download(repo_id=weight["repo"], revision=weight["revision"],
                               filename=weight["file"], local_dir=args.model_dir / weight["repo"])
        verification = completed.get("verified_weights", {}).get(weight["file"], {})
        stamp = Path(path).stat().st_mtime_ns
        if verification != {"sha256": weight["sha256"], "mtime_ns": stamp, "size": weight["size"]}:
            verify_weight(path, weight)
            completed.setdefault("verified_weights", {})[weight["file"]] = {
                "sha256": weight["sha256"], "mtime_ns": stamp, "size": weight["size"],
            }
            write(receipt, completed)
        destination = args.state / "comfy-models" / weight["category"] / Path(weight["file"]).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.resolve() != Path(path).resolve():
            raise ValueError("a different model already occupies " + str(destination))
        if not destination.exists():
            destination.symlink_to(Path(path).resolve())
    completed["render_weights"] = {"count": len(manifest["render_weights"]), "completed_at": time.time()}
    write(receipt, completed)


def setup(args):
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = json.loads((APP / "models.json").read_text())
        comfy = args.state / "ComfyUI"
        for runtime in manifest["runtimes"].values():
            destination = comfy / runtime["path"]
            if not destination.exists():
                command(["git", "clone", "--no-checkout", runtime["url"], destination])
                command(["git", "-C", destination, "checkout", "--detach", runtime["revision"]])
            else:
                current = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
                if current != runtime["revision"]:
                    raise ValueError("existing runtime has another revision: " + str(destination))
        if not args.skip_install:
            npm = shutil.which("npm")
            node = shutil.which("node")
            if not npm or not node:
                raise RuntimeError("Install Node.js 20 or newer (including npm) to build the canvas editor, then rerun setup.")
            node_version = subprocess.check_output([node, "--version"], text=True).strip()
            if int(node_version.lstrip("v").split(".")[0]) < 20:
                raise RuntimeError("Episode Studio needs Node.js 20 or newer; found " + node_version)
            for name in ("episode-core", "episode-media", "episode-director", "episode-comfy"):
                path = args.env_root / name
                if not path.exists():
                    command([sys.executable, "-m", "venv", path])
            command([python(args.env_root, "episode-core"), "-m", "pip", "install", str(ROOT) + "[server,models,media]", "huggingface-hub>=0.34"])
            command([python(args.env_root, "episode-media"), "-m", "pip", "install", "torch==2.8.0", "torchvision==0.23.0",
                     "-r", ROOT / "apps/media-service/requirements-qwen.txt"])
            command([python(args.env_root, "episode-media"), "-m", "pip", "install", "-r", ROOT / "apps/media-service/requirements-speech.txt"])
            command([python(args.env_root, "episode-director"), "-m", "pip", "install", "vllm==0.33.0",
                     "nvidia-cuda-nvcc==13.0.88", "nvidia-nvvm==13.0.88", "nvidia-cuda-crt==13.0.88"])
            for runtime in manifest["runtimes"].values():
                requirements = comfy / runtime["path"] / "requirements.txt"
                if requirements.exists():
                    command([python(args.env_root, "episode-comfy"), "-m", "pip", "install", "-r", requirements])
            command([python(args.env_root, "episode-comfy"), "-m", "pip", "install", "imageio-ffmpeg==0.6.0"])
            command([npm, "ci"], cwd=ROOT / "apps/studio")
            command([npm, "run", "build"], cwd=ROOT / "apps/studio")
        command([python(args.env_root, "episode-core"), APP / "launch.py", "download", "--state", args.state,
                 "--model-dir", args.model_dir, *(["--mirror", args.mirror] if args.mirror else [])])
        model_paths = {role: str(args.model_dir / model["repo"]) for role, model in manifest["models"].items()}
        config = {"env_root": str(args.env_root), "state": str(args.state), "models": model_paths,
                  "recipe": str(args.recipe), "director_gpus": 4, "media_gpu": 4, "comfy_gpu": 5,
                  "context_length": 32768, "max_concurrent_requests": 4, "max_batched_tokens": 8192,
                  "idle_unload_seconds": 1800,
                  "model_timeout_seconds": 1200,
                  "voice_load_strategy": "auto",
                  "image_load_strategy": "auto",
                  "safetensors_load_strategy": "eager", "enforce_eager": False,
                  "image_steps": 40, "image_width": 1344, "image_height": 768,
                  "ports": {"director": 18882, "media": 18880, "comfy": 18884, "app": 18767}}
        config_path = args.state / "services.json"
        if config_path.exists():
            saved = json.loads(config_path.read_text())
            config = {**config, **saved, "models": {**model_paths, **saved.get("models", {})}}
        write(config_path, config)
        print("Ready. Start with: python apps/episode-studio/launch.py start --state", args.state)


def device_partition(config, visible):
    count = config["director_gpus"]
    if type(count) is not int or count < 1:
        raise ValueError("director_gpus must be a positive integer")
    slots = [*range(count), config["media_gpu"], config["comfy_gpu"]]
    if any(type(slot) is not int or slot < 0 or slot >= len(visible) for slot in slots):
        raise ValueError("not enough allocated GPUs for services.json")
    if len(set(slots)) != len(slots):
        raise ValueError("director, media and ComfyUI require disjoint GPU allocations")
    return {"director": ",".join(visible[:count]), "media": visible[config["media_gpu"]],
            "comfy": visible[config["comfy_gpu"]]}


def stop_services(processes, timeout=45):
    """Release every service group, including when a child exits during shutdown."""
    processes = list(reversed(list(processes)))
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + timeout
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def run_services(args):
    config = json.loads((args.state / "services.json").read_text())
    state = args.state
    ports = config["ports"]
    if len(set(ports.values())) != len(ports):
        raise ValueError("service ports must be distinct")
    for port in ports.values():
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible is None:
        visible = subprocess.check_output(["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"], text=True).replace("\n", ",").strip(",")
    devices = device_partition(config, visible.split(","))
    models, env_root = config["models"], config["env_root"]
    profile = state / "deployment.yaml"
    with tempfile.NamedTemporaryFile(dir=state, prefix="deployment-", suffix=".yaml") as temporary:
        pending = Path(temporary.name)
    try:
        command([python(env_root, "episode-core"), ROOT / "examples/episode-studio/configure.py", "--recipe", config["recipe"],
                 "--model-url", f"http://127.0.0.1:{ports['director']}/v1", "--media-url", f"http://127.0.0.1:{ports['media']}",
                 "--comfy-url", f"http://127.0.0.1:{ports['comfy']}",
                 "--model-timeout-seconds", str(config.get("model_timeout_seconds", 1200)), "--out", pending])
        pending.replace(profile)
    finally:
        pending.unlink(missing_ok=True)
    model_root = state / "comfy-models"
    manifest = json.loads((APP / "models.json").read_text())
    categories = sorted({weight["category"] for weight in manifest["render_weights"]})
    # JSON is also YAML; the supervisor itself needs only the Python stdlib.
    (state / "extra-model-paths.yaml").write_text(json.dumps({"episode": {"base_path": str(model_root),
        "is_default": True, **{name: name for name in categories}}}))
    commands = {
        "director": [python(env_root, "episode-director"), str(APP / "model_entry.py"), "--model", models["director"],
            "--served-model-name", "Qwen3.8-Flash-Next", "--host", "127.0.0.1", "--port", str(ports["director"]),
            "--tensor-parallel-size", str(config["director_gpus"]), "--enable-expert-parallel", "--moe-backend", "triton",
            "--engram-config", '{"cpu_offload":false}', "--max-model-len", str(config["context_length"]),
            "--max-num-batched-tokens", str(config.get("max_batched_tokens", 8192)),
            "--max-num-seqs", str(config["max_concurrent_requests"]), "--enable-prefix-caching", "--enable-auto-tool-choice",
            "--tool-call-parser", "qwen3_coder", "--reasoning-parser", "qwen3",
            *(["--enforce-eager"] if config.get("enforce_eager", False) else []),
            "--safetensors-load-strategy", config.get("safetensors_load_strategy", "eager"),
            "--limit-mm-per-prompt", '{"image":8,"video":0}'],
        "comfy": [python(env_root, "episode-comfy"), str(state / "ComfyUI/main.py"), "--listen", "127.0.0.1", "--port", str(ports["comfy"]),
            "--extra-model-paths-config", str(state / "extra-model-paths.yaml"), "--disable-auto-launch"],
        "media": [python(env_root, "episode-media"), str(ROOT / "apps/media-service/app.py"),
            "--image-backend", "qwen-image-2.1", "--image-model", models["image"], "--voice-model", models["voice"], "--preload", "voice",
            "--speech-model", models["speech"], "--image-steps", str(config.get("image_steps", 40)),
            "--width", str(config.get("image_width", 1344)), "--height", str(config.get("image_height", 768)),
            "--outputs", str(state / "media"), "--database", str(state / "media.sqlite"), "--port", str(ports["media"]),
            "--public-url", f"http://127.0.0.1:{ports['media']}", "--comfy-input", str(state / "ComfyUI/input"),
            "--comfy-output", str(state / "ComfyUI/output"), "--idle-unload-seconds", str(config["idle_unload_seconds"])],
        "app": [python(env_root, "episode-core"), str(APP / "app.py"), "--profile", str(profile),
            "--workspace", str(state / "workspace"), "--media-root", str(state / "media"), "--port", str(ports["app"])],
    }
    processes, logs = {}, []
    session = {"pid": os.getpid(), "started": time.time(), "services": {}}
    stop = state / "stop"
    stop.unlink(missing_ok=True)
    def terminate(signum, frame):
        stop.touch()
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)
    try:
        for role, argv in commands.items():
            log = (state / (role + ".log")).open("a")
            logs.append(log)
            env = service_environment(config, role, state)
            if role == "comfy":
                ffmpeg = subprocess.check_output([python(env_root, "episode-comfy"), "-c",
                    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"], text=True, env=env).strip()
                env.update(IMAGEIO_FFMPEG_EXE=ffmpeg, VHS_FORCE_FFMPEG_PATH=ffmpeg)
            if role in devices:
                env["CUDA_VISIBLE_DEVICES"] = devices[role]
            process = subprocess.Popen(argv, env=env, stdout=log, stderr=log, start_new_session=True)
            processes[role] = process
            session["services"][role] = {"pid": process.pid, "state": "starting", "port": ports[role]}
        write(state / "session.json", session)
        print(f"Episode Studio: http://127.0.0.1:{ports['app']}/episode/", flush=True)
        print("Models stay loaded for this session. Ctrl+C or the stop command releases all services.", flush=True)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while not stop.exists():
            for role, process in processes.items():
                if process.poll() is not None:
                    raise RuntimeError(role + " exited; inspect " + str(state / (role + ".log")))
                if session["services"][role]["state"] == "starting":
                    endpoint = "/system_stats" if role == "comfy" else "/api/health" if role == "app" else "/health"
                    try:
                        with opener.open(f"http://127.0.0.1:{ports[role]}{endpoint}", timeout=1):
                            session["services"][role]["state"] = "ready"
                            write(state / "session.json", session)
                    except OSError:
                        pass
            if time.time() - session["started"] > 5400 and any(x["state"] == "starting" for x in session["services"].values()):
                raise TimeoutError("a service did not start within 90 minutes; inspect its log")
            time.sleep(2)
    finally:
        stop_services(processes.values())
        for log in logs:
            log.close()
        session["stopped"] = time.time()
        for role, process in processes.items():
            session["services"][role].update(state="stopped", exit_code=process.returncode)
        write(state / "session.json", session)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "download", "start", "stop", "status"])
    parser.add_argument("--state", type=Path, default=Path(".evosprig/episode"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--env-root", type=Path, default=Path(".venvs"))
    parser.add_argument("--recipe", type=Path, default=APP / "render-recipe.json")
    parser.add_argument("--mirror", help="Hugging Face-compatible endpoint, e.g. https://hf-mirror.com")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    args.state, args.model_dir, args.env_root = (p.resolve() for p in (args.state, args.model_dir, args.env_root))
    if args.action == "setup" and sys.version_info < (3, 12):
        parser.error("Run setup with Python 3.12 or newer.")
    if args.action in {"start", "stop", "status"} and not (args.state / "services.json").is_file():
        parser.error("Run setup first, or use --state to select an existing installation.")
    if args.action == "setup":
        if not args.recipe.is_file():
            parser.error("render recipe file does not exist")
        args.recipe = args.recipe.resolve()
        setup(args)
    elif args.action == "download":
        args.state.mkdir(parents=True, exist_ok=True)
        with (args.state / "download.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            download(args)
    elif args.action == "start":
        with (args.state / "session.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run_services(args)
    elif args.action == "stop":
        (args.state / "stop").touch()
    else:
        session = args.state / "session.json"
        print(session.read_text() if session.exists() else json.dumps({"state": "not_started"}))


if __name__ == "__main__":
    main()

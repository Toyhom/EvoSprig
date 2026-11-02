"""Deterministic original graphics. No downloaded visual/audio assets."""

import hashlib
import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont


def render(storyboard, output: Path, canceled):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".partial.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "640x360",
        "-r",
        "12",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    font, small = ImageFont.load_default(size=24), ImageFont.load_default(size=17)
    colors = {
        "dawn": ("#181b35", "#ffc982"),
        "day": ("#102c31", "#a8eed1"),
        "night": ("#131e35", "#c6bcff"),
    }
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for index, shot in enumerate(storyboard["shots"]):
            background, accent = colors[shot["palette"]]
            for frame in range(72):
                if canceled.is_set():
                    raise InterruptedError("render canceled")
                t = frame / 71
                image = Image.new("RGB", (640, 360), background)
                draw = ImageDraw.Draw(image)
                for n in range(16):
                    x = (n * 113 + 45) % 640
                    y = 50 + (n * 37) % 180 + math.sin(t * math.pi + n) * 5
                    draw.ellipse((x, y, x + 2, y + 2), fill=accent)
                draw.line((70, 275, 570, 275), fill=accent, width=2)
                stage = shot["stage"]
                height = 0 if stage == "seed" else 55 if stage == "sprout" else 100
                height += (8 if stage == "seed" else 20) * t
                draw.ellipse((308, 264, 332, 281), fill="#d1a56d")
                if height > 10:
                    top = 270 - height
                    draw.line((320, 270, 320, top), fill="#78d6aa", width=5)
                    draw.ellipse((283, top + 12, 320, top + 33), fill="#78d6aa")
                    draw.ellipse((320, top + 28, 359, top + 50), fill="#51ac91")
                    if stage == "bloom":
                        for petal in range(6):
                            angle = petal * math.pi / 3 + t * 0.3
                            x, y = 320 + math.cos(angle) * 18, top + math.sin(angle) * 18
                            draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill=accent)
                        draw.ellipse((310, top - 10, 330, top + 10), fill="#e3b35a")
                draw.text((32, 25), storyboard["title"], font=font, fill=accent)
                draw.text((32, 310), shot["caption"], font=small, fill="#eeeeef")
                draw.text((575, 28), f"{index + 1}/3", font=small, fill=accent)
                process.stdin.write(image.tobytes())
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=30):
            raise RuntimeError("ffmpeg failed: " + error.decode(errors="replace")[:300])
        output.write_bytes(temporary.read_bytes())  # Sequential object-store-safe publication.
        temporary.unlink()
        return hashlib.sha256(output.read_bytes()).hexdigest()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if temporary.exists():
            temporary.unlink()

"""Explicit image inputs for chat models, without implicit file or network access."""

import base64
import copy
from urllib.parse import urlsplit

from .protocols import ExecutionError
from .spec import canonical_json


def image_uri(value):
    if isinstance(value, dict):
        value = value.get("uri")
    if not isinstance(value, str):
        raise ExecutionError("image inputs must contain image URIs or asset objects")
    if value.startswith("data:"):
        try:
            header, data = value.split(",", 1)
            if header not in {
                "data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"
            } or len(data) > 12 * 1024 * 1024:
                raise ValueError()
            if not base64.b64decode(data, validate=True):
                raise ValueError()
        except (ValueError, TypeError):
            raise ExecutionError("invalid or oversized image data URI") from None
    else:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment):
            raise ExecutionError("images require base64 data or an HTTPS URI")
    return value


def user_content(arguments, image_inputs):
    if not image_inputs:
        return canonical_json(arguments)
    text = copy.deepcopy(arguments)
    images = []
    for name in image_inputs:
        values = arguments[name]
        values = values if isinstance(values, list) else [values]
        labels = []
        for value in values:
            images.append({"type": "image_url", "image_url": {"url": image_uri(value)}})
            labels.append(f"Image {len(images)}")
        text[name] = labels
    if not images or len(images) > 16:
        raise ExecutionError("a model message requires between 1 and 16 images")
    if sum(len(part["image_url"]["url"]) for part in images) > 20 * 1024 * 1024:
        raise ExecutionError("combined image input exceeds 20 MiB")
    return [{"type": "text", "text": canonical_json(text)}, *images]


def input_reservation(messages, tools, image_tokens=4096):
    """Reserve text bytes plus image allowance; reconcile with provider usage."""
    sanitized = copy.deepcopy(messages)
    images = 0
    for message in sanitized:
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    part["image_url"] = {"url": "<image>"}
                    images += 1
    return len(canonical_json({"messages": sanitized, "tools": tools}).encode()) + 128 + images * image_tokens

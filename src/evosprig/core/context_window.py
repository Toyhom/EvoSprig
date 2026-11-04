"""Bound observations sent to a model; full tool results stay in the journal."""

import hashlib
import json

from .spec import canonical_json


def tool_observation(value, max_chars=None):
    text = canonical_json(value)
    if max_chars is None or len(text) <= max_chars:
        return text
    wrapper = {"truncated": True, "original_chars": len(text),
               "sha256": hashlib.sha256(text.encode()).hexdigest(),
               "preview": "", "hint": "Request a narrower result to read the omitted content."}
    # Budget the encoded wrapper, including escaped characters in the preview.
    low, high = 0, len(text)
    while low < high:
        size = (low + high + 1) // 2
        head = size * 3 // 4
        wrapper["preview"] = text[:head] + "\n…\n" + text[-(size-head):] if size else ""
        if len(canonical_json(wrapper)) <= max_chars:
            low = size
        else:
            high = size - 1
    head = low * 3 // 4
    wrapper["preview"] = text[:head] + "\n…\n" + text[-(low-head):] if low else ""
    return json.dumps(wrapper, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

"""Bound observations sent to a model; full tool results stay in the journal."""

import copy
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


def project_tool_history(messages, policy):
    """Prune older observations in the request, preserving call/result pairing and logs.

    Recent rounds and instruction/user messages are kept intact. The character cap
    applies to tool observations; protected messages can exceed it.
    """
    if policy is None:
        return messages, None
    rounds, current = [], []
    for index, message in enumerate(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            current = []
            rounds.append(current)
        if message.get("role") == "tool" and isinstance(message.get("content"), str):
            if not rounds:
                rounds.append(current)
            current.append(index)
    all_indices = [index for group in rounds for index in group]
    before = sum(len(messages[index]["content"]) for index in all_indices)
    total = before
    eligible = rounds[:-policy.keep_recent_rounds] if policy.keep_recent_rounds else rounds
    projected = list(messages)
    changed = 0
    for index in (i for group in eligible for i in group):
        if total <= policy.max_chars:
            break
        content = messages[index]["content"]
        limit = max(512, len(content) - (total - policy.max_chars))
        if len(content) <= limit:
            continue
        compact = tool_observation(content, limit)
        projected[index] = {**copy.deepcopy(messages[index]), "content": compact}
        total -= len(content) - len(compact)
        changed += 1
    return projected, {"before_chars": before, "after_chars": total, "pruned_results": changed,
                       "cap_satisfied": total <= policy.max_chars}

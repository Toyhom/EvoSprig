"""Discover relevant procedures in a versioned task-stream skill library."""

import json
import re


def skill_content(text, query, limit=5):
    try:
        library = json.loads(text)
    except ValueError:
        return text
    if not isinstance(library, dict) or library.get("evosprig_skill_library") != 1:
        return text
    tokens = set(re.findall(r"\w+", query.lower()))
    entries = library.get("entries", [])
    ranked = sorted(
        entries,
        key=lambda e: (
            len(tokens & set(re.findall(r"\w+", e["trigger"].lower()))),
            e["level"] == "general",
        ),
        reverse=True,
    )
    selected = [
        e
        for e in ranked
        if e["level"] == "general" or tokens & set(re.findall(r"\w+", e["trigger"].lower()))
    ][:limit]
    return (
        library.get("base", "")
        + "\n"
        + "\n\n".join(f"### {e['id']}\nWhen: {e['trigger']}\n{e['body']}" for e in selected)
    )

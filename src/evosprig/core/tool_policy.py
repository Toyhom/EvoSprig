"""Deterministic, training-free tool discovery inside an explicit allowlist."""

import math
import re
from collections import Counter


def select_tools(aliases, tools, query, limit):
    def terms(text):
        return set(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", text.casefold()))

    words = terms(query)
    descriptions = [terms(alias + " " + tools[alias].description) for alias in aliases]
    frequency = Counter(term for description in descriptions for term in description)
    scores = [
        sum(math.log(1 + len(aliases) / frequency[word]) for word in words & description)
        for description in descriptions
    ]
    return [aliases[i] for i in sorted(range(len(aliases)), key=lambda i: (-scores[i], i))[:limit]]

def run(inputs):
    request = inputs["request"]
    return {
        "source": request["source"],
        "audience": request.get("audience", "对这个话题有兴趣、愿意了解实际用途的读者"),
        "voice": request.get("voice", "observer"),
        "emoji": request.get("emoji", "light"),
        "goal": request.get("goal", "用一个具体切入点，让读者知道这件事对自己有什么用"),
        "required_terms": request.get("required_terms", []),
        "links": request.get("links", []),
        "references": request.get("references", []),
        "max_title_chars": request.get("max_title_chars", 24),
        "max_body_chars": request.get("max_body_chars", 650)
    }

def run(inputs):
    post = inputs["post"]
    request = inputs["request"]
    text = post["title"] + "\n" + post["body"]
    issues = []
    if len(post["title"]) > request["max_title_chars"]:
        issues = issues + ["标题超长：" + str(len(post["title"])) + " 字符，上限 " + str(request["max_title_chars"])]
    if len(post["body"]) > request["max_body_chars"]:
        issues = issues + ["正文超长：" + str(len(post["body"])) + " 字符，上限 " + str(request["max_body_chars"])]
    for term in request["required_terms"]:
        if term not in text:
            issues = issues + ["标题或正文缺少必留信息：" + term]
    for tag in post["tags"]:
        if "#" in tag or " " in tag or "\n" in tag or len(tag) > 24:
            issues = issues + ["话题标签只保留短名称，不带井号、空格或换行"]
    if "http://" in text or "https://" in text:
        issues = issues + ["链接由发布格式节点追加，请移除正文和标题内的网址"]
    for phrase in ["赋能", "闭环", "重塑", "颠覆", "家人们谁懂啊", "建议收藏", "不允许你还不知道", "这不是", "而是"]:
        if phrase in text and phrase not in request["source"]:
            issues = issues + ["换成具体表达：" + phrase]
    return {"passed": len(issues) == 0, "issues": issues,
            "title_chars": len(post["title"]), "body_chars": len(post["body"])}

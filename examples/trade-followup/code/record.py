def run(inputs):
    draft = inputs["draft"]
    status = "approved draft" if inputs["approval"]["approved"] else "needs revision"
    content = inputs["history"]["content"] + "\nThread: " + inputs["request"]["thread_id"] + "\nStatus: " + status + "\nSubject: " + draft["subject"] + "\n" + draft["body"] + "\nReview: " + inputs["approval"]["note"] + "\n"
    return {"content": content[-50000:]}

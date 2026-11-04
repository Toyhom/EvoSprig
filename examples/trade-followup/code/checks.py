def run(inputs):
    request = inputs["request"]
    history = inputs["history"]["content"]
    marker = "Thread: " + request["thread_id"] + "\n"
    return {"previous_drafts": history[-12000:], "duplicate_thread": marker in history,
            "customer_id": request["customer_id"], "delivery": "draft"}

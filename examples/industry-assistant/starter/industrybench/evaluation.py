"""Replay operations against a fresh record and apply fixed business rules."""

from .session import Session


def evaluate(predictions, industry, ids):
    scores = []
    for prediction in predictions:
        if prediction["case_id"] not in ids or industry != "government":
            raise ValueError("Case outside the selected environment")
        session = Session(prediction["case_id"])
        read_back = False
        for call in prediction["calls"]:
            response = session.call(call["tool"], call["arguments"], call["idempotency_key"])
            if call["tool"] == "application.decide" and response.get("ok"):
                read_back = False
            if call["tool"] == "application.read" and response.get("decision"):
                read_back = True
        case = session.case
        expected = ("manual_review" if case["conflicting_records"] else
                    "request_documents" if not case["documents_complete"] else
                    "approve" if case["resident"] and case["income"] <= 25000 else "deny")
        scores.append(float(session.state["decision"] == expected and read_back))
    return {"summary": {"task_success_rate": sum(scores) / len(scores) if scores else 0}}

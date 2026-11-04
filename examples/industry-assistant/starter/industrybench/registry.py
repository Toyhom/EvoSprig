"""Small, fixed municipal training-grant cases for the application quickstart."""

CASES = [
    {"id": f"grant-{index + 1}", "resident": resident, "income": income,
     "documents_complete": complete, "conflicting_records": conflict}
    for index, (resident, income, complete, conflict) in enumerate([
        (True, 18000, True, False), (True, 35000, True, False),
        (False, 12000, True, False), (True, 15000, False, False),
        (True, 16000, True, True), (True, 25000, True, False),
        (True, 28000, False, False), (False, 9000, True, True),
    ])
]


def case_id(case):
    return case["id"]


def select(industry, ids=None, limit=12):
    if industry != "government":
        raise ValueError("The included sandbox supports government; connect your own other domains")
    return [(industry, dict(case)) for case in CASES if not ids or case["id"] in ids][:limit]


def sop(industry, case):
    return ("Read the application before deciding. Conflicting records require manual_review. "
            "Otherwise incomplete documents require request_documents. With complete, consistent "
            "records, approve residents with annual income at most 25000; deny other applications. "
            "Record the decision and a nonempty reason, then read it back to verify the saved state.")

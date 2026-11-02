"""Build practical workflows with EvoSprig; no application-specific agent runner."""

import json
from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder

ROOT = Path(__file__).parent
TEXT = {"type": "string"}


def obj(**fields):
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def ref(path):
    return {"ref": path}


def start(name, inputs):
    return (
        Builder(name, inputs, obj(text=TEXT), spec_version="0.3")
        .model("main", "main", ["text", "tool_calling", "structured_output"])
        .execution(
            max_steps=80,
            max_model_calls=24,
            max_parallel_nodes=3,
            max_total_tokens=70000,
            max_output_tokens=2500,
            timeout_seconds=300,
        )
    )


def writer(b, name, inputs, skills, *, tools=None, schema=None):
    b.resource(name, f"prompts/{name}.md")
    b.node(
        name,
        "agent" if tools else "model",
        model="main",
        instructions={"resource": name},
        inputs=inputs,
        skills=skills,
        tools=tools or [],
        output_schema=schema or obj(text=TEXT),
        response_format="json" if schema else "text",
        output_errors="feedback",
        tool_errors="feedback" if tools else "raise",
        max_output_retries=2,
        temperature=0.3,
        **({"max_tool_rounds": 3} if tools else {}),
    )


def save(b, prompts, skills, sample, groups=None):
    folder = ROOT / b.data["id"]
    for sub, values in [("prompts", prompts), ("skills", skills)]:
        (folder / sub).mkdir(parents=True, exist_ok=True)
        for name, text in values.items():
            (folder / sub / f"{name}.md").write_text(text.strip() + "\n")
    save_spec(b.build_spec(), folder / "agent.yaml")
    (folder / "sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n")
    (folder / "studio.json").write_text(
        json.dumps({"canvas": {"groups": groups or {}}, "layout": {}}, indent=2) + "\n"
    )


def career_coach():
    b = start("career-coach", obj(resume=TEXT, job=TEXT))
    skills = {
        "factual_writing": "Use only supplied experience, dates, employers and measurements. Preserve the candidate's scope of responsibility. Mark missing facts as questions. Never invent qualifications, metrics or employment history.",
        "interview_coaching": "Ask job-specific questions. In feedback, separate what the answer already demonstrates from what needs a concrete example. Suggest a STAR structure using only the candidate's facts; do not supply imaginary achievements.",
    }
    for name in skills:
        b.skill(name, f"skills/{name}.md")
    writer(
        b,
        "fit_review",
        {"resume": ref("input.resume"), "job": ref("input.job")},
        ["factual_writing"],
    )
    writer(
        b,
        "resume_draft",
        {
            "resume": ref("input.resume"),
            "job": ref("input.job"),
            "review": ref("nodes.fit_review.output.text"),
        },
        ["factual_writing"],
    )
    writer(
        b,
        "interview",
        {
            "resume": ref("input.resume"),
            "job": ref("input.job"),
            "review": ref("nodes.fit_review.output.text"),
        },
        ["interview_coaching"],
    )
    b.node(
        "practice",
        "human",
        inputs={
            "questions": ref("nodes.interview.output.text"),
            "resume_draft": ref("nodes.resume_draft.output.text"),
        },
        output_schema=obj(answer=TEXT),
    )
    writer(
        b,
        "coach",
        {
            "answer": ref("nodes.practice.output.answer"),
            "questions": ref("nodes.interview.output.text"),
            "draft": ref("nodes.resume_draft.output.text"),
            "resume": ref("input.resume"),
        },
        ["factual_writing", "interview_coaching"],
    )
    for source, target in [
        ("fit_review", "resume_draft"),
        ("fit_review", "interview"),
        ("resume_draft", "practice"),
        ("interview", "practice"),
        ("practice", "coach"),
    ]:
        b.edge(source, target)
    b.output(text=ref("nodes.coach.output.text"))
    save(
        b,
        {
            "fit_review": "Compare the resume with the job. Return a requirement-to-experience table, missing details to ask about, and three priorities for the application. Do not assign a hiring verdict.",
            "resume_draft": "Write a tailored professional summary and up to four resume bullets. Use the review to select relevant experience. Keep unsupported requirements in a separate questions list.",
            "interview": "Prepare three specific interview questions and the facts each question would help clarify. Put the most useful question first for the candidate to practice.",
            "coach": "Give feedback on the candidate's practice answer, then provide the tailored summary and bullets and a short practice plan. Identify missing detail without manufacturing it. Keep the full handoff under 650 words.",
        },
        skills,
        {
            "resume": "Maya: operations analyst, 2023-present. Built SQL reports on shipment delays and a Python CSV cleaning script. Worked with 4 warehouse coordinators. Weekly reporting changed from 3 hours to 45 minutes. No production ML experience.",
            "job": "Operations analytics role: SQL, Python, explain delays to warehouse teams, own weekly reporting. Machine learning is optional. Prepare an application and practice one interview answer.",
        },
        {
            "graph": [
                {
                    "id": "group:application",
                    "label": "Application materials",
                    "members": ["resume_draft", "interview"],
                    "collapsed": False,
                    "direction": "DOWN",
                }
            ]
        },
    )


def content_studio():
    b = start(
        "content-studio",
        obj(
            source=TEXT,
            audience=TEXT,
            channels={"type": "array", "items": TEXT, "minItems": 1, "maxItems": 6},
        ),
    )
    skills = {
        "brand_voice": "Write in plain, direct language for the stated audience. Lead with the most useful information, such as what is happening, when, and who it affects. Use concrete verbs and specific nouns instead of vague or promotional wording. Avoid slogans, inflated benefits, hype, and generic closing summaries. Match tone and format to each named channel, and keep the message focused on what the audience needs to know or do.",
        "source_fidelity": "Base every factual claim, including product features, prices, dates, times, locations, eligibility, and conditions, strictly on the supplied source. Keep qualifiers, limits, and dates attached to the claims they modify. Do not invent statistics, customer quotes, testimonials, results, or URLs. If the source says something is unavailable or not yet supplied, do not fabricate it; omit it or note that it is pending.",
    }
    for name in skills:
        b.skill(name, f"skills/{name}.md")
    writer(
        b,
        "brief",
        {"source": ref("input.source"), "audience": ref("input.audience")},
        ["source_fidelity"],
    )
    b.resource("adapt", "prompts/adapt.md")
    body = {
        "entry": "write",
        "nodes": {
            "write": {
                "type": "model",
                "model": "main",
                "instructions": {"resource": "adapt"},
                "skills": ["brand_voice", "source_fidelity"],
                "inputs": {
                    "channel": ref("input.item"),
                    "brief": ref("input.context.brief"),
                    "source": ref("input.context.source"),
                },
                "output_schema": obj(text=TEXT),
                "temperature": 0.5,
            }
        },
        "edges": [],
        "output": {"channel": ref("input.item"), "text": ref("nodes.write.output.text")},
    }
    b.map(
        "channels",
        items=ref("input.channels"),
        body=body,
        inputs={"brief": ref("nodes.brief.output.text"), "source": ref("input.source")},
        output_schema=obj(items={"type": "array"}),
        max_items=6,
    )
    writer(
        b,
        "editor",
        {"drafts": ref("nodes.channels.output.items"), "source": ref("input.source")},
        ["brand_voice", "source_fidelity"],
    )
    b.edge("brief", "channels").edge("channels", "editor").output(
        text=ref("nodes.editor.output.text")
    )
    save(
        b,
        {
            "brief": "Extract the facts, intended reader, useful message and any restrictions for a small content campaign. Flag missing dates, URLs and availability.",
            "adapt": "Adapt the brief for the requested channel. Email: subject and concise body; social: a short post; blog: headline and up to 300 words. Use the supplied source. Return the copy ready for editing.",
            "editor": "Review all channel drafts against the source. Fix unsupported claims and inconsistencies, then return the final copy under separate channel headings. Add at most three factual questions that remain before publication.",
        },
        skills,
        {
            "audience": "Local visitors",
            "channels": ["Social post", "Email newsletter"],
            "source": "North Museum has a late opening on April 2, 2027 until 8pm. Standard tickets $12; students $7 with ID. The archive room remains closed. The cafe closes at 6pm. Tickets can be purchased at the front desk only.",
        },
    )


def study_coach():
    b = start("study-coach", obj(topic=TEXT, level=TEXT, material=TEXT))
    skills = {
        "teaching": "Use the supplied material to teach the topic. Explain with a worked example, then ask questions requiring the learner to apply it. Keep the answer key out of the exercise. Match vocabulary to the learner's level.",
        "coaching_feedback": "Assess each submitted answer against the question and source. Identify the exact misunderstanding, show one corrected example and give one follow-up practice task. Acknowledge correct reasoning. Do not infer ability from missing answers.",
    }
    for name in skills:
        b.skill(name, f"skills/{name}.md")
    b.tool("recall", "memory.search")
    writer(
        b,
        "lesson",
        {
            "topic": ref("input.topic"),
            "level": ref("input.level"),
            "material": ref("input.material"),
        },
        ["teaching"],
        tools=["recall"],
    )
    writer(
        b,
        "quiz",
        {"lesson": ref("nodes.lesson.output.text"), "material": ref("input.material")},
        ["teaching"],
        schema=obj(questions={"type": "array", "items": TEXT, "minItems": 3, "maxItems": 3}),
    )
    b.node(
        "learner",
        "human",
        inputs={
            "lesson": ref("nodes.lesson.output.text"),
            "questions": ref("nodes.quiz.output.questions"),
        },
        output_schema=obj(answers={"type": "array", "items": TEXT, "minItems": 3, "maxItems": 3}),
    )
    writer(
        b,
        "feedback",
        {
            "questions": ref("nodes.quiz.output.questions"),
            "answers": ref("nodes.learner.output.answers"),
            "material": ref("input.material"),
        },
        ["coaching_feedback"],
    )
    b.edge("lesson", "quiz").edge("quiz", "learner").edge("learner", "feedback").output(
        text=ref("nodes.feedback.output.text")
    )
    save(
        b,
        {
            "lesson": "Look up relevant prior learning preferences if available. Teach the requested topic using the supplied material in under 300 words. Do not assume missing prior knowledge.",
            "quiz": "Create exactly three short application questions about this lesson. Return only a questions array; no solutions or hints that give away the answers.",
            "feedback": "Return question-by-question feedback and a short practice plan using the learner's actual answers. Keep the response under 500 words.",
        },
        skills,
        {
            "topic": "Python list aliasing and shallow copies",
            "level": "Beginner who knows lists and assignment",
            "material": "Assignment b = a binds another name to the same list. b = a.copy() creates a shallow copy: the outer list is new but nested objects remain shared. copy.deepcopy(a) recursively copies nested objects. Mutating a shared nested list is visible through both outer lists.",
        },
    )


if __name__ == "__main__":
    career_coach()
    content_studio()
    study_coach()

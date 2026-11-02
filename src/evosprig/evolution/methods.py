"""Implemented training-free resource optimizers and their feedback requirements."""

from typing import Literal

Method = Literal[
    "opro",
    "gepa",
    "evoprompt_ga",
    "evoprompt_de",
    "self_refine",
    "ace",
    "ape",
    "protesgi",
    "bootstrap_fewshot",
    "fewshot_search",
    "promptbreeder",
    "reflexion",
    "expel",
]

METHODS = {
    "opro": {
        "name": "OPRO",
        "family": "score history",
        "feedback": "scalar scores",
        "source": "https://arxiv.org/abs/2309.03409",
    },
    "gepa": {
        "name": "GEPA",
        "family": "Pareto reflection",
        "feedback": "scores and trajectories",
        "source": "https://github.com/gepa-ai/gepa",
    },
    "evoprompt_ga": {
        "name": "EvoPrompt GA",
        "family": "population search",
        "feedback": "scalar scores",
        "source": "https://arxiv.org/abs/2309.08532",
    },
    "evoprompt_de": {
        "name": "EvoPrompt DE",
        "family": "population search",
        "feedback": "scalar scores",
        "source": "https://arxiv.org/abs/2309.08532",
    },
    "self_refine": {
        "name": "Self-Refine",
        "family": "critique and revision",
        "feedback": "written critique and scores",
        "source": "https://arxiv.org/abs/2303.17651",
    },
    "ace": {
        "name": "ACE",
        "family": "incremental playbook",
        "feedback": "trajectories and scores",
        "source": "https://arxiv.org/abs/2510.04618",
    },
    "ape": {
        "name": "APE",
        "family": "instruction induction",
        "feedback": "examples and scalar scores",
        "source": "https://github.com/keirp/automatic_prompt_engineer",
    },
    "protesgi": {
        "name": "ProTeGi-style beam",
        "family": "textual gradients",
        "feedback": "minibatch failures and scores",
        "source": "https://github.com/microsoft/LMOps/tree/main/prompt_optimization",
    },
    "bootstrap_fewshot": {
        "name": "Bootstrap few-shot",
        "family": "demonstration selection",
        "feedback": "scored successful executions",
        "source": "https://github.com/stanfordnlp/dspy",
    },
    "fewshot_search": {
        "name": "Few-shot random search",
        "family": "demonstration selection",
        "feedback": "scored successful executions",
        "source": "https://github.com/stanfordnlp/dspy",
    },
    "promptbreeder": {
        "name": "PromptBreeder-style",
        "family": "task/mutator coevolution",
        "feedback": "population fitness",
        "source": "https://arxiv.org/abs/2309.16797",
    },
    "reflexion": {
        "name": "Reflexion memory",
        "family": "episodic reflection",
        "feedback": "environment feedback and trajectories",
        "source": "https://github.com/noahshinn/reflexion",
    },
    "expel": {
        "name": "ExpeL insights",
        "family": "experience induction",
        "feedback": "successful and failed trajectories",
        "source": "https://github.com/LeapLabTHU/ExpeL",
    },
}

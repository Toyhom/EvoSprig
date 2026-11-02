"""Create the business agent with EvoSprig's shared industry workflow builder."""
from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.industry_cli import industry_agent

if __name__ == "__main__":
    save_spec(industry_agent(), Path(__file__).with_name("agent.yaml"))

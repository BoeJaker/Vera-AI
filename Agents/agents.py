"""
    agents.py
    This module provides functionality to dynamically build and configure AI agents 
    based on a specified configuration file and template. It generates a system 
    prompt using Jinja2 templates, writes a Modelfile for the agent, and builds the 
    agent using the `ollama` command-line tool.
    Functions:
    -----------
    - build_agent(agent_name: str, config_path: str, output_path: str) -> None:
        Constructs an agent by reading its configuration, rendering a system prompt 
        template, and creating a Modelfile. It then invokes the `ollama` tool to 
        build the agent.
    Usage:
    ------
    The script can be executed directly to build multiple agents defined in the 
    `agents` dictionary. Each agent is associated with a configuration file and 
    output path for the Modelfile.
    Dependencies:
    -------------
    - subprocess: For running external commands.
    - jinja2.Template: For rendering system prompt templates.
    - yaml: For parsing YAML configuration files.
    - os: For interacting with the file system.
    Constants:
    ----------
    - BASE_MODEL: The base model used for building agents.
    - CTX: The context size parameter for the model.
    - GPU_LAYERS: The number of GPU layers parameter for the model.
"""

import subprocess
from jinja2 import Template
import yaml
import os

BASE_MODEL = "llama3"
CTX = 65536
GPU_LAYERS = 999

def build_agent(agent_name, config_path, output_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Build system prompt dynamically
    template_path = f"agents/{agent_name}/prompt_template.j2"
    with open(template_path) as f:
        t = Template(f.read())

    system_prompt = t.render(cfg)

    # Write Modelfile
    modelfile = f"""
FROM {BASE_MODEL}

PARAMETER num_ctx {CTX}
PARAMETER gpu_layers {GPU_LAYERS}

SYSTEM \"\"\"
{system_prompt}
\"\"\"
"""
    with open(output_path, "w") as f:
        f.write(modelfile)

    # Build model
    subprocess.run(["ollama", "create", agent_name, "-f", output_path], check=True)

if __name__ == "__main__":
    agents = {
        "tool": "config/tool_agent.yaml",
        "triage": "config/triage_agent.yaml",
        "fast": "config/fast_agent.yaml"
    }

    for agent, cfg in agents.items():
        out = f"agents/{agent}/Modelfile"
        build_agent(agent, cfg, out)

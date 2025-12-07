#!/usr/bin/env python3
import os, yaml, subprocess, textwrap
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(__file__)) if os.path.basename(os.getcwd())=="scripts" else os.getcwd()
AGENTS_DIR = os.path.join(ROOT, "agents")
TEMPLATES_DIR = os.path.join(ROOT, "templates")
BUILD_DIR = os.path.join(ROOT, "build")
os.makedirs(BUILD_DIR, exist_ok=True)

env = Environment(loader=FileSystemLoader(ROOT))
# helper for includes - resolves relative to current agent dir
current_agent_path = None
def include_file(path):
    full = os.path.join(current_agent_path, path)
    with open(full, "r", encoding="utf-8") as f:
        return f.read()
env.globals["include_file"] = include_file

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def render_system_prompt(agent_name, cfg):
    global current_agent_path
    current_agent_path = os.path.join(AGENTS_DIR, agent_name)
    tmpl_name = f"agents/{agent_name}/{cfg['system_prompt']['template']}"
    template = env.get_template(tmpl_name)
    return template.render(**cfg['system_prompt']['variables'])

def build_modelfile(agent_name, cfg, system_prompt):
    model_template = env.get_template("templates/Modelfile.j2")
    rendered = model_template.render(
        base_model=cfg['base_model'],
        parameters=cfg['parameters'],
        num_ctx=cfg['num_ctx'],
        gpu_layers=cfg['gpu_layers'],
        system_prompt=system_prompt
    )
    out = os.path.join(BUILD_DIR, f"{agent_name}.Modelfile")
    with open(out, "w", encoding="utf-8") as f:
        f.write(rendered)
    return out

def ollama_create(agent_name, modelfile_path):
    print(f"[BUILD] ollama create {agent_name} -f {modelfile_path}")
    subprocess.run(["ollama", "create", agent_name, "-f", modelfile_path], check=True)

def build_agent(agent_name):
    cfg_path = os.path.join(AGENTS_DIR, agent_name, "agent.yaml")
    cfg = load_yaml(cfg_path)
    system_prompt = render_system_prompt(agent_name, cfg)
    # optional: warn if system_prompt very big
    size_kb = len(system_prompt) / 1024
    if size_kb > 512:
        print(f"[WARN] Prompt for {agent_name} is {size_kb:.1f}KB; ensure num_ctx is large enough")
    modelfile = build_modelfile(agent_name, cfg, system_prompt)
    ollama_create(cfg['name'], modelfile)

def main():
    for agent in sorted(os.listdir(AGENTS_DIR)):
        full = os.path.join(AGENTS_DIR, agent)
        if os.path.isdir(full):
            print(f"[INFO] Building agent: {agent}")
            build_agent(agent)
    print("[OK] All agents built.")

if __name__ == "__main__":
    main()

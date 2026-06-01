"""Flask web interface for BUGHUNTER-AI."""
from __future__ import annotations
import os
import pathlib
from flask import Flask, render_template, request, jsonify

from slm.agent import Agent
from slm.llm import LlamaClient
from slm.init import first_run

app = Flask(__name__, 
            template_folder='web/templates',
            static_folder='web/static')

# Initialize if needed
first_run()

def _make_agent(yolo=False):
    import tomllib
    slm_home = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
    cfg = tomllib.loads((slm_home / "config.toml").read_text())
    
    # Simple tier-based model selection
    tier = cfg.get("model", {}).get("tier", "mobile")
    if tier == "auto": tier = "mobile" # Default for web chat on unknown
    
    m_cfg = cfg.get("model", {}).get(tier, {})
    llm = LlamaClient(
        model_path=m_cfg.get("path"),
        n_ctx=m_cfg.get("n_ctx", 2048),
        flash_attn=m_cfg.get("flash_attn", True)
    )
    
    sys_prompt = (slm_home / "system.md").read_text()
    return Agent(llm, sys_prompt, yolo=yolo, tier=tier)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message', '')
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        agent = _make_agent(yolo=False)
        events = []
        for ev in agent.run(user_msg):
            events.append({
                "kind": ev.kind,
                "content": ev.content,
                "meta": ev.meta
            })
            if ev.kind == "final":
                break
        return jsonify({"events": events})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_web(port=5000):
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    run_web()

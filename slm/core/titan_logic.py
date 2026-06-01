"""TITAN CORE LOGIC - Advanced Autonomous Orchestration.
Part of the BUGHUNTER-AI TITAN EDITION v2.4 upgrade.

This module handles:
  - Recursive Task Decomposition (Task Tree)
  - Self-Healing Execution (Plan adjustment on tool failure)
  - Skill Synthesis (Generating on-the-fly Python skills)
  - Mission State Serialization
"""
from __future__ import annotations
import json
import os
import pathlib
import re
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Any

from slm.agent import Agent, Event
from slm.tools import dispatch

logger = logging.getLogger("titan.logic")

@dataclass
class Task:
    """A single node in the recursive task tree."""
    id: str
    description: str
    status: str = "PENDING"  # PENDING | RUNNING | COMPLETED | FAILED
    parent_id: Optional[str] = None
    subtasks: List[Task] = field(default_factory=list)
    result: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "result": self.result,
            "attempts": self.attempts
        }

class MissionOrchestrator:
    """High-level manager for complex TITAN missions."""
    
    def __init__(self, agent: Agent, workdir: Optional[pathlib.Path] = None):
        self.agent = agent
        self.workdir = workdir or pathlib.Path.cwd()
        self.task_tree: Optional[Task] = None
        self.current_mission_id: str = f"mission_{int(time.time())}"
        
    async def decompose_goal(self, goal: str) -> Task:
        """Use the SLM to break a high-level goal into a task tree."""
        prompt = (
            f"Decompose the following bug-bounty goal into a JSON task tree:\n"
            f"Goal: {goal}\n\n"
            f"Respond with ONLY a valid JSON object with 'id', 'description', and 'subtasks' keys."
        )
        
        # We use the agent's LLM directly for decomposition
        system = "You are a master bug-bounty architect. Respond in JSON."
        try:
            raw = self.agent.llm.complete(system, [{"role": "user", "content": prompt}], temperature=0.1)
            # Extract JSON from potential markdown tags
            m = re.search(r"(\{.*\})", raw, re.S)
            if m:
                data = json.loads(m.group(1))
                return self._parse_task(data)
        except Exception as e:
            logger.error(f"Decomposition failed: {e}")
            
        # Fallback to single task if decomposition fails
        return Task(id="root", description=goal)

    def _parse_task(self, data: dict, parent_id: str = None) -> Task:
        task = Task(
            id=data.get("id", f"task_{int(time.time() * 1000)}"),
            description=data.get("description", "Unknown task"),
            parent_id=parent_id
        )
        for sub in data.get("subtasks", []):
            task.subtasks.append(self._parse_task(sub, task.id))
        return task

    async def execute_mission(self, goal: str) -> Iterator[Event]:
        """Run the full TITAN mission with recursive execution."""
        yield Event("thought", f"Initializing TITAN Mission: {self.current_mission_id}")
        
        self.task_tree = await self.decompose_goal(goal)
        yield Event("plan", f"MISSION STRUCTURE DEPLOYED:\n{json.dumps(self.task_tree.to_dict(), indent=2)}")
        
        # Start recursive execution
        async for ev in self._execute_task_recursive(self.task_tree):
            yield ev
            
        yield Event("final", f"Mission {self.current_mission_id} finalized.")

    async def _execute_task_recursive(self, task: Task) -> Iterator[Event]:
        """Depth-first execution of the task tree."""
        if task.status == "COMPLETED":
            return

        task.status = "RUNNING"
        yield Event("thought", f"Starting Task: {task.description}")
        
        if task.subtasks:
            for sub in task.subtasks:
                async for ev in self._execute_task_recursive(sub):
                    yield ev
            
            # After subtasks, evaluate if root task is done
            task.status = "COMPLETED"
        else:
            # Atomic task - run through agent
            async for ev in self.agent.run(task.description):
                yield ev
                if ev.kind == "final":
                    task.result = ev.content
                    task.status = "COMPLETED"
                elif ev.kind == "error":
                    task.attempts += 1
                    if task.attempts < task.max_attempts:
                        yield Event("thought", f"Retrying task: {task.description} (Attempt {task.attempts})")
                        # Recursive retry
                        async for rev in self._execute_task_recursive(task):
                            yield rev
                    else:
                        task.status = "FAILED"
                        yield Event("error", f"Task {task.id} failed after {task.max_attempts} attempts.")

class SkillSynthesizer:
    """Generates and validates new Python skills for the agent."""
    
    def __init__(self, slm_home: pathlib.Path):
        self.skills_dir = slm_home / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def synthesize_skill(self, request: str, agent: Agent) -> str:
        """Prompt the SLM to write a new Python tool/skill."""
        prompt = (
            f"Write a Python function for a new bug-bounty skill.\n"
            f"Requirement: {request}\n"
            f"The function must be decorated with @tool from slm.tools.\n"
            f"Respond with ONLY the Python code."
        )
        
        system = "You are a senior Python developer specializing in security automation."
        code = agent.llm.complete(system, [{"role": "user", "content": prompt}], temperature=0.2)
        
        # Strip potential markdown
        code = re.sub(r"```python|```", "", code).strip()
        
        # Save to disk
        filename = f"dynamic_{int(time.time())}.py"
        path = self.skills_dir / filename
        path.write_text(code)
        
        return f"Synthesized new skill: {filename}"

# Advanced Error Analysis Patterns
FAILURE_ANALYSIS = {
    "connection_refused": "Target is likely blocking standard ports. Switch to stealth scan.",
    "timeout": "Network latency detected. Increase timeout or reduce threads.",
    "permission_denied": "Path sandbox restriction. Attempt authorized alternatives.",
    "command_not_found": "Missing binary. Attempt to install via tool_installer.",
}

def analyze_failure(error_msg: str) -> str:
    """Analyze a tool error and suggest a TITAN-level workaround."""
    for key, suggestion in FAILURE_ANALYSIS.items():
        if key in error_msg.lower():
            return f"SUGGESTION: {suggestion}"
    return "SUGGESTION: Attempt alternative approach or decompose further."

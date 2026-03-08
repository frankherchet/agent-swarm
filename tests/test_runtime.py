"""Tests for provider runtime plumbing."""

from __future__ import annotations

import pytest

from claude_swarm.orchestrator import SwarmOrchestrator
from claude_swarm.runtime import AgentRuntime, RuntimeTextResult, create_runtime
from claude_swarm.types import SwarmPlan, SwarmTask, TaskStatus


class FakeRuntime(AgentRuntime):
    provider = "fake"
    default_worker_model = "fake-worker"

    def validate_environment(self) -> None:
        return None

    async def generate_text(
        self,
        prompt: str,
        cwd: str,
        model: str,
        *,
        max_turns: int,
    ) -> RuntimeTextResult:
        del prompt, cwd, model, max_turns
        return RuntimeTextResult(text="generated", total_cost_usd=0.01)

    async def run_task(
        self,
        task: SwarmTask,
        cwd: str,
        *,
        model: str,
        on_tool_use=None,
        on_file_write=None,
    ) -> RuntimeTextResult:
        del cwd, model
        if on_tool_use:
            on_tool_use("Read", {"file_path": "src/app.py"})
        if on_file_write:
            on_file_write("src/app.py")
        return RuntimeTextResult(text=f"done:{task.id}", total_cost_usd=0.25)


def test_create_runtime_known_providers() -> None:
    assert create_runtime("claude").provider == "claude"
    assert create_runtime("copilot").provider == "copilot"


def test_create_runtime_unknown_provider() -> None:
    with pytest.raises(ValueError):
        create_runtime("unknown")


@pytest.mark.anyio
async def test_orchestrator_runs_task_via_runtime() -> None:
    task = SwarmTask(id="task-1", description="Do work", agent_type="coder", status=TaskStatus.RUNNING)
    plan = SwarmPlan(original_prompt="test", tasks=[task])
    runtime = FakeRuntime()
    orch = SwarmOrchestrator(
        plan=plan,
        cwd="/tmp",
        runtime=runtime,
        default_worker_model=runtime.default_worker_model,
    )

    await orch._run_agent(task)

    assert task.status == TaskStatus.COMPLETED
    assert task.result == "done:task-1"
    assert task.cost_usd == 0.25
    assert orch.total_cost == 0.25
    assert len(orch.agents) == 1
    only_agent = next(iter(orch.agents.values()))
    assert only_agent.current_tool == "Read"
    assert only_agent.files_modified == ["src/app.py"]

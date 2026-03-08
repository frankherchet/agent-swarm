"""Provider-neutral agent runtimes for Claude and GitHub Copilot."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .types import SwarmTask


ToolUseCallback = Callable[[str, dict[str, Any]], None]
FileWriteCallback = Callable[[str], None]


@dataclass
class RuntimeTextResult:
    """Normalized text result from an agent runtime."""

    text: str = ""
    total_cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRuntime(ABC):
    """Abstract runtime used by the swarm."""

    provider: str
    default_worker_model: str

    @abstractmethod
    def validate_environment(self) -> None:
        """Raise an error when required runtime dependencies are unavailable."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        cwd: str,
        model: str,
        *,
        max_turns: int,
    ) -> RuntimeTextResult:
        """Generate text for planning and review phases."""

    @abstractmethod
    async def run_task(
        self,
        task: SwarmTask,
        cwd: str,
        *,
        model: str,
        on_tool_use: ToolUseCallback | None = None,
        on_file_write: FileWriteCallback | None = None,
    ) -> RuntimeTextResult:
        """Execute a worker task."""


class ClaudeRuntime(AgentRuntime):
    """Runtime backed by claude-agent-sdk."""

    provider = "claude"
    default_worker_model = "haiku"

    def validate_environment(self) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your key at: https://console.anthropic.com/settings/keys"
            )

        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "claude-agent-sdk is not installed. Install project dependencies first."
            ) from exc

    async def generate_text(
        self,
        prompt: str,
        cwd: str,
        model: str,
        *,
        max_turns: int,
    ) -> RuntimeTextResult:
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

        options = ClaudeAgentOptions(
            model=model,
            cwd=cwd,
            permission_mode="default",
            max_turns=max_turns,
        )

        collected_text = ""
        total_cost = 0.0

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected_text += block.text
            elif isinstance(message, ResultMessage):
                total_cost = message.total_cost_usd or 0.0

        return RuntimeTextResult(text=collected_text, total_cost_usd=total_cost)

    async def run_task(
        self,
        task: SwarmTask,
        cwd: str,
        *,
        model: str,
        on_tool_use: ToolUseCallback | None = None,
        on_file_write: FileWriteCallback | None = None,
    ) -> RuntimeTextResult:
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_sdk.types import (
            AssistantMessage,
            HookContext,
            HookInput,
            HookJSONOutput,
            HookMatcher,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
        )

        async def track_file_writes(
            input_data: HookInput, tool_use_id: str | None, context: HookContext
        ) -> HookJSONOutput:
            del tool_use_id, context
            tool_name = input_data.get("tool_name", "")
            tool_input = input_data.get("tool_input", {})
            if tool_name in ("Write", "Edit"):
                file_path = tool_input.get("file_path", "")
                if file_path and on_file_write:
                    on_file_write(file_path)
            return {}

        hooks: dict[str, list[HookMatcher]] = {}
        if on_file_write:
            hooks["PostToolUse"] = [HookMatcher(matcher="Write|Edit", hooks=[track_file_writes])]

        options = ClaudeAgentOptions(
            model=model,
            cwd=cwd,
            permission_mode="acceptEdits",
            max_turns=20,
            max_budget_usd=0.50,
            hooks=hooks or None,
            allowed_tools=task.tools or None,
        )

        collected_text = ""
        total_cost = 0.0

        async for message in query(prompt=task.prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected_text += block.text
                    elif isinstance(block, ToolUseBlock) and on_tool_use:
                        on_tool_use(block.name, block.input)
            elif isinstance(message, ResultMessage):
                total_cost = message.total_cost_usd or 0.0

        return RuntimeTextResult(text=collected_text, total_cost_usd=total_cost)


class CopilotRuntime(AgentRuntime):
    """Runtime backed by the GitHub Copilot Python SDK."""

    provider = "copilot"
    default_worker_model = "gpt-5"

    def validate_environment(self) -> None:
        try:
            from copilot import CopilotClient  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "github-copilot-sdk is not installed. Install project dependencies first."
            ) from exc

    async def generate_text(
        self,
        prompt: str,
        cwd: str,
        model: str,
        *,
        max_turns: int,
    ) -> RuntimeTextResult:
        del max_turns
        return await self._run_session(prompt=prompt, cwd=cwd, model=model)

    async def run_task(
        self,
        task: SwarmTask,
        cwd: str,
        *,
        model: str,
        on_tool_use: ToolUseCallback | None = None,
        on_file_write: FileWriteCallback | None = None,
    ) -> RuntimeTextResult:
        hooks = self._build_hooks(on_tool_use=on_tool_use, on_file_write=on_file_write)
        return await self._run_session(
            prompt=task.prompt,
            cwd=cwd,
            model=model,
            hooks=hooks,
        )

    async def _run_session(
        self,
        *,
        prompt: str,
        cwd: str,
        model: str,
        hooks: dict[str, Any] | None = None,
    ) -> RuntimeTextResult:
        from copilot import CopilotClient

        client = CopilotClient({"cwd": cwd})
        await client.start()

        collected_text: list[str] = []
        done = asyncio.Event()

        try:
            session_config: dict[str, Any] = {
                "model": model,
                "streaming": False,
            }
            if hooks:
                session_config["hooks"] = hooks

            session = await client.create_session(session_config)

            def on_event(event: Any) -> None:
                event_type = getattr(getattr(event, "type", None), "value", None)
                if event_type is None and isinstance(event, dict):
                    event_type = event.get("type")

                data = getattr(event, "data", None)
                if data is None and isinstance(event, dict):
                    data = event.get("data", {})

                content = getattr(data, "content", None)
                if content is None and isinstance(data, dict):
                    content = data.get("content")

                if event_type == "assistant.message" and content:
                    collected_text.append(str(content))
                elif event_type == "session.idle":
                    done.set()

            session.on(on_event)

            async with session:
                await session.send({"prompt": prompt})
                await done.wait()

            return RuntimeTextResult(
                text="".join(collected_text),
                metadata={"cost_tracked": False},
            )
        finally:
            await client.stop()

    def _build_hooks(
        self,
        *,
        on_tool_use: ToolUseCallback | None,
        on_file_write: FileWriteCallback | None,
    ) -> dict[str, Any]:
        async def on_pre_tool_use(input_data: dict[str, Any], invocation: Any) -> dict[str, Any]:
            del invocation
            tool_name = input_data.get("toolName", "")
            tool_args = input_data.get("toolArgs", {}) or {}
            if on_tool_use and tool_name:
                on_tool_use(tool_name, tool_args)
            return {
                "permissionDecision": "allow",
                "modifiedArgs": tool_args,
            }

        async def on_post_tool_use(
            input_data: dict[str, Any], invocation: Any
        ) -> dict[str, Any]:
            del invocation
            tool_name = input_data.get("toolName", "")
            tool_args = input_data.get("toolArgs", {}) or {}
            if on_file_write and tool_name in {"edit_file", "write_file"}:
                for key in ("path", "file_path", "filePath"):
                    file_path = tool_args.get(key)
                    if file_path:
                        on_file_write(str(file_path))
                        break
            return {}

        return {
            "on_pre_tool_use": on_pre_tool_use,
            "on_post_tool_use": on_post_tool_use,
        }


def create_runtime(provider: str) -> AgentRuntime:
    """Create an agent runtime for the requested provider."""
    normalized = provider.strip().lower()
    if normalized == "claude":
        return ClaudeRuntime()
    if normalized == "copilot":
        return CopilotRuntime()
    raise ValueError(f"Unsupported provider: {provider}")

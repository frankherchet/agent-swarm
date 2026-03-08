# Claude Swarm

[![PyPI](https://img.shields.io/pypi/v/claude-swarm)](https://pypi.org/project/claude-swarm/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-44%20passing-brightgreen.svg)]()

**Multi-agent orchestration for coding agents** — decompose complex tasks into parallel subtasks, coordinate agents in real-time, and visualize everything in a rich terminal UI.

Built in Python with pluggable runtimes for the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) and the [GitHub Copilot SDK](https://github.com/github/copilot-sdk).

## How It Works

```
You: "Refactor auth module from Express middleware to Next.js API routes"

Claude Swarm:
  Phase 1:   A planner decomposes the task into a dependency graph
  Phase 2:   Parallel agents execute subtasks with live dashboard
  Phase 2.5: A reviewer checks the combined output
  Phase 3:   Results summary with costs and session replay
```

1. **Task Decomposition** — Describe a complex task. Claude Swarm uses the configured provider/model to analyze your codebase and break it into a dependency graph of subtasks
2. **Parallel Agent Spawning** — Independent subtasks run simultaneously via the selected runtime provider. Dependent tasks wait.
3. **Real-time Coordination** — File conflict detection prevents agents from stepping on each other. Budget enforcement stops runaway costs.
4. **Quality Gate** — After agents complete, the configured review model checks the combined output for correctness, consistency, and completeness
5. **Rich Terminal UI** — `htop`-style dashboard showing agent progress, tool usage, costs, and file conflicts in real-time
6. **Session Replay** — Every swarm execution is recorded. Replay any session to review what each agent did.

## Quick Start

```bash
# See it in action instantly (no API key needed!)
pip install claude-swarm
claude-swarm --demo

# Or install from source
git clone https://github.com/affaan-m/claude-swarm
cd claude-swarm
pip install -e .

# Claude runtime
export ANTHROPIC_API_KEY="sk-ant-..."

# Run a swarm with Claude
claude-swarm "Refactor auth module from Express middleware to Next.js API routes"

# Run a swarm with GitHub Copilot
claude-swarm --provider copilot "Refactor auth module from Express middleware to Next.js API routes"

# Dry run (shows plan without executing)
claude-swarm --dry-run "Add user authentication with JWT"

# Custom budget, agents, and retries
claude-swarm --budget 3.0 --max-agents 6 --retry 2 "Build a REST API for user management"

# Disable quality gate for faster execution
claude-swarm --no-quality-gate "Quick fix: update README"
```

## Architecture

```
┌───────────────────────────────────────────────┐
│              Claude Swarm CLI                  │
│                                                │
│  Phase 1: Decompose                            │
│  ┌─────────────────────────────────────────┐   │
│  │  Runtime-backed Task Decomposer        │   │
│  │  "Add auth" -> [create routes,          │   │
│  │   add middleware, write tests, review]   │   │
│  └──────────────┬──────────────────────────┘   │
│                 │ dependency graph              │
│  Phase 2: Execute                              │
│  ┌──────────────▼──────────────────────────┐   │
│  │       Swarm Orchestrator                │   │
│  │                                         │   │
│  │  Wave 1: ┌────────┐ ┌────────┐         │   │
│  │          │ Agent 1 │ │ Agent 2 │  (parallel)│
│  │          │ coder   │ │ coder   │         │  │
│  │          └────┬────┘ └────┬────┘         │  │
│  │  Wave 2:      └─────┬─────┘              │  │
│  │               ┌─────▼─────┐              │  │
│  │               │  Agent 3  │  (depends)   │  │
│  │               │  tester   │              │  │
│  │               └─────┬─────┘              │  │
│  │  Wave 3:      ┌─────▼─────┐              │  │
│  │               │  Agent 4  │  (depends)   │  │
│  │               │  reviewer │              │  │
│  │               └───────────┘              │  │
│  │                                          │  │
│  │  File Locks: {auth.ts -> Agent 1}       │  │
│  │  Budget: $0.23 / $5.00                  │  │
│  │  Retries: task-2 (attempt 2/3)          │  │
│  └──────────────────────────────────────────┘  │
│                                                │
│  Phase 2.5: Quality Gate                       │
│  ┌──────────────────────────────────────────┐  │
│  │  Configured reviewer checks output       │  │
│  │  Score: 8/10 | Verdict: PASS            │  │
│  └──────────────────────────────────────────┘  │
│                                                │
│  Phase 3: Results                              │
│  ┌──────────────────────────────────────────┐  │
│  │  4/4 tasks completed | $0.45 | 32s      │  │
│  │  Session: swarm-a1b2c3d4                 │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **Dependency-aware scheduling** | Tasks only start when their dependencies complete |
| **File conflict detection** | Pessimistic file locking prevents agents from editing the same file simultaneously |
| **Budget enforcement** | Hard cost limit — cancels remaining tasks when budget is exceeded |
| **Cost tracking** | Real-time per-agent and total cost monitoring where the provider exposes usage/cost data |
| **Provider runtime abstraction** | Run the swarm through Claude Agent SDK or GitHub Copilot SDK |
| **Quality Gate** | Phase 2.5 — a configurable review model checks all agent outputs for correctness and consistency |
| **Per-phase model selection** | Configure separate planning, review, and worker models |
| **Task retry** | Failed tasks are automatically retried with configurable attempt limits |
| **Demo mode** | `--demo` flag shows animated TUI without API key (great for presentations) |
| **Session recording** | Every swarm execution recorded as JSONL events |
| **Session replay** | `claude-swarm replay <id>` to review what each agent did |
| **YAML config** | Declarative swarm topologies via `swarm.yaml` |
| **Progress visualization** | Live htop-style dashboard with Rich |

## CLI Reference

```bash
# Main command
claude-swarm [OPTIONS] TASK

Options:
  -d, --cwd TEXT            Working directory (default: .)
  --provider [claude|copilot]
                            Agent runtime provider (default: claude)
  -n, --max-agents INTEGER  Max concurrent agents (default: 4)
  -m, --model TEXT          Decomposition model (default: opus)
  -b, --budget FLOAT        Max budget in USD (default: 5.0)
  -r, --retry INTEGER       Max retries for failed tasks (default: 1)
  -c, --config PATH         Path to swarm.yaml
  --demo                    Run demo simulation (no API key needed)
  --dry-run                 Show plan without executing
  --quality-gate/--no-quality-gate  Enable/disable final quality review (default: on)
  --no-ui                   Disable rich terminal UI
  -v, --version             Show version

# Subcommands
claude-swarm sessions              # List past sessions
claude-swarm replay <session-id>   # Replay a session's events
```

## YAML Configuration

Create `swarm.yaml` in your project root to define custom agent types:

```yaml
swarm:
  name: full-stack-review
  provider: copilot
  max_concurrent: 4
  budget_usd: 5.0
  model: gpt-5
  review_model: gpt-5-mini
  worker_model: gpt-5-codex

agents:
  security-reviewer:
    description: Reviews code for OWASP vulnerabilities
    model: gpt-5
    tools: [Read, Grep, Glob]
    prompt: |
      Analyze the code for SQL injection, XSS, CSRF...

  tester:
    description: Writes and runs tests
    model: gpt-5-codex
    tools: [Read, Write, Edit, Bash]
    prompt: |
      Write comprehensive tests. Ensure 80% coverage...

connections:
  - from: coder
    to: security-reviewer
  - from: coder
    to: tester
  - from: [security-reviewer, tester]
    to: reviewer
```

Claude Swarm auto-detects `swarm.yaml` or `.claude/swarm.yaml` in your project.

## Providers and Models

Claude Swarm now separates orchestration from agent runtime.

- `claude` uses `claude-agent-sdk` and requires `ANTHROPIC_API_KEY`
- `copilot` uses `github-copilot-sdk` and your local Copilot authentication/session
- `model` configures the planning phase
- `review_model` configures the quality gate
- `worker_model` provides the default model for task execution
- Per-agent `model` entries in `swarm.yaml` override the default worker model

The orchestrator, retries, conflict detection, TUI, and session replay remain local to `claude-swarm`; only the agent runtime changes by provider.

## Cost Tracking Notes

- Claude runs report cost through the SDK and participate fully in budget accounting.
- Copilot runs are supported through the runtime abstraction, but provider cost reporting may be limited by the SDK surface. Budget enforcement is therefore most accurate on Claude today.

## Tech Stack

- **Python 3.11+** with `anyio` for structured async concurrency
- **claude-agent-sdk** (v0.1.35+) for the Claude runtime
- **github-copilot-sdk** for the Copilot runtime
- **Rich** for terminal UI (Live dashboard with panels and tables)
- **Click** for CLI framework
- **Pydantic** for data validation
- **NetworkX** for dependency graph topological sorting

## Development

```bash
# Clone and install
git clone https://github.com/affaan-m/claude-swarm
cd claude-swarm
pip install -e ".[dev]"

# Run tests (44 passing)
pytest tests/ -v

# Lint
ruff check src/ tests/
```

## Project Structure

```
src/claude_swarm/
  cli.py           CLI entry point (Click group + subcommands)
  types.py         Core dataclasses (SwarmTask, SwarmPlan, etc.)
  runtime.py       Provider abstraction for Claude and Copilot runtimes
  decomposer.py    Provider-backed task decomposition
  orchestrator.py  Parallel execution with file locks, budget, retries
  quality_gate.py  Provider-backed quality review of agent outputs
  demo.py          Demo simulation with animated TUI
  config.py        YAML swarm topology configuration
  session.py       JSONL event recording and replay
  ui.py            Rich terminal dashboard
```

## License

MIT — [Affaan Mustafa](https://x.com/affaanmustafa)

## Acknowledgments

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) for the Claude runtime
- [GitHub Copilot SDK](https://github.com/github/copilot-sdk) for the Copilot runtime
- [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) for agent patterns and inspiration
- Built for the [Cerebral Valley x Anthropic Claude Code Hackathon](https://cerebralvalley.ai/hackathons/claude-code-hackathon-aaHFuycPfjQa5dNaxZpU)

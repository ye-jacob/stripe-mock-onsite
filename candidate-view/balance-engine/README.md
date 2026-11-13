# balance-engine — AI-enabled programming exercise

## How this session works

- 60 minutes: about 10 for introductions and setup, 45 to solve, 5 to wrap up.
- The exercise comes in several parts and you get them one at a time. Part 1 is
  in [`PROBLEM.md`](PROBLEM.md). Your interviewer releases the next part when
  you have finished the current one, so you will not see the whole problem up
  front. Most people do not finish every part.
- **Use an AI coding agent.** This interview is about how you plan, direct,
  check and build on what the agent produces.
  - Use the agent built into your editor: Cursor, VS Code with GitHub Copilot in
    agent mode, Windsurf, or a CLI agent (Claude Code, Codex, Gemini CLI)
    running in the editor's terminal.
  - Use **one** assistant, and keep it visible in your screen share for the
    whole session, prompts and answers included.
  - No other AI tools, tabs or chat windows.
- Think out loud: say why you prompt the way you do, and what you make of the
  answers.
- Ask your interviewer anything, at any time, as you would ask a teammate.

At the end your interviewer will ask: **"How do you know this is correct?"**

## Setup

You need Python 3.9 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest                     # one test fails until Part 1 is done
```

## What is here

| Path | What it is |
| --- | --- |
| `PROBLEM.md` | Part 1 of the problem. |
| `balance_engine.py` | Your code. Every function a part asks for must be importable from this module. |
| `tests/` | Your tests. `tests/test_examples.py` holds the Part 1 example. |
| `data/sample_events.csv` | A small event log to experiment with. |

When you receive a later part you may save its text in this folder, for example
as `PART2.md`, so that your agent can read it.

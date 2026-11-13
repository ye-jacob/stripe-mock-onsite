# Environment check

Do this a day or two before your mock interview. It takes about 15 minutes.

In the real interviews only the first 5 to 10 minutes are set aside for
settling in. Anything that goes wrong with your setup after that comes out of
your coding time, so find the problems now.

## 1. Python toolchain (every session)

You need Python 3.9 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python check_env.py
```

Every line should start with `[ ok ]`. Fix anything marked `[FAIL]` and read
anything marked `[warn]`.

## 2. Your AI coding agent (AI-enabled programming session)

On the day you will solve a multi-part problem together with an AI agent that
lives in your editor. Pick the one you will use and rehearse with it:

- Cursor (Agent), VS Code with GitHub Copilot in agent mode, Windsurf, or
- a CLI agent such as Claude Code, Codex or Gemini CLI running in your editor's
  terminal.

Check that your plan has enough quota left for about 45 minutes of steady use.

Then open **this folder** in that editor and do the warm-up:

1. Run `python -m pytest warmup`. The tests fail: `warmup/text_stats.py` is a stub.
2. Read `warmup/test_text_stats.py` yourself and decide what the code has to do.
3. Ask your agent to make the tests pass. Give it the constraints you noticed.
4. Review what it wrote before you accept it. Run the tests yourself.

You are ready when you can do all of these without hunting through menus:

- point the agent at specific files, and have it edit files and run commands,
- see exactly what it changed (the diff), and accept or reject changes,
- interrupt it when it goes in the wrong direction,
- run the tests from the terminal yourself.

## 3. Your debugger (Bug squash session)

In the bug squash session you track down bugs in a library you have not read
before. A debugger you are fluent with saves a lot of time there. Rehearse on
the warm-up, before or after your agent has solved it:

```bash
python -m pytest warmup -x --pdb     # drops into pdb at the first failure
```

Or use your editor: set a breakpoint in `warmup/text_stats.py`, then run one
test in debug mode.

You are ready when you can do these without thinking about the keys:

- set a breakpoint and run a single test up to it,
- step over, step into and step out,
- inspect variables and evaluate an expression,
- move up and down the call stack.

Debugging with print statements is fine too. Decide which you will use.

## 4. Screen sharing

- Share your **whole editor window**: code, terminal and the agent panel.
- Raise the font size so that code is readable in a video call.
- Close anything you would not want on screen, and silence notifications.
- For the Integration and Bug squash sessions, turn AI completions **off** in
  your editor.

## 5. For a real Stripe interview

Stripe publishes its own environment check for each language. Run it too:
<https://github.com/stripe-interview/python-interview-prep>

# Interviewer kit: Stripe-style mock virtual onsite

Everything in this folder is for the interviewer. The full run-of-show, scripts,
hint ladders and scorecards are in the interviewer guide (the doc that came with
this kit). This file is only a map.

## Getting material to the candidate

Preferred: share the **candidate portal** link. The candidate downloads the
starter repositories from it, and each stage stays encrypted until you give the
code for it (`unlock-codes.txt`).

If the link cannot be shared, send `candidate-portal.html` as a file instead. It
is the same portal in one self-contained page: the candidate opens it in a
browser, and it works offline.

If you would rather not use the portal at all, everything it contains is in
`send-to-candidate/`: send each item at the moment the table below says.

| When | Portal code for | Or send by hand |
| --- | --- | --- |
| A few days before | (always open) | `environment-check.zip` |
| Start of Session 1 | Session 1 | `larkspur-settlements.zip` |
| Start of Session 2 | Session 2, Part 1 | `balance-engine.zip` |
| When each part is done | Part 2, Part 3, Part 4 | paste `part-cards/part2.md` and so on into the call chat |
| Start of Session 3 | Session 3 | `mako-bugsquash.zip` |
| After each session | verification suites, Session 3 debrief | `verify_integration.zip`, `verify_ai.zip`, `bug-squash-debrief.md` |

## What is where

| Path | What it is |
| --- | --- |
| `unlock-codes.txt` | The nine portal codes |
| `candidate-portal.html` | Offline copy of the portal |
| `send-to-candidate/` | The same material as plain zips and Markdown |
| `integration/reference-solution/` | One good solution: drop the four files over `settlements/` in the starter |
| `integration/verify_integration/` | Verification suite (59 tests) with its own README |
| `integration/expected-results.md` | The right numbers for every merchant, and the numbers common mistakes produce |
| `integration/tools/` | How the mock data was generated and how the suite was validated |
| `ai-exercise/part-cards/` | The four problem statements, exactly as the candidate sees them |
| `ai-exercise/reference-solution/` | One good `balance_engine.py` covering all four parts |
| `ai-exercise/verify_ai/` | Verification suite (118 tests) with its own README |
| `ai-exercise/tools/` | Independent oracle, fuzzer and mutation check used to validate the suite |
| `bug-squash/debrief.md` | The three planted bugs: failing tests, symptoms, a good path to each, the fix |
| `bug-squash/solution.patch` | All three fixes as one patch (`git apply` it in the candidate's folder) |
| `bug-squash/fixed-files/` | The three corrected Mako source files |

## Try it yourself first (10 minutes)

```bash
cd send-to-candidate && unzip larkspur-settlements.zip && cd larkspur-settlements
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m pytest                                   # 31 passed
cp ../../integration/reference-solution/settlements/*.py settlements/
cp -r ../../integration/verify_integration .
python -m pytest verify_integration                # 59 passed
python server/mock_api.py &                        # then, in the same shell:
python -m settlements report acct_nimbus
python -m settlements settle acct_nimbus --date 2026-11-12
```

## Dry-run the bug squash (5 minutes)

From the kit folder, in a new terminal:

```bash
cd send-to-candidate && unzip mako-bugsquash.zip && cd mako-bugsquash
python3 -m venv .venv && source .venv/bin/activate && pip install -r bugsquash-requirements.txt
python -m pytest test/ --tb=short                  # 5 failed, 460 passed, 53 skipped
git init -q && git apply ../../bug-squash/solution.patch
python -m pytest test/ --tb=short                  # 465 passed, 53 skipped
```

Then read `bug-squash/debrief.md` with the three patched files open.

## Optional: GitHub and Codespaces

HackerRank's AI interview environment is a browser IDE with an agent. A GitHub
Codespace is the closest free equivalent, and the Session 1 and Session 2
starters ship a `.devcontainer` for it. Session 3 is meant to be done locally,
with the candidate's own debugger.

1. Create an empty private repository for each starter.
2. Unzip the starter, then `git init -b main && git add . && git commit -m "Starter" && git remote add origin <url> && git push -u origin main`.
3. At the start of the session add the candidate as a collaborator, or make the repository public.
4. The candidate chooses Code, Codespaces, Create codespace on main. Dependencies install automatically.

For the AI session the candidate needs GitHub Copilot on their own account. For
the Integration session Copilot is switched off by the devcontainer settings.

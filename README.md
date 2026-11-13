# Stripe mock onsite kit (private)

**Keep this repository private.** It holds the reference solutions, the answer
keys and the unlock codes for the candidate portal.

The run-of-show, scripts, hint ladders and scorecards are in the
[interviewer guide](https://claude.ai/artifact/3jjJd2eTRn7VsvA3sM46Pi). The
candidate works from the
[candidate portal](https://claude.ai/artifact/Xp6d5RHSeqohLJXCFvTCKz).

## Open these during a session

| Session | For you | What the candidate sees |
| --- | --- | --- |
| Pre-work | | [Environment check](candidate-view/environment-check/README.md) |
| 1. Integration | [Expected results and common wrong numbers](interviewer-kit/integration/expected-results.md) · [Reference solution](interviewer-kit/integration/reference-solution/settlements) · [Verification suite](interviewer-kit/integration/verify_integration/README.md) | [Spec](candidate-view/larkspur-settlements/README.md) · [API reference](candidate-view/larkspur-settlements/docs/API.md) · [Starter code](candidate-view/larkspur-settlements) |
| 2. AI-enabled programming | Part cards: [1](interviewer-kit/ai-exercise/part-cards/part1.md) · [2](interviewer-kit/ai-exercise/part-cards/part2.md) · [3](interviewer-kit/ai-exercise/part-cards/part3.md) · [4](interviewer-kit/ai-exercise/part-cards/part4.md) · [Reference solution](interviewer-kit/ai-exercise/reference-solution/balance_engine.py) · [Verification suite](interviewer-kit/ai-exercise/verify_ai/README.md) | [README](candidate-view/balance-engine/README.md) · [PROBLEM.md](candidate-view/balance-engine/PROBLEM.md) · [Starter code](candidate-view/balance-engine) |
| 3. Bug squash | [Debrief: the three bugs and their fixes](interviewer-kit/bug-squash/debrief.md) · [Solution patch](interviewer-kit/bug-squash/solution.patch) · [Notes](interviewer-kit/bug-squash/README.md) | [BUGSQUASH.md](candidate-view/mako-bugsquash/BUGSQUASH.md) · [Repository](candidate-view/mako-bugsquash) |

Also: [unlock codes](interviewer-kit/unlock-codes.txt) · [map of the kit](interviewer-kit/README.md)

## Layout

| Folder | What it is |
| --- | --- |
| `interviewer-kit/` | The exact contents of `interviewer-kit.zip` |
| `candidate-view/` | Unzipped copies of what the candidate downloads, for reading. `mako-bugsquash/` still contains its three planted bugs. |

Nothing here is affiliated with or endorsed by Stripe. Larkspur, the company in
Sessions 1 and 2, is fictional. `candidate-view/mako-bugsquash/` is Mako 1.3.12
(MIT licence, see its `LICENSE`) with bugs planted for the exercise.

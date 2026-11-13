# Bug squash

This folder is a copy of **Mako**, an open-source template library for Python
(version 1.3.12, MIT licence, see `LICENSE`). Bugs have been planted in it for
this exercise, so do not use this copy for anything else.

## Your task

Some tests in the test suite fail. Find out why, fix the library, and get the
suite back to green.

- The bugs are in the library code under `mako/`. The tests are right: do not
  change anything under `test/`.
- You will not be told how many bugs there are. There are not many.
- Each fix is small. Being able to explain why it is the right fix matters more
  than the diff.

## Ground rules

- 60 minutes, in your own editor, sharing your screen.
- Think out loud. Before each step, say what you expect to find: a hypothesis
  first, then the check that confirms or rejects it.
- Use whatever you debug with: an IDE debugger, `pdb`, print statements.
- You may read Mako's documentation (in `doc/build/`, or online at
  <https://docs.makotemplates.org>) and search the web.
- Work from this copy only. Do not download Mako's original source code or
  compare this folder with it: that would skip the exercise.
- **No AI assistance of any kind.** No chat assistants, no AI code completion
  in your editor, no AI answers in search results.
- Your interviewer is your teammate. Ask whenever something is unclear.
- You do not have to find every bug. A clear method counts for more than a
  lucky find.

## Setup

You need Python 3.9 or newer. Run everything from this folder.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r bugsquash-requirements.txt
python -m pytest test/               # most tests pass, some are skipped, a few fail
```

The skipped tests need optional packages that this exercise does not use.
Ignore them.

Optional, and useful: put the starting state under version control, so that
`git diff` always shows exactly what you have changed.

```bash
git init -q && git add -A && git commit -qm "Starting point"
```

## Finding your way around

| Path | What it is |
| --- | --- |
| `mako/` | The library |
| `test/` | Its test suite. `test/templates/` holds template files that some tests load. |
| `doc/build/*.rst` | The documentation, as plain text |
| `setup.cfg` | Includes the pytest settings this project uses |
| `README.rst` | What Mako is, with a small example |

Running one test, or a few:

```bash
python -m pytest test/test_template.py                  # one file
python -m pytest test/test_template.py -k "include"     # tests whose name contains "include"
```

The project's pytest settings print long tracebacks. Add `--tb=short` to
shorten them, or `-x` to stop at the first failure.

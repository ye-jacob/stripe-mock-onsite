# Bug squash: interviewer files

| File | What it is |
| --- | --- |
| `debrief.md` | The three bugs: failing tests, symptoms, a good path to each, the fix. The portal releases the same text to the candidate with the debrief code. |
| `solution.patch` | All three fixes as one patch. From the candidate's folder: `git apply solution.patch` (or `patch -p1 < solution.patch`). |
| `fixed-files/mako/` | The three corrected source files, to copy over the candidate's if you prefer |

The candidate's folder is Mako 1.3.12 with three planted bugs. Besides the bugs
it differs from the original in four small ways: three test assertions carry
Mako's own later fix for Pygments 2.21, one test was added next to
`test_convert_str`, `.gitignore` has four more lines, and `BUGSQUASH.md` and
`bugsquash-requirements.txt` were added.

At the start `python -m pytest test/` ends with `5 failed, 460 passed, 53 skipped`.
With the patch applied it ends with `465 passed, 53 skipped`. The skipped tests
need optional packages (Beaker, dogpile.cache, Babel, lingua) that the exercise
does not install.

Green is necessary, not sufficient. `debrief.md` lists two fixes that turn the
tests green without being right; compare the candidate's `git diff` with
`solution.patch` before you call a bug done.

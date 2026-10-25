# Engineering guide for students: the code-quality tools in KhetSetu

This guide explains the quality tools that were added to this repo (ruff, mypy, pytest,
import-linter, gitleaks, pre-commit, pip-audit, GitHub Actions), in plain language. It is written
for a student team that has not used them before.

Read **"The 10-minute version"** first. Everything after it is reference material for when you are
curious or stuck. The technical runbook for maintainers is in [`docs/ci.md`](ci.md).

---

## The 10-minute version

### What problem are these tools solving?

When several people edit the same project, the usual problems are:

- someone commits a typo-level bug that only shows up when the app runs;
- code looks different in every file, so reviews are about style, not logic;
- someone pastes a password or API token into the code and pushes it to GitHub;
- someone adds a 800 MB dataset to git and the repo becomes unusable;
- the UI code quietly starts reaching into the model code, and the project becomes tangled.

Each tool below is a **robot reviewer** that catches one of these problems in seconds, before a
human has to. They do not write your code. They only say "this is wrong" or "this is fine".

### The tools, one line each

| Tool | Think of it as | Catches |
| --- | --- | --- |
| **pytest** | Automatic exam for your code | Code that does the wrong thing |
| **ruff** | Spell-check + grammar-check for Python | Unused imports, likely bugs, messy formatting, missing docstrings |
| **mypy** | A checker for "did you pass the right kind of thing?" | Passing a string where a number is expected, etc. |
| **import-linter** | A rule book about who may talk to whom | Frontend importing backend internals |
| **gitleaks** | A metal detector for passwords | API tokens or passwords committed to git |
| **pip-audit** | A recall-notice checker for libraries | Libraries with known security holes |
| **pre-commit** | A bouncer at the `git commit` door | Runs the above on your changes before the commit is created |
| **GitHub Actions (CI)** | The same robot reviewers, running on GitHub | Anything that slipped past your laptop |
| **uv** | Installs the exact same libraries for everyone | "It works on my machine" problems |

### The only commands you need to remember

Run these from the project root. `make` runs a pre-written list of commands (see the `Makefile`).

```bash
make sync     # one time, and after anyone changes dependencies: install everything
make check    # THE command: lint + types + import rules + tests
make test     # only the tests, if you are in a hurry
make help     # shows all available commands
```

If `make check` prints errors, fix them before you commit. That is the whole workflow.

### The golden rule

> **Before you commit or open a pull request, run `make check`. If it is green, you are done.**

Everything else in this document explains *why* and *how to read the errors*.

---

## How each tool works and how to use it

### 1. pytest: your safety net

**What it does.** Finds files named `test_*.py`, runs every function starting with `test_`, and
reports which ones failed.

**Example.** A test says "when the model is not sure, the app must not name a disease". If a later
change breaks that, the test fails immediately, even if you did not notice.

**How to use it.**

```bash
make test                                   # all tests, with a coverage report
uv run pytest tests/test_workspace.py -q    # one file
uv run pytest -k "gate" -q                  # only tests with "gate" in the name
```

**Coverage.** `make test` also prints what percentage of your code the tests actually run. The
repo requires at least 80%. Think of it as "how much of the code has an exam" rather than "how
good the code is".

**Good habits.**

- Write the test first when fixing a bug: make it fail, then fix the code until it passes.
- One test checks one behaviour, and its name says which (`test_refusal_never_has_disease_name`).
- A test that never fails is useless. If you cannot imagine it failing, it tests nothing.

### 2. ruff: spelling and style for Python

**What it does.** Two jobs:

- `ruff check` finds probable mistakes (unused variables, risky code patterns, missing docstrings,
  forgotten `print` calls left in code).
- `ruff format` rewrites code into one consistent style (spacing, quotes, line length 100).

**How to use it.**

```bash
uv run ruff check .             # list problems
uv run ruff check --fix .       # fix the simple ones automatically
uv run ruff format .            # auto-format everything
make lint                       # what CI runs (check + format check)
```

**Reading an error.**

```
backend/src/khetsetu_backend/cli.py:12:8: F401 `os` imported but unused
```

That is `file : line : column : rule code  message`. Search the rule code (`F401`) in the ruff
docs for a full explanation with examples. Most errors fix themselves with `--fix`.

**Why it makes you better.** Reading these messages for a few weeks teaches you the common Python
traps (mutable default arguments, bare `except:`, unused imports) without anyone lecturing you.

### 3. mypy: type checking

**What it does.** Python lets you pass anything anywhere. Type hints say what you intend:

```python
def confidence_label(score: float) -> str: ...
```

mypy reads those hints and reports places where you break your own promise, such as passing
`"0.9"` (text) where `0.9` (a number) is expected, or forgetting that a value can be `None`.

**How to use it.**

```bash
make type          # or: uv run mypy
```

**Reading an error.**

```
app.py:20: error: Argument 1 to "predict" has incompatible type "str"; expected "bytes"
```

Fix the call or fix the hint, whichever is wrong.

**It is "strict" here.** That means every function needs type hints. It feels fussy for a week
and then you stop making a whole class of bugs. If a specific error is baffling, ask the team
before silencing it with `# type: ignore`.

### 4. import-linter: who may talk to whom

**What it does.** The project has three parts:

```
frontend (the Gradio UI)  ──uses──▶  contracts (shared data shapes)  ◀──uses──  backend (the ML, RAG, config)
```

The rules in `pyproject.toml` forbid the shortcuts that would tangle them, for example the frontend
importing `torch` or `khetsetu_backend` directly. This is what lets us later split the app into
two deployments without rewriting it.

**How to use it.**

```bash
make imports
```

**If it complains**, the fix is almost always: move the shared thing into `contracts/`, or call it
through the service interface instead of importing the backend file directly.

### 5. gitleaks: password detector

**What it does.** Scans the files and git history for things that look like API keys, tokens and
private keys. Hugging Face tokens, for example, start with `hf_`.

**Why it matters.** Once a token is pushed to GitHub, assume it is stolen within minutes by bots.
Deleting it later does not help; it stays in history.

**How to use it.**

```bash
scripts/install_gitleaks.sh     # one time: downloads the gitleaks program
make secrets                    # scan the whole git history
```

**The `.env` file.** Real secrets live in `.env` on your own laptop. It is listed in `.gitignore`,
so git never sees it. `.env.example` shows the *names* of the settings with empty values. Never
copy a real value into `.env.example`, `README.md`, a test, or a chat.

**If a secret is ever committed**, do these in order: (1) revoke/rotate the token on the website
first, (2) remove it from the code, (3) tell the team. Rotating is what actually protects you.

### 6. pre-commit: the bouncer

**What it does.** Installs a git hook so that every `git commit` first runs ruff, mypy,
import-linter, gitleaks (on the staged changes) and a few hygiene checks (no files over 500 KB,
no private keys, no trailing whitespace). If anything fails, the commit is refused with a
message.

**How to use it.**

```bash
make hooks          # one time per clone
git commit -m "..." # now checks run automatically
```

**Tips.**

- Hooks may *modify* files (fix whitespace, format code). If the commit is refused for that
  reason, run `git add` on those files again and commit again.
- Do not use `git commit --no-verify` to skip the checks. CI will run the same checks anyway and
  you will only find out later.
- Hooks are optional to install. `make check` before a commit gives you most of the benefit.

### 7. pip-audit: library security

**What it does.** Compares the libraries we use against a public database of known
vulnerabilities.

```bash
make audit
```

**Current status (honest note).** This check is **red right now**: it reports known issues in
`pillow` (the image library) that are only fixed in a newer version that Gradio 6.30.0 does not
allow yet. The options are listed at the bottom of [`docs/ci.md`](ci.md). A red audit is normal
in real projects; the skill is deciding and writing down what to do, not hiding it.

### 8. GitHub Actions ("CI"): the same checks on GitHub

**What it does.** The file `.github/workflows/ci.yml` tells GitHub to run the checks on every push
and pull request, on a clean machine. It has three jobs: `quality` (lint, types, imports, tests),
`audit` and `secrets`.

**Why a second copy of the checks?** Your laptop may have a different setup, or you may have
skipped the hooks. CI is the neutral referee: "does it pass on a clean machine?"

**Important:** nothing has run on GitHub yet because nothing has been pushed. The first run will
tell you if anything is environment-specific. To make a failing check actually *block* merging,
a repo admin has to turn on branch protection once (steps in [`docs/ci.md`](ci.md)).

### 9. uv and the lock file

**What it does.** `uv` installs Python libraries fast and records the exact version of every
library in `uv.lock`. Everyone then gets identical versions.

```bash
make sync                      # install exactly what uv.lock says
uv add some-library            # add a library (updates pyproject.toml and uv.lock)
uv run <command>               # run a command inside the project's environment
```

Always commit `uv.lock` together with `pyproject.toml`.

---

## A daily workflow you can copy

1. `git pull` to get the latest code, then `make sync` if dependencies changed.
2. Make a small change.
3. `make test` while you work, `make check` before you commit.
4. Fix whatever the tools complain about. Use `ruff check --fix` and `ruff format .` first; they
   fix most things for you.
5. Commit with a message that says *why*, not just *what*.
6. Push and open a pull request; wait for the CI checks to turn green.
7. Ask a teammate to read your diff. Review the code, not the person.

## Practices that make you a better developer

- **Small commits and small pull requests.** A 50-line change can be reviewed properly; a
  2000-line one gets a quick "looks good".
- **Make it fail first.** For a bug, write a failing test, then fix it. Now the bug can never come
  back unnoticed.
- **Read the error from the top.** The first error usually causes the rest.
- **Never silence a tool without a reason.** `# noqa` and `# type: ignore` should have a comment
  saying why. If you cannot explain it, fix the code.
- **Treat secrets like toothbrushes.** Never share, never reuse, replace when in doubt.
- **Say "I don't know" in the product.** KhetSetu's rule is to refuse instead of guess when the
  model is not confident. The tests protect that rule. The same attitude applies to your code:
  an honest error beats a silent wrong result.
- **Document decisions, not just code.** Short notes in `docs/` about *why* you chose something
  save the next person (including future you) hours.

## What to ignore at first

You do not need to understand all of this on day one. A sensible order:

1. **Week 1:** `make sync`, `make test`, `make check`. Fix errors using `--fix`.
2. **Week 2:** read type-hint and ruff errors properly; start writing small tests for your own code.
3. **Later:** pre-commit hooks, gitleaks details, branch protection, the audit decisions.

## Quick troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `make: command not found` | `make` not installed | Install it (`sudo apt install make`), or run the underlying `uv run ...` command shown in the `Makefile` |
| `uv: command not found` | uv not installed | See https://docs.astral.sh/uv/ |
| `ruff format --check` fails | code is not formatted | `uv run ruff format .` |
| `ruff check` fails with fixable errors | simple style problems | `uv run ruff check --fix .` |
| mypy error you do not understand | missing/incorrect type hint | Read the line number, check what type the function expects, ask the team |
| import-linter says a contract is broken | UI importing backend internals | Move the shared thing into `contracts/` |
| `make secrets` says gitleaks is missing | not installed yet | `scripts/install_gitleaks.sh` |
| Commit refused by hooks | a check failed or files were auto-fixed | Read the output, `git add` the fixed files, commit again |
| Tests fail only on GitHub | environment difference (Python version, missing env var) | Compare with the CI log; reproduce with `make sync && make check` on a fresh clone |

## Glossary

- **Lint:** automated checking of code for likely mistakes and style problems.
- **Type hint:** a note such as `x: int` saying what kind of value something should be.
- **Test coverage:** the percentage of code lines that run during the tests.
- **CI (continuous integration):** automatically running checks whenever code is pushed.
- **Pull request (PR):** a request to merge your branch into `main`, with room for review.
- **Pre-commit hook:** a script git runs automatically just before creating a commit.
- **Lock file:** a file listing the exact version of every library so installs are identical.
- **Secret:** a password, token or key that must not be shared or committed.
- **Dependency:** a library your project needs.
- **CVE / vulnerability:** a publicly known security weakness in a library.

## Where things live

| Thing | File |
| --- | --- |
| Shortcut commands | `Makefile` |
| Tool settings (ruff, mypy, pytest, import rules) | `pyproject.toml` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| GitHub checks | `.github/workflows/ci.yml` |
| Secret-scan settings | `.gitleaks.toml` |
| Config / environment variables | `.env.example`, [`docs/configuration.md`](configuration.md) |
| Maintainer runbook | [`docs/ci.md`](ci.md) |
| Tests that check the tools themselves | `tests/test_gates_canary.py`, `tests/test_ci_workflow.py` |

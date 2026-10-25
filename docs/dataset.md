# The training dataset

KhetSetu is trained on [`Project-AgML/plant_village_classification`](https://huggingface.co/datasets/Project-AgML/plant_village_classification)
(55,448 leaf photos, 39 classes, about 823 MB). This page explains when the dataset is
downloaded, how we make sure it is the right one, and how to change it.

## Why the dataset is for developers, never for the Space

The deployed Space only needs the trained model. Downloading 823 MB of training images every
time the Space wakes up would make start-up slow and pointless (see `.planning/research/STACK.md`,
finding 5). So:

- Scripts you run on your own machine (training, evaluation, dev tools) **download the dataset
  first**, once.
- The Space and CI **never** download it.

## When is it fetched?

| How you start something | What happens |
| --- | --- |
| `khetsetu data download` | Makes sure the dataset is on disk. Downloads only if files are missing or have the wrong size. Add `--verify` to also re-check every file's sha256 (reads about 860 MB from disk). |
| `khetsetu data inspect` | Same check first, then prints the real counts (rows, classes, shards). |
| Any command decorated with `@requires_dataset` | Same check runs before the command body. |
| `python app.py` on your machine (`KHETSETU_APP_ENV=local`) | Same check runs before the demo is built. |
| `python app.py` on a Space or in CI | Nothing. The downloader is never called. |

Run it twice and the second run says `outcome: cache_hit`: it only compares file sizes on disk and
uses no network at all. A complete local copy works fully offline.

### The mode table

`KHETSETU_DATASET_MODE` (optional) overrides the default that comes from `KHETSETU_APP_ENV`:

| `KHETSETU_APP_ENV` | `KHETSETU_DATASET_MODE` unset | `blocking` | `off` |
| --- | --- | --- | --- |
| `local` | blocking (downloads if needed) | blocking | off |
| `ci` | off | blocking | off |
| `space` | off | **rejected at start-up** | off |

CI sets `KHETSETU_DATASET_MODE=off` in the workflow.

## Where the files live

`data/plant_village_classification/` (the `data/` folder is git-ignored, so the images never get
committed). Inside it the Hugging Face client keeps a hidden `.cache/huggingface/` folder with
resume information; leave it alone. If you already downloaded the dataset by hand into that folder,
KhetSetu recognises it and reuses it.

Using a git worktree? `data/` is untracked, so the worktree has no copy. Either accept one fresh
download or point `KHETSETU_DATA_DIR` at the main checkout's `data` directory (an absolute path).

## How we know it is the right data

The file `backend/src/khetsetu_backend/data/dataset_manifest.json` pins:

- the dataset repository, `Project-AgML/plant_village_classification`;
- one exact commit, `cb08789a92460034ced0449eac1dba72bb4883da` (so upstream edits cannot change
  our data silently);
- for each of the three files (`README.md` and two parquet shards): its size and sha256.

The values were checked twice: against the Hub file metadata for that commit, and by hashing the
local copy. Checks at run time:

- **Every call:** every file exists and has the manifest size.
- **After a download, and with `--verify`:** the sha256 of every file as well.

Any problem raises an error that names the repository, the revision or the offending file (never a
token) and the command exits with code 3. Exit codes: 0 success, 2 invalid configuration, 3 dataset
problem.

## Changing the pinned revision

1. Pick the new commit on the Hub.
2. Update the default `dataset_revision` in `backend/src/khetsetu_backend/config.py` and the line in
   `.env.example`.
3. Regenerate `dataset_manifest.json`: file sizes and sha256 come from
   `HfApi().dataset_info(repo_id, revision=..., files_metadata=True)`; `README.md` is not an LFS file,
   so hash a copy yourself.
4. Run `khetsetu data download --verify`.
5. Update this page.

## Adding a command that needs the dataset

Decorate it, then read the files through `active_dataset()`:

```python
@data_app.command("my-tool")
@requires_dataset
def my_tool() -> None:
    handle = active_dataset()  # verified files: handle.readme, handle.parquet_files
    ...
```

Remember to do this for every future training, evaluation or dev command; nothing checks it
automatically (see "Open items").

## Open items

- The dataset licence and attribution of the AgML mirror are unconfirmed. This must be resolved
  before a model card is published in Phase 3.
- There is deliberately no automatic check that every future command uses `@requires_dataset`
  (the team chose to keep the tooling light); reviewers should look for it.

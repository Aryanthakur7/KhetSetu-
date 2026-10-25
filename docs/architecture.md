# Architecture

KhetSetu is three small Python packages plus one file that connects them. This page describes what exists **today** (the walking skeleton, with fake services) and where real code will plug in later.

## The pieces

```
                    app.py   (composition root)
                   /   |   \
                  /    |    \
     khetsetu_frontend |  khetsetu_backend
        (Gradio UI)    |   (services, config, CLI)
                  \    |    /
                   \   |   /
                khetsetu_contracts
          (typed data + Protocols, no I/O)
```

| Piece | Folder | Job |
| --- | --- | --- |
| `khetsetu_contracts` | `contracts/` | The shared vocabulary: the data types (`DiagnosisRequest`, `DiagnosisResult`, ...) and the Protocols (`DiagnosisService`, `HealthService`) that the UI and the services agree on. |
| `khetsetu_backend` | `backend/` | Everything that does work: settings, logging, the dataset downloader, the `khetsetu` command line and the services that answer requests. No UI code. |
| `khetsetu_frontend` | `frontend/` | The Gradio page. It only sees contract types, never a backend class. |
| `app.py` | repo root | The only file that knows both sides. It builds the services, passes them to the UI and launches the server. |

## Import rules

The arrows above are enforced by `uv run lint-imports` (part of `make check`). The three rules are defined in `pyproject.toml`:

| Rule name | What it protects |
| --- | --- |
| Frontend depends on contracts only | The UI cannot import `khetsetu_backend` (or torch, transformers, huggingface_hub, datasets, chromadb, sentence_transformers). That keeps it movable to its own Space later. |
| Backend has no UI | `khetsetu_backend` cannot import `khetsetu_frontend` or `gradio`, so services stay usable from the command line, training jobs and tests. |
| Contracts is a leaf | `khetsetu_contracts` imports nothing from the other packages and no heavy libraries. It is pydantic plus the standard library. |

## The composition root

`app.py` is where objects are created. `main()` loads and validates the settings, prepares the runtime (locally this makes sure the dataset is on disk; on a Space it does nothing), calls `build_services(settings)` from the backend, passes the result to `build_ui(...)` from the frontend and calls `demo.launch()`.

At the top of `app.py` there is a small path shim (`_ensure_workspace_importable`). On your machine the three packages are installed by `uv sync`, so it does nothing. A Gradio Space installs only third-party libraries from `requirements.txt` and starts `app.py` from the uploaded folder, so the shim adds `contracts/src`, `backend/src` and `frontend/src` to `sys.path`. That is what lets the same file work in both places. [hosting.md](hosting.md) describes how this was rehearsed.

## What happens when a farmer uploads a photo

1. **Upload.** The browser sends the file to Gradio, which rejects anything above the configured size limit.
2. **Handler.** `diagnose_upload` in `frontend/src/khetsetu_frontend/ui.py` reads the bytes into a `DiagnosisRequest`.
3. **Protocol call.** The handler calls `services.diagnosis.diagnose(request)`. It only knows the `DiagnosisService` Protocol.
4. **Fake service.** `FakeDiagnosisService` (in `backend/src/khetsetu_backend/services/fakes.py`) checks the image safely (size, pixel count, decodes) and returns a `DiagnosisResult`. If the image is bad it raises a typed contract error instead.
5. **Presenter.** `presenters.py` turns the result or the error into the Markdown shown to the farmer. A refusal (not a leaf, not sure) can never carry a disease name; the `DiagnosisResult` model itself forbids it.

## Where the real model plugs in (Phase 4)

`build_services` in `backend/src/khetsetu_backend/services/container.py` is the single swap point. Today it returns the fakes. In Phase 4 it will return a real `DiagnosisService` that runs the fine-tuned classifier and the confidence gate. Nothing in the frontend, the contracts or `app.py` has to change, because they only depend on the Protocol.

## Splitting into two Spaces later

If the UI and the backend ever need to run apart, write a small class that implements the same Protocols by calling a backend over HTTP, and a second composition root that passes it to `build_ui`. The frontend code is untouched, and the import rules above guarantee that it never reached into the backend.

## Module map (what exists now)

| Module | Purpose |
| --- | --- |
| `khetsetu_contracts.models`, `.errors`, `.protocols` | Data types, typed errors with a message key, and the service Protocols plus the `Services` container. |
| `khetsetu_backend.config` | `Settings` and `load_settings`: typed configuration that fails fast. |
| `khetsetu_backend.logging_setup` | Standard-library logging setup. |
| `khetsetu_backend.cli` | The `khetsetu` command line. |
| `khetsetu_backend.data` | The pinned dataset manifest and the idempotent downloader. |
| `khetsetu_backend.bootstrap` | `prepare_runtime`: dataset preparation before the app starts (local only). |
| `khetsetu_backend.services` | `FakeDiagnosisService`, `FakeHealthService` and `build_services`. |
| `khetsetu_frontend.ui`, `.presenters`, `.messages` | The Gradio page, the result renderers and the English message table. |
| `scripts/` | Space tooling: `space_bundle.py`, `space_rehearsal.py`, `space_probe.py`. |

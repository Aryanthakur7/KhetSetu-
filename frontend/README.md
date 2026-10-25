# khetsetu-frontend

The Gradio user interface. It talks to services only through the types and Protocols in `khetsetu_contracts`.

## Structure

| File | Purpose |
| --- | --- |
| `src/khetsetu_frontend/ui.py` | `build_ui(services)`: the page, and the handlers `diagnose_upload` and `load_banner`. |
| `src/khetsetu_frontend/presenters.py` | Pure functions that turn contract results and errors into Markdown. No Gradio inside, so they are easy to test. |
| `src/khetsetu_frontend/messages.py` | The English message table and banners. |

## The one rule

The frontend depends on `khetsetu_contracts` and Gradio, **never** on `khetsetu_backend`. The services arrive as an argument to `build_ui`; `app.py` at the repository root creates them. The import rule "Frontend depends on contracts only" fails `make check` if this is broken.

## Running its tests

The tests build the page with stub services, so no backend is needed:

```bash
uv run pytest frontend/tests
```

## Language

Version 1 is English only. Every sentence shown to a farmer lives in `messages.py` and is looked up by a message key, so adding Hindi later is a matter of swapping that mapping, not editing the UI code.

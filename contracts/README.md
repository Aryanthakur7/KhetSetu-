# khetsetu-contracts

The typed seam between the user interface and the services. It holds the data types and the Protocols that both sides agree on, and nothing else.

## What it may import

Only pydantic and the standard library. It must not import `khetsetu_backend`, `khetsetu_frontend`, Gradio, Pillow, torch, transformers or the Hugging Face libraries. This is checked by `uv run lint-imports` (the rule "Contracts is a leaf").

## What is in it

| Name | Kind | Meaning |
| --- | --- | --- |
| `DiagnosisRequest` | data | The image bytes to diagnose. |
| `DiagnosisResult` | data | The outcome: a status, a message key and, only when the status is `DIAGNOSED`, the disease name, crop and alternatives. A refusal cannot carry a disease name. |
| `ScoredLabel`, `GateStatus`, `MessageKey`, `Readiness`, `ReadyState`, `ServiceMode` | data | Supporting types. |
| `ContractError` and its subclasses (`InvalidImageError`, `ImageTooLargeError`, `NotReadyError`) | errors | Typed failures that carry a message key, so the UI never shows exception text. |
| `DiagnosisService`, `HealthService` | Protocols | What a diagnosis service and a health check must offer. |
| `Services` | container | The bundle of services `app.py` passes to the UI. |

## Changing the seam

The frontend, the backend and a possible future HTTP split all depend on these types, so change them together: update the model or Protocol, the fake services in `backend/src/khetsetu_backend/services/fakes.py`, the presenters or messages in the frontend, and the tests, in one change. A new service follows the same path: a Protocol here, a fake in the backend, wiring only in `build_services`, and a presenter in the frontend.

## Tests

`contracts/tests/` (run everything with `make check`, or only this package with `uv run pytest contracts/tests`).

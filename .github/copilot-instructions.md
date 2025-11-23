<!-- .github/copilot-instructions.md - guidance for AI coding agents -->
# Copilot / AI agent instructions for nsw-fuel-api-client

This file gives concise, repository-specific guidance to help an AI coding agent be immediately productive.

**Purpose**: Implement and maintain the NSW FuelCheck API client and related Home Assistant custom integrations. Keep changes minimal and consistent with existing patterns.

**Big picture**:
- **Core API client**: `nsw_fuel/client.py` contains the async HTTP client (`NSWFuelApiClient`) that handles OAuth token fetching (`_async_get_token`) and all endpoints (`_async_request`, `get_fuel_prices`, `get_fuel_prices_within_radius`, etc.).
- **Data models / DTOs**: `nsw_fuel/dto.py` defines NamedTuple/DTO classes (e.g., `Price`, `Station`, `GetFuelPricesResponse`) and `deserialize` methods used throughout the client.
- **Constants & config**: `nsw_fuel/const.py` stores API endpoints and HTTP status constants used by the client.
- **Home Assistant integrations**: `custom_components/nsw_fuel_station/` and `custom_components/nsw_fuel_ui/` implement HA sensors and coordinators that call into the client. These are examples of how the library is used in integrations.

**Key files to inspect when changing behavior**:
- `nsw_fuel/client.py` — primary logic for API calls, error handling and token lifecycle.
- `nsw_fuel/dto.py` — data validation and deserialization; keep DTO shapes in sync with API responses.
- `nsw_fuel/const.py` — endpoint paths and status constants.
- `demo.py` — minimal run example of the client; useful for quick manual checks.
- `tests/` — unit and integration tests (run with `pytest`).
- `custom_components/*` — Home Assistant usage examples and integration-specific patterns.

**Project-specific patterns and conventions**:
- Async-first API: use asyncio/aiohttp patterns. Client methods are `async def` and return typed DTOs.
- Token caching: `_async_get_token` caches a bearer token and sets `_token_expiry`. Respect this logic when modifying authentication.
- Response parsing: `_async_request` normalizes JSON/text responses and uses `_extract_error_details` to surface API messages.
- DTO deserialization: use `.deserialize()` methods on DTO classes rather than reconstructing objects manually.
- Error hierarchy: raise `NSWFuelApiClientAuthError`, `NSWFuelApiClientConnectionError`, or `NSWFuelApiClientError` so callers (including HA integrations) can distinguish behaviors.

**Testing & developer workflows**:
- Virtualenv / install:
  - `python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]` (recommended)
  - Alternatively, `pipenv install --dev` (a `Pipfile` exists) or use `poetry`/`pyproject.toml` as preferred.
- Run demo locally: `python demo.py` (observes `token` / `secrets` files for credentials)
- Run tests: `pytest -q` or `pytest tests/test_client.py -q` for focused runs. See `pytest.ini` for test configuration.

**Integration points & external dependencies**:
- External API: NSW FuelCheck endpoints defined in `nsw_fuel/const.py` and used by `NSWFuelApiClient`.
- Credentials: client id/secret and token artifacts are stored in local `token` / `secrets` files in this repo — do not hardcode secrets into code.
- Home Assistant: custom_components show how the package is consumed by HA; changes to public client APIs may require updates to those integrations.

**How to approach edits and PRs**:
- Keep changes minimal and localized: fix root causes (e.g., deserialization mismatch in `dto.py`) instead of superficial patches.
- Preserve public client API shape unless the change is intentional; update `custom_components/*` accordingly.
- Add/adjust unit tests in `tests/` when behavior changes.

**Example prompts / tasks for the AI agent**:
- "Update `nsw_fuel/dto.py` to accept an optional `price_display` field from the API and add unit tests." — inspect `dto.py`, add field to DTO, update `.deserialize()` and tests under `tests/`.
- "Fix token refresh edge-case in `nsw_fuel/client.py` where expiry isn't respected" — inspect `_async_get_token` and `_async_request` token usage and token-expiry calculation.

If you find an existing `.github/copilot-instructions.md` or AGENT file, merge carefully: keep repo-specific sections above, and preserve any historical guidance.

If anything in this file is unclear or you need more examples (specific DTO fields, token mock patterns, or common failing tests), please ask and I will iterate.

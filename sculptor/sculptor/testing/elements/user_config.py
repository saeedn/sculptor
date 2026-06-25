"""Helpers for toggling user config flags via the API in integration tests.

Each helper does a GET + PUT + reload against ``/api/v1/config`` rather than
driving the settings UI, which has timing issues with Radix controls.
"""

from playwright.sync_api import Page

from sculptor.testing.elements.base import wait_for_tiptap_ready

# Under heavy load the backend can transiently return 500 (e.g. SQLite busy),
# so the config PUT is retried a few times with a short delay between attempts.
_PUT_RETRY_COUNT = 3
_PUT_RETRY_DELAY_MS = 500


def _set_user_config_flag(page: Page, field: str, value: object) -> None:
    """Set a single field on the user config via the REST API, then reload.

    This is more reliable than toggling through the settings UI, which has
    timing issues with Radix controls.
    """
    base_url = page.url.split("#")[0].rstrip("/")
    config_url = f"{base_url}/api/v1/config"

    response = page.request.get(config_url)
    assert response.ok, f"GET /api/v1/config failed: {response.status}"
    current_config = response.json()

    current_config[field] = value
    for _attempt in range(_PUT_RETRY_COUNT):
        put_response = page.request.put(config_url, data={"userConfig": current_config})
        if put_response.ok:
            break
        page.wait_for_timeout(_PUT_RETRY_DELAY_MS)
    assert put_response.ok, f"PUT /api/v1/config failed: {put_response.status}"

    page.reload()
    page.wait_for_load_state("networkidle")

    # Wait for Tiptap to re-initialize after reload (if on a workspace page).
    wait_for_tiptap_ready(page)


def enable_default_fast_mode(page: Page) -> None:
    """Enable the default-fast-mode user preference."""
    _set_user_config_flag(page, "defaultFastMode", True)

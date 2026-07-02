from typing import Any

from playwright.sync_api import Locator
from playwright.sync_api import Page
from playwright.sync_api import expect
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_fixed


class PlaywrightIntegrationTestElement(Locator):
    """
    Represents an element on the page. This subclasses Locator for tooltips/type inference, but all calls are
    caught by __getattr__ and rerouted the self._locator, which is the real object. Internal locator methods or instance
    vars should never reach the actual Locator class being extended here.
    """

    def __init__(self, locator: Locator, page: Page) -> None:
        # Playwright page object stored for when HTML outside this element need to be accessed (e.g. dropdowns)
        self._page = page
        self._locator = locator

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._locator, attr)


# NOTE: These are exceptions to our rule against using .type() in tests.
# Some UI behaviors (mention popups, slash command menus, debounce) are
# triggered by the keyDown/keyUp event sequence that only .type() produces;
# .fill() and insertContent() bypass keyboard events entirely.


def type_with_delay(locator: Locator, text: str, delay: int) -> None:
    """Type text character by character with a delay between keystrokes.

    Used to test behaviors that depend on timing between individual keystrokes,
    such as debounce logic in search inputs.  Playwright's ``fill()`` sets the
    value instantly, bypassing the debounce entirely.
    """
    locator.type(text, delay=delay)


# NOTE: This is an exception to our rule to not use page.evaluate().
# There is no Playwright API to wait for a single animation frame.
# page.wait_for_timeout(N) is the alternative, but requires guessing a
# millisecond value that is either too large (slow tests) or too small (flaky).
# requestAnimationFrame guarantees exactly one render cycle (~16 ms).
def wait_for_one_frame(page: Page) -> None:
    """Wait for one browser animation frame to allow React to re-render.

    Use after programmatically updating content when the test needs a React
    component to have re-rendered before the next interaction.
    """
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")


@retry(
    retry=retry_if_exception_type(AssertionError),
    stop=stop_after_attempt(5),
    wait=wait_fixed(0.25),
    reraise=True,
)
def dismiss_with_escape(dialog: Locator) -> None:
    """Press Escape on a Radix dialog and retry until it closes.

    Radix's ``DismissableLayer`` attaches its Escape keydown listener in a
    ``useEffect``, so an Escape that lands before that effect runs is dropped.
    Retry until the dialog closes.

    The 2 s per-attempt timeout is intentional: combined with the 5-attempt
    retry budget (~11 s total) it replaces a single 30 s ``expect`` wait
    rather than tightening it.
    """
    dialog.press("Escape")
    expect(dialog).not_to_be_visible(timeout=2_000)

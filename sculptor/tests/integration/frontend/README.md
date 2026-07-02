# Frontend Integration Testing Guide

This is a very important guide on rules to follow when writing tests. You should read over this carefully before writing any tests.

## Core Architecture: Page Object Model (POM)

Our integration testing structure uses a POM: HTML pages and elements are represented using classes that **subclass Playwright's native `Page` and `Locator` objects**. This inheritance gives you full access to Playwright's methods while providing our semantic abstractions.

### Key Classes and Structure

**Page Classes** (found in `sculptor/sculptor/testing/pages/`):
- Base class: `PlaywrightIntegrationTestPage` - Wraps Playwright's `Page`
- Concrete implementations provide semantic access to page elements

**Element Classes** (found in `sculptor/sculptor/testing/elements/`):
- Base class: `PlaywrightIntegrationTestElement` - Wraps Playwright's `Locator`
- Concrete implementations group related functionality for complex UI components

**Simple Elements**: Many methods return raw `Locator` objects for basic elements:
```python
def get_start_button(self) -> Locator:
    return self.get_by_test_id(ElementIDs.START_TASK_BUTTON)
```

The custom classes exist to:
- Group related functionality (e.g., all agent-tab-bar operations in one place)
- Prevent raw `get_by_test_id()` calls in test code
- Provide a semantic interface for complex components

### Test IDs

All test IDs are centralized in `sculptor/sculptor/constants.py` in the `ElementIDs` enum (a `StrEnum`):

Frontend components include these as `data-testid` attributes:
```tsx
// Example from a React component
<Button
    data-testid="START_TASK_BUTTON"
    onClick={handleStart}
>
    Start Task
</Button>
```

**Warning**: Be careful where you place the `data-testid` attribute. If it's on a component that doesn't directly render HTML (like a higher-level React component), the test ID might not appear in the final HTML.

## Critical Testing Patterns

### Fixture Imports

Import fixtures explicitly with `# noqa: F401` comments. This helps with IDE navigation since some setups don't automatically recognize fixtures from conftest files.

### Use `expect()` for Assertions and Waits

The `expect()` pattern is the standard way to handle assertions and waiting:

```python
# Always use expect
expect(agent_tabs).to_have_count(1)
expect(workspace_name_input).to_have_value("")
expect(terminal_tab).to_have_attribute("data-dot-status", "running")
expect(changes_tree.get_tree_rows().filter(has_text="hello.txt")).to_be_visible()
```

Avoid using Python's `assert` statements or manual wait loops unless there's an exceptional reason. Both `PlaywrightIntegrationTestElement` and `PlaywrightIntegrationTestPage` inherit from Playwright's classes, so all Playwright methods work seamlessly.

### Timeout Management

- **Default `expect()` timeout**: Configured in `sculptor/tests/integration/frontend/conftest.py` via the `configure_expect_timeout` autouse fixture — 30 seconds by default.
- Avoid defining custom and hardcoded timeouts unless absolutely necessary.

### Element Access Hierarchy

**Important**: Always access elements through the POM hierarchy. Never use raw `get_by_test_id()` calls in test code - if you need access to an element that doesn't have a getter, add a method to the parent POM class (or create it):
```python
# Correct approach
add_workspace_page = PlaywrightAddWorkspacePage(page=sculptor_instance_.page)
add_workspace_page.get_workspace_name_input().fill("My Workspace")

# Avoid direct access
sculptor_instance_.page.get_by_test_id("WORKSPACE_NAME_INPUT").fill("My Workspace")  # Don't do this
```

### User Story Decorator

Tests should use the `@user_story("...")` decorator to document what user-facing behavior the test validates:
```python
from sculptor.testing.user_stories import user_story

@user_story("to see changes in the agent's code")
def test_artifact_panel_diff_tab_basic(sculptor_instance_: SculptorInstance) -> None:
    ...
```


## How to Write a New Integration Test

### Reference Patterns

You can see examples of different testing scenarios:
- `test_home_page.py::test_empty_state_shown_for_new_user` - Verifies the home page starts with no workspaces
- `test_fake_terminal_agent_harness.py::test_fake_terminal_agent_drives_diff_and_tab_dot` - The canonical fake terminal-agent test: drives the agent through the side-effecting DSL and asserts the diff viewer and tab dot react
- `test_multi_agent_workspace.py::test_create_second_agent_in_existing_workspace` - Tests adding agents to a workspace via the agent tab bar
- `test_restarts.py::test_chats_persist_on_restart` - Uses `sculptor_instance_factory_` to assert state survives a backend restart
- `test_keybindings.py` - Settings-page tests that don't require an agent

## Important Implementation Details

### Lazy Locator Evaluation

Playwright locators are lazy - they don't search the DOM until you interact with them. This means you can create locators once and reuse them throughout your test:

```python
agent_tabs = agent_tab_bar.get_agent_tabs()  # Creates locator, doesn't search yet
expect(agent_tabs).to_have_count(1)  # First DOM search
# ... user adds a second agent ...
expect(agent_tabs).to_have_count(2)  # Same locator, fresh search
```

### Elements Outside Their Parent

Some elements (dropdowns, dialogs, modals) render at the page level, not within their parent component:
```python
# Note: using the page, not the tab locator — the context menu renders in a portal
delete_menu_item = page.get_by_test_id(ElementIDs.TAB_CONTEXT_MENU_DELETE)
```

## When to Extend the POM

Consider adding new element classes when you encounter major page components with multiple child elements (like the agent tab bar or the file browser). For simple elements, returning raw Locators is fine.

Add new methods to page or element classes when you need to access an element that doesn't have a getter method.

## Key Principles

- **Proper waits**: Use `expect()` for all waiting and assertions
- **One test, one feature**: Each test should verify a single piece of functionality
- **Readability**: Tests should read like user stories
- **POM encapsulation**: Never access internal locator attributes directly — call methods on POM objects, which auto-route to the underlying locator
- **POM returns data, helpers perform actions**: POM classes should return locators or element objects. Complex actions or wait logic should be helper functions or utilities, not methods on Page or Element subclasses
- **Minimal code changes**: Avoid modifying frontend or backend code in ways that could affect actual functionality. Changes should be isolated to the testing setup as much as possible
- **Use `only()`**: When you expect exactly one element and need to work with it, use `only()` from `imbue_core.itertools` rather than `.first` or indexing. This makes the test's expectations explicit and will fail clearly if the assumption is violated
- **Match existing patterns**: When writing new tests, try to match the existing patterns as closely as possible. If you deviate, there should be a strong reason why

## Running Tests

**CRITICAL: If you are a Claude/Sculptor agent, you MUST use the `/run-integration-test` skill to run integration tests.** Do not run `pytest` or `just test-integration` directly — the skill handles background execution and timeout monitoring, which is required because integration tests can hang indefinitely on failure. Running in foreground will block you with no way to recover.

The Justfile contains the default flags for integration testing as part of the `test-integration` command. Here are some custom arguments you can include:
- `--headed`: Runs the tests with a browser window open. This is the same browser window the test itself interfaces with.
- `-n <N>`: Runs tests with N parallel workers (uses pytest-xdist). By default, tests run sequentially.

Here are some example test commands:
```bash
# Run a specific test with browser visible
just test-integration "sculptor/tests/integration/frontend/test_fake_terminal_agent_harness.py::test_fake_terminal_agent_drives_diff_and_tab_dot" "--headed"

# Run all tests with no parallelism (default behavior)
just test-integration

# Run with 4 parallel workers
just test-integration "sculptor/tests/integration/" "-n 4"
```

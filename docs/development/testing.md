# Testing

## Test Organization

| Type              | Location                       | Naming      |
|-------------------|--------------------------------|-------------|
| Unit tests        | Colocated with source          | `*_test.py` |
| Integration tests | `sculptor/tests/integration/`  | `test_*.py` |

## Running Tests

```bash
just test-unit              # All unit tests (backend, frontend, foundation, sculpt CLI)
just test-unit-backend      # Backend only
just test-unit-frontend     # Frontend only
just test-integration       # All integration tests
```

For specific integration tests:

```bash
just test-integration "sculptor/tests/integration/frontend/test_fake_terminal_agent_harness.py::test_fake_terminal_agent_drives_diff_and_tab_dot"
just test-integration "sculptor/tests/integration/frontend/test_fake_terminal_agent_harness.py" "--headed"  # with browser
XDIST_WORKERS=4 just test-integration "sculptor/tests/integration/"  # override parallel workers (default: -n auto, capped at 3)
```

## Integration Tests

Uses Playwright with a Page Object Model (POM) architecture.

### Key Concepts

- **Page classes** (`sculptor/sculptor/testing/pages/`): wrap Playwright's `Page`
- **Element classes** (`sculptor/sculptor/testing/elements/`): wrap Playwright's `Locator`
- **Test IDs**: centralized in `sculptor/sculptor/constants.py` (`ElementIDs` enum), used as `data-testid` attributes

### Rules

- Always access elements through POM hierarchy — never raw `get_by_test_id()` in tests
- Use `expect()` for assertions and waiting — not Python `assert` or manual loops
- Use `@user_story("...")` decorator to document what the test validates
- Use `start_task_and_wait_for_ready()` to create a workspace with a terminal agent; use the fake terminal agent harness (`sculptor/sculptor/testing/fake_terminal_agent.py`) when the test must drive deterministic agent behavior
- One test, one feature

See [docs/development/review/integration_tests.md](review/integration_tests.md) for detailed anti-patterns with examples (flaky assertions, timeout rules, test isolation).

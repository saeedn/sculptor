import os
import sys


def is_running_within_a_pytest_tree() -> bool:
    """
    This is true if this, or any parent process, is running under pytest.

    This is usually what you want to check
    (eg, this will be true even if you are a separately launched integration server process)
    """
    return "PYTEST_CURRENT_TEST" in os.environ


def is_live_debugging() -> bool:
    """
    Returns True if the current process is being debugged, for example by PyCharm or another IDE.
    """
    # sys.gettrace() is not None would also be true when measuring coverage and in other cases;
    # checking breakpointhook is the narrower signal that is only true when debugging (e.g. in PyCharm).
    return sys.breakpointhook.__module__ != "sys"

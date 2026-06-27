"""Process-wide registry of subscribers for UI actions.

Endpoint code calls publish_ui_action(action); each registered subscriber
callback receives the action. Callbacks are added/removed by the
WebSocket entry point in stream_everything().

Module-level state mirrors local_terminal_manager — both deliberately
skip the Service / service-collection plumbing because there is no
lifecycle work to do.
"""

from queue import Full
from threading import Lock
from typing import Callable

from loguru import logger

from sculptor.web.data_types import OpenFileUiAction

UiAction = OpenFileUiAction
UiActionSubscriber = Callable[[UiAction], object]

_subscribers: set[UiActionSubscriber] = set()
_lock = Lock()


def add_subscriber(subscriber: UiActionSubscriber) -> None:
    with _lock:
        _subscribers.add(subscriber)


def remove_subscriber(subscriber: UiActionSubscriber) -> None:
    with _lock:
        _subscribers.discard(subscriber)


def publish_ui_action(action: UiAction) -> None:
    with _lock:
        subscribers = list(_subscribers)
    for subscriber in subscribers:
        try:
            subscriber(action)
        except Full:
            logger.warning(
                "Dropping {} for workspace {}: subscriber queue full",
                type(action).__name__,
                action.workspace_id,
            )

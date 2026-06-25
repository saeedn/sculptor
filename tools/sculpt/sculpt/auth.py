"""Authentication and shared configuration for the sculpt CLI."""

import os

import httpx
import typer

from sculpt.client import Client
from sculpt.session import SessionTokenError
from sculpt.session import get_session_token

DEFAULT_PORT = 5050


def get_default_base_url() -> str:
    """Get the default base URL, respecting SCULPT_API_PORT if set."""
    port = os.environ.get("SCULPT_API_PORT", str(DEFAULT_PORT))
    return f"http://localhost:{port}"


def get_authenticated_client(base_url: str) -> Client:
    """Create an authenticated client for the Sculptor API."""
    client = Client(base_url=base_url)
    try:
        session_token = get_session_token(client)
    except SessionTokenError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    except (httpx.ConnectError, httpx.ConnectTimeout):
        typer.echo(f"Error: Could not connect to Sculptor server at {base_url}", err=True)
        raise typer.Exit(code=1) from None
    return client.with_headers({"x-session-token": session_token})

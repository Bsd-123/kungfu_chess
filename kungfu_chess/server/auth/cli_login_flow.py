"""The permanent CLI login state machine (Decision 2 -- this is not a
placeholder for a future GUI login screen, it is the authentication
interface for the life of this scope): AWAITING_USERNAME ->
AWAITING_PASSWORD -> AUTHENTICATED. The state machine itself
(`submit_username`/`submit_password`) is decoupled from any I/O so it's
directly unit-testable; `run()` is the thin stdin/stdout driver used by
the real client entry point."""
from __future__ import annotations

import getpass
from enum import Enum, auto
from typing import Callable, Optional

from kungfu_chess.server.auth.session_manager import AuthenticationError, SessionManager


class LoginState(Enum):
    AWAITING_USERNAME = auto()
    AWAITING_PASSWORD = auto()
    AUTHENTICATED = auto()


class CliLoginFlow:
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager
        self.state = LoginState.AWAITING_USERNAME
        self.token: Optional[str] = None
        self.error: Optional[str] = None
        self._username: Optional[str] = None

    def submit_username(self, username: str) -> None:
        if self.state is not LoginState.AWAITING_USERNAME:
            raise ValueError(f"cannot submit username while in state {self.state}")
        self._username = username
        self.error = None
        self.state = LoginState.AWAITING_PASSWORD

    def submit_password(self, password: str) -> bool:
        """Returns True and transitions to AUTHENTICATED on success;
        returns False and drops back to AWAITING_USERNAME (with `error`
        set) on a rejected login, so the caller can re-prompt from the
        top rather than retrying the same username forever."""
        if self.state is not LoginState.AWAITING_PASSWORD:
            raise ValueError(f"cannot submit password while in state {self.state}")
        try:
            self.token = self._session_manager.login(self._username, password)
        except AuthenticationError as exc:
            self.error = str(exc)
            self.state = LoginState.AWAITING_USERNAME
            self._username = None
            return False
        self.state = LoginState.AUTHENTICATED
        return True

    def run(self, input_fn: Callable[[str], str] = input,
            password_input_fn: Optional[Callable[[str], str]] = None,
            output_fn: Callable[[str], None] = print) -> str:
        """Drives the flow over stdin/stdout until AUTHENTICATED,
        returning the session token. `password_input_fn` defaults to
        `getpass.getpass` so a real terminal never echoes the password;
        tests inject a plain stub instead."""
        if password_input_fn is None:
            password_input_fn = getpass.getpass

        while self.state is not LoginState.AUTHENTICATED:
            if self.state is LoginState.AWAITING_USERNAME:
                self.submit_username(input_fn("Username: "))
            else:
                if not self.submit_password(password_input_fn("Password: ")):
                    output_fn(f"Login failed: {self.error}")
        return self.token

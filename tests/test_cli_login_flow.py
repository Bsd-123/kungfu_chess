from kungfu_chess.server.auth.cli_login_flow import CliLoginFlow, LoginState
from kungfu_chess.server.auth.credentials_store import SqliteUserRepository
from kungfu_chess.server.auth.db import open_connection
from kungfu_chess.server.auth.session_manager import SessionManager
from kungfu_chess.server.auth.session_repository import SqliteSessionRepository
from kungfu_chess.server.config import AuthenticationConfig

_AUTH_CONFIG = AuthenticationConfig(pbkdf2_iterations=1000)


def make_flow():
    conn = open_connection(":memory:")
    users = SqliteUserRepository(conn, _AUTH_CONFIG)
    sessions = SqliteSessionRepository(conn)
    manager = SessionManager(users, sessions, _AUTH_CONFIG)
    return CliLoginFlow(manager)


def test_starts_in_awaiting_username():
    flow = make_flow()
    assert flow.state is LoginState.AWAITING_USERNAME


def test_submit_username_transitions_to_awaiting_password():
    flow = make_flow()
    flow.submit_username("alice")
    assert flow.state is LoginState.AWAITING_PASSWORD


def test_successful_password_reaches_authenticated_with_a_token():
    flow = make_flow()
    flow.submit_username("alice")
    accepted = flow.submit_password("hunter2")
    assert accepted is True
    assert flow.state is LoginState.AUTHENTICATED
    assert flow.token is not None


def test_wrong_password_for_known_user_drops_back_to_awaiting_username():
    flow = make_flow()
    flow.submit_username("alice")
    flow.submit_password("hunter2")  # registers alice

    retry = make_flow_with_same_backing(flow)
    retry.submit_username("alice")
    accepted = retry.submit_password("wrong-password")

    assert accepted is False
    assert retry.state is LoginState.AWAITING_USERNAME
    assert retry.error is not None


def make_flow_with_same_backing(flow: CliLoginFlow) -> CliLoginFlow:
    return CliLoginFlow(flow._session_manager)


def test_submit_password_before_username_raises():
    flow = make_flow()
    try:
        flow.submit_password("hunter2")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_run_drives_the_flow_over_injected_io_and_returns_token():
    flow = make_flow()
    usernames = iter(["alice"])
    passwords = iter(["hunter2"])
    messages = []

    token = flow.run(input_fn=lambda _prompt: next(usernames),
                      password_input_fn=lambda _prompt: next(passwords),
                      output_fn=messages.append)

    assert token == flow.token
    assert flow.state is LoginState.AUTHENTICATED
    assert messages == []


def test_run_reprompts_after_a_rejected_password():
    conn_flow = make_flow()
    conn_flow.submit_username("alice")
    conn_flow.submit_password("hunter2")  # registers alice via a throwaway flow

    flow = CliLoginFlow(conn_flow._session_manager)
    usernames = iter(["alice", "alice"])
    passwords = iter(["wrong-password", "hunter2"])
    messages = []

    token = flow.run(input_fn=lambda _prompt: next(usernames),
                      password_input_fn=lambda _prompt: next(passwords),
                      output_fn=messages.append)

    assert token is not None
    assert flow.state is LoginState.AUTHENTICATED
    assert len(messages) == 1
    assert "Login failed" in messages[0]

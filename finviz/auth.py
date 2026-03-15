import os

import requests

from finviz.config import USER_AGENT
from finviz.helper_functions.request_functions import http_request_get

LOGIN_URL = "https://finviz.com/login_submit.ashx"
SCREENER_URL = "https://finviz.com/screener.ashx"


def get_auth_session(username, password, user_agent=USER_AGENT, validate_login=False):
    """
    Create an authenticated Finviz requests.Session.

    Finviz uses an email field in the login form, so username should be the
    account email/username used on the site.
    """

    if not username or not password:
        raise ValueError("username and password are required")

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    response = session.post(
        LOGIN_URL,
        data={"email": username, "password": password},
        headers={"User-Agent": user_agent},
        verify=False,
    )
    response.raise_for_status()

    if validate_login:
        _, url = http_request_get(
            SCREENER_URL,
            session=session,
            parse=True,
            user_agent=user_agent,
        )
        if "/login" in url.lower():
            raise RuntimeError("Finviz login did not produce an authenticated session")

    return session


def get_auth_session_from_env(
    user_agent=USER_AGENT,
    validate_login=False,
    username_var="FINVIZ_USER_NAME",
    password_var="FINVIZ_PASSWORD",
):
    """
    Create an authenticated Finviz session from environment variables.
    """

    username = os.getenv(username_var)
    password = os.getenv(password_var)

    if not username or not password:
        raise ValueError(
            f"{username_var} and {password_var} must be set to create an authenticated session"
        )

    return get_auth_session(
        username=username,
        password=password,
        user_agent=user_agent,
        validate_login=validate_login,
    )


login = get_auth_session
login_from_env = get_auth_session_from_env

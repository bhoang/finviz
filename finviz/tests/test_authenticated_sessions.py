from unittest.mock import Mock, patch

from lxml import html as lxml_html

import finviz
from finviz.main_func import STOCK_PAGE, get_page
from finviz.screener import Screener


def _screener_page():
    return lxml_html.fromstring(
        """
        <html>
          <body>
            <table>
              <tr valign="middle">
                <th>No.</th>
                <th>Ticker</th>
              </tr>
            </table>
          </body>
        </html>
        """
    )


def test_get_auth_session_posts_credentials():
    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_session.post.return_value = mock_response

    with patch("finviz.auth.requests.Session", return_value=mock_session):
        session = finviz.get_auth_session("user@example.com", "secret")

    assert session is mock_session
    mock_session.post.assert_called_once()
    assert mock_session.post.call_args.kwargs["data"] == {
        "email": "user@example.com",
        "password": "secret",
    }


def test_get_auth_session_from_env_reads_env_vars():
    mock_session = Mock()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_session.post.return_value = mock_response

    with patch("finviz.auth.requests.Session", return_value=mock_session), patch.dict(
        "os.environ",
        {"FINVIZ_USER_NAME": "env-user@example.com", "FINVIZ_PASSWORD": "env-secret"},
        clear=False,
    ):
        session = finviz.get_auth_session_from_env()

    assert session is mock_session
    assert mock_session.post.call_args.kwargs["data"] == {
        "email": "env-user@example.com",
        "password": "env-secret",
    }


def test_get_page_cache_isolated_by_session():
    STOCK_PAGE.clear()
    anonymous_page = _screener_page()
    auth_page = _screener_page()
    auth_session = object()

    with patch(
        "finviz.main_func.http_request_get",
        side_effect=[(anonymous_page, "anon"), (auth_page, "auth")],
    ) as mock_request:
        assert get_page("AAPL") is anonymous_page
        assert get_page("AAPL") is anonymous_page
        assert get_page("AAPL", session=auth_session) is auth_page
        assert get_page("AAPL", session=auth_session) is auth_page

    assert mock_request.call_count == 2


def test_screener_uses_authenticated_session_for_paging():
    session = Mock()
    page_content = _screener_page()

    with patch(
        "finviz.screener.http_request_get",
        return_value=(page_content, "https://finviz.com/screener.ashx?v=111"),
    ) as mock_get, patch(
        "finviz.screener.scrape.get_total_rows",
        return_value=40,
    ), patch(
        "finviz.screener.scrape.get_page_urls",
        return_value=["page-1", "page-2"],
    ), patch(
        "finviz.screener.sequential_data_scrape",
        return_value=[[{"Ticker": "AAPL"}], [{"Ticker": "MSFT"}]],
    ) as mock_scrape:
        screener = Screener(filters=["cap_largeover"], session=session)

    assert [row["Ticker"] for row in screener.data] == ["AAPL", "MSFT"]
    assert mock_get.call_args.kwargs["session"] is session
    assert mock_scrape.call_args.kwargs["session"] is session


def test_screener_init_from_url_accepts_session():
    session = Mock()
    page_content = _screener_page()

    with patch(
        "finviz.screener.http_request_get",
        return_value=(page_content, "https://finviz.com/screener.ashx?v=111&f=cap_largeover"),
    ), patch(
        "finviz.screener.scrape.get_total_rows",
        return_value=1,
    ), patch(
        "finviz.screener.scrape.get_page_urls",
        return_value=["page-1"],
    ), patch(
        "finviz.screener.sequential_data_scrape",
        return_value=[[{"Ticker": "AAPL"}]],
    ):
        screener = Screener.init_from_url(
            "https://finviz.com/screener.ashx?v=111&f=cap_largeover&t=AAPL",
            session=session,
        )

    assert screener._session is session
    assert screener.data[0]["Ticker"] == "AAPL"


def test_get_ticker_details_uses_authenticated_session():
    session = Mock()
    page_content = _screener_page()

    with patch(
        "finviz.screener.http_request_get",
        return_value=(page_content, "https://finviz.com/screener.ashx?v=111"),
    ), patch(
        "finviz.screener.scrape.get_total_rows",
        return_value=1,
    ), patch(
        "finviz.screener.scrape.get_page_urls",
        return_value=["page-1"],
    ), patch(
        "finviz.screener.sequential_data_scrape",
        side_effect=[
            [[{"Ticker": "AAPL"}]],
            [{"AAPL": [{"Price": "123.45"}, []]}],
        ],
    ) as mock_scrape:
        screener = Screener(filters=["cap_largeover"], session=session)
        details = screener.get_ticker_details()

    assert details[0]["Price"] == "123.45"
    assert mock_scrape.call_args.kwargs["session"] is session

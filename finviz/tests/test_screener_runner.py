from unittest.mock import Mock, patch

import finviz


def test_load_screener_config_reads_screeners_list(tmp_path):
    config = tmp_path / "screeners.json"
    config.write_text(
        '{"screeners":[{"name":"a","url":"https://finviz.com/screener.ashx?v=111"}]}',
        encoding="utf-8",
    )

    payload = finviz.load_screener_config(config)

    assert len(payload) == 1
    assert payload[0]["name"] == "a"


def test_run_screeners_from_config_uses_env_auth_and_exports(tmp_path):
    config = tmp_path / "screeners.json"
    export_dir = tmp_path / "exports"
    config.write_text(
        '{"screeners":[{"name":"growth","url":"https://finviz.com/screener.ashx?v=111"}]}',
        encoding="utf-8",
    )

    screener = Mock()
    screener.data = [{"Ticker": "AAPL"}]

    with patch("finviz.screener_runner.get_auth_session_from_env", return_value="session") as mock_auth, patch(
        "finviz.screener_runner.build_screener",
        return_value=("growth", screener),
    ) as mock_build:
        results = finviz.run_screeners_from_config(
            path=config,
            auth_from_env=True,
            export_dir=export_dir,
        )

    assert results["growth"] is screener
    mock_auth.assert_called_once()
    assert mock_build.call_args.kwargs["session"] == "session"
    screener.to_csv.assert_called_once_with(str(export_dir / "growth.csv"))


def test_run_screeners_from_config_respects_export_csv_from_config(tmp_path):
    config = tmp_path / "screeners.json"
    config.write_text(
        '{"screeners":[{"name":"breakout","filters":["idx_sp500"],"export_csv":"custom.csv"}]}',
        encoding="utf-8",
    )

    screener = Mock()
    screener.data = [{"Ticker": "MSFT"}]

    with patch(
        "finviz.screener_runner.build_screener",
        return_value=("breakout", screener),
    ):
        finviz.run_screeners_from_config(path=config)

    screener.to_csv.assert_called_once_with("custom.csv")


def test_extract_tickers_returns_ordered_tickers():
    rows = [{"Ticker": "AAPL"}, {"Ticker": "MSFT"}]

    assert finviz.extract_tickers(rows) == ["AAPL", "MSFT"]


def test_extract_tickers_raises_for_missing_ticker():
    try:
        finviz.extract_tickers([{"Symbol": "AAPL"}])
    except ValueError as exc:
        assert "Ticker" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing ticker field")

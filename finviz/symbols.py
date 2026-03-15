def extract_tickers(data_or_screener, ticker_field="Ticker"):
    """
    Extract ordered tickers from a Screener instance or row iterable.

    Raises ValueError if any row is missing the configured ticker field.
    """

    rows = getattr(data_or_screener, "data", data_or_screener)
    tickers = []

    for index, row in enumerate(rows):
        if ticker_field not in row or not row[ticker_field]:
            raise ValueError(
                f"Missing non-empty '{ticker_field}' in screener row at index {index}"
            )
        tickers.append(row[ticker_field])

    return tickers

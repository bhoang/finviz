from datetime import datetime

from finviz.helper_functions.request_functions import http_request_get
from finviz.helper_functions.scraper_functions import get_table

STOCK_URL = "https://finviz.com/quote.ashx"
NEWS_URL = "https://finviz.com/news.ashx"
CRYPTO_URL = "https://finviz.com/crypto_performance.ashx"
STOCK_PAGE = {}


def _stock_cache_key(ticker, session=None):
    return (ticker.upper(), id(session) if session else None)


def get_page(ticker, force_refresh=False, session=None):
    """
    Fetches and caches the stock page for a given ticker.

    :param ticker: stock symbol
    :type ticker: str
    :param force_refresh: force re-fetching the page
    :type force_refresh: bool
    """

    cache_key = _stock_cache_key(ticker, session=session)

    if force_refresh or cache_key not in STOCK_PAGE:
        STOCK_PAGE[cache_key], _ = http_request_get(
            url=STOCK_URL,
            payload={"t": ticker},
            parse=True,
            session=session,
        )

    return STOCK_PAGE[cache_key]


def get_stock(ticker, session=None):
    """
    Returns a dictionary containing stock data.

    :param ticker: stock symbol
    :type ticker: str
    :return dict
    """

    page_parsed = get_page(ticker, session=session)

    data = {}

    # Extract basic info from the new header structure
    ticker_elem = page_parsed.cssselect("h1.quote-header_ticker-wrapper_ticker")
    if ticker_elem:
        data["Ticker"] = ticker_elem[0].text_content().strip()
    else:
        data["Ticker"] = ticker

    company_elem = page_parsed.cssselect(
        "h2.quote-header_ticker-wrapper_company a.tab-link"
    )
    if company_elem:
        data["Company"] = company_elem[0].text_content().strip()
        company_link = company_elem[0].attrib.get("href", "")
        data["Website"] = company_link if company_link.startswith("http") else None
    else:
        data["Company"] = ""
        data["Website"] = None

    quote_links = page_parsed.cssselect("div.quote-links a.tab-link")
    sector_industry_country = []
    for link in quote_links:
        href = link.attrib.get("href", "")
        if "f=sec_" in href or "f=ind_" in href or "f=geo_" in href:
            sector_industry_country.append(link.text_content().strip())

    if len(sector_industry_country) >= 3:
        data["Sector"] = sector_industry_country[0]
        data["Industry"] = sector_industry_country[1]
        data["Country"] = sector_industry_country[2]
    elif len(sector_industry_country) == 2:
        data["Sector"] = sector_industry_country[0]
        data["Industry"] = sector_industry_country[1]
        data["Country"] = ""
    elif len(sector_industry_country) == 1:
        data["Sector"] = sector_industry_country[0]
        data["Industry"] = ""
        data["Country"] = ""

    all_rows = page_parsed.cssselect("tr.table-dark-row")

    for row in all_rows:
        cells = row.cssselect("td.snapshot-td2")
        for i in range(0, len(cells) - 1, 2):
            label_cell = cells[i]
            value_cell = cells[i + 1]

            label = label_cell.text_content().strip()
            value = value_cell.text_content().strip()

            if not label:
                continue

            if label == "EPS next Y" and "EPS next Y" in data:
                data["EPS growth next Y"] = value
                continue
            elif label == "Volatility":
                vols = value.split()
                if len(vols) >= 2:
                    data["Volatility (Week)"] = vols[0]
                    data["Volatility (Month)"] = vols[1]
                elif len(vols) == 1:
                    data["Volatility (Week)"] = vols[0]
                    data["Volatility (Month)"] = vols[0]
                continue

            data[label] = value

    return data


def get_insider(ticker, session=None):
    """
    Returns a list of dictionaries containing all recent insider transactions.

    :param ticker: stock symbol
    :return: list
    """

    page_parsed = get_page(ticker, session=session)

    outer_tables = page_parsed.cssselect("table.styled-table-new")

    insider_table = None
    for table in outer_tables:
        headers = table.cssselect("thead th")
        if headers and any("Insider Trading" in h.text_content() for h in headers):
            insider_table = table
            break

    if insider_table is None:
        old_tables = page_parsed.cssselect("table.body-table.insider-trading-table")
        if old_tables:
            insider_table = old_tables[0]

    if insider_table is None:
        return []

    header_elements = insider_table.cssselect("thead th")
    if header_elements:
        headers = [h.text_content().strip() for h in header_elements]
    else:
        first_row = insider_table.cssselect("tr")[0] if insider_table.cssselect("tr") else None
        if first_row is None:
            return []
        headers = [td.text_content().strip() for td in first_row.cssselect("td")]

    data = []
    tbody = insider_table.cssselect("tbody")
    if tbody:
        rows = tbody[0].cssselect("tr")
    else:
        rows = insider_table.cssselect("tr")[1:]

    for row in rows:
        cells = row.cssselect("td")
        if len(cells) >= len(headers):
            row_data = {}
            for i, header in enumerate(headers):
                row_data[header] = cells[i].text_content().strip()
            data.append(row_data)

    return data


def get_news(ticker, session=None):
    """
    Returns a list of tuples containing (timestamp, headline, url, source) for stock news.

    :param ticker: stock symbol
    :return: list of tuples (timestamp, headline, url, source)
    """

    page_parsed = get_page(ticker, session=session)
    news_table = page_parsed.cssselect("table#news-table")

    if len(news_table) == 0:
        return []

    rows = news_table[0].cssselect("tr")

    results = []
    current_date = datetime.now().date()

    for row in rows:
        try:
            cells = row.cssselect("td")
            if len(cells) < 2:
                continue

            raw_timestamp = cells[0].text_content().strip()
            parsed_timestamp = None

            if "Today" in raw_timestamp:
                time_part = raw_timestamp.replace("Today", "").strip()
                try:
                    parsed_time = datetime.strptime(time_part, "%I:%M%p")
                    parsed_timestamp = datetime.combine(datetime.now().date(), parsed_time.time())
                    current_date = parsed_timestamp.date()
                except ValueError:
                    continue
            elif len(raw_timestamp) > 8 and "-" in raw_timestamp:
                try:
                    parsed_timestamp = datetime.strptime(raw_timestamp, "%b-%d-%y %I:%M%p")
                    current_date = parsed_timestamp.date()
                except ValueError:
                    try:
                        parsed_timestamp = datetime.strptime(raw_timestamp, "%b-%d-%Y %I:%M%p")
                        current_date = parsed_timestamp.date()
                    except ValueError:
                        continue
            else:
                try:
                    parsed_time = datetime.strptime(raw_timestamp, "%I:%M%p")
                    parsed_timestamp = datetime.combine(current_date, parsed_time.time())
                except ValueError:
                    continue

            if parsed_timestamp is None:
                continue

            news_link = cells[1].cssselect("a.tab-link-news")
            if not news_link:
                continue

            headline = news_link[0].text_content().strip()
            url = news_link[0].get("href", "")

            source = ""
            source_elem = cells[1].cssselect("div.news-link-right span")
            if source_elem:
                source_text = source_elem[0].text_content().strip()
                source = source_text.strip("()")

            results.append(
                (
                    parsed_timestamp.strftime("%Y-%m-%d %H:%M"),
                    headline,
                    url,
                    source,
                )
            )
        except (IndexError, AttributeError):
            continue

    return results


def get_all_news(session=None):
    """
    Returns a list of sets containing time, headline and url
    :return: list
    """

    page_parsed, _ = http_request_get(url=NEWS_URL, parse=True, session=session)
    all_dates = [
        row.text_content() for row in page_parsed.cssselect('td[class="nn-date"]')
    ]
    all_headlines = [
        row.text_content() for row in page_parsed.cssselect('a[class="nn-tab-link"]')
    ]
    all_links = [
        row.get("href") for row in page_parsed.cssselect('a[class="nn-tab-link"]')
    ]

    return list(zip(all_dates, all_headlines, all_links))


def get_crypto(pair, session=None):
    """

    :param pair: crypto pair
    :return: dictionary
    """

    page_parsed, _ = http_request_get(url=CRYPTO_URL, parse=True, session=session)
    page_html, _ = http_request_get(url=CRYPTO_URL, parse=False, session=session)
    crypto_headers = page_parsed.cssselect('tr[valign="middle"]')[0].xpath("td//text()")
    crypto_table_data = get_table(page_html, crypto_headers)

    return crypto_table_data[pair]


def get_analyst_price_targets(ticker, last_ratings=5, session=None):
    """
    Returns a list of dictionaries containing all analyst ratings and price targets.

    Each dictionary contains:
    - date: rating date (YYYY-MM-DD format)
    - category: rating category (e.g., "Reiterated", "Upgrade", "Downgrade")
    - analyst: analyst firm name
    - rating: rating action (e.g., "Buy", "Hold", "Sell")
    - target_from: previous price target (if available)
    - target_to: new price target (if available)
    - target: single price target (if only one is provided)

    :param ticker: stock symbol
    :param last_ratings: number of most recent ratings to return
    :return: list of dictionaries
    """

    analyst_price_targets = []

    try:
        page_parsed = get_page(ticker, session=session)

        tables = page_parsed.cssselect("table.js-table-ratings")
        if not tables:
            tables = page_parsed.cssselect("table.fullview-ratings-outer")

        if not tables:
            return []

        table = tables[0]

        tbody = table.cssselect("tbody")
        if tbody:
            rows = tbody[0].cssselect("tr")
        else:
            rows = table.cssselect("tr")

        for row in rows:
            try:
                cells = row.cssselect("td")
                if len(cells) < 4:
                    continue

                rating_data = [cell.text_content().strip() for cell in cells]
                rating_data = [val.replace("â†’", "->").replace("$", "") for val in rating_data if val]

                if len(rating_data) < 4:
                    continue

                try:
                    date_str = datetime.strptime(rating_data[0], "%b-%d-%y").strftime("%Y-%m-%d")
                except ValueError:
                    try:
                        date_str = datetime.strptime(rating_data[0], "%b-%d-%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        continue

                data = {
                    "date": date_str,
                    "category": rating_data[1],
                    "analyst": rating_data[2],
                    "rating": rating_data[3],
                }

                if len(rating_data) >= 5 and rating_data[4]:
                    price_str = rating_data[4].replace(" ", "")
                    if "->" in price_str:
                        parts = price_str.split("->")
                        if len(parts) == 2:
                            try:
                                data["target_from"] = float(parts[0]) if parts[0] else 0.0
                                data["target_to"] = float(parts[1]) if parts[1] else 0.0
                            except ValueError:
                                pass
                    else:
                        try:
                            data["target"] = float(price_str)
                        except ValueError:
                            pass

                analyst_price_targets.append(data)
            except (IndexError, AttributeError):
                continue

    except Exception:
        pass

    return analyst_price_targets[:last_ratings]

import argparse
import json
from pathlib import Path

from finviz.auth import get_auth_session_from_env
from finviz.config import USER_AGENT
from finviz.screener import Screener


def load_screener_config(path="screeners.json"):
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        screeners = payload
    else:
        screeners = payload.get("screeners", [])

    if not isinstance(screeners, list):
        raise ValueError("Config file must contain a 'screeners' list or be a list itself")

    return screeners


def build_screener(definition, session=None, user_agent=USER_AGENT):
    name = definition.get("name")
    if not name:
        raise ValueError("Each screener definition must include a non-empty 'name'")

    common_kwargs = {
        "rows": definition.get("rows"),
        "user_agent": definition.get("user_agent", user_agent),
        "request_method": definition.get("request_method", "sequential"),
        "session": session,
    }

    if definition.get("url"):
        return name, Screener.init_from_url(
            definition["url"],
            rows=definition.get("rows"),
            user_agent=common_kwargs["user_agent"],
            request_method=common_kwargs["request_method"],
            session=session,
        )

    return name, Screener(
        tickers=definition.get("tickers"),
        filters=definition.get("filters"),
        rows=definition.get("rows"),
        order=definition.get("order", ""),
        signal=definition.get("signal", ""),
        table=definition.get("table"),
        custom=definition.get("custom"),
        user_agent=common_kwargs["user_agent"],
        request_method=common_kwargs["request_method"],
        session=session,
    )


def run_screeners_from_config(
    path="screeners.json",
    session=None,
    auth_from_env=False,
    export_dir=None,
    user_agent=USER_AGENT,
):
    if session is None and auth_from_env:
        session = get_auth_session_from_env(user_agent=user_agent)

    results = {}
    screeners = load_screener_config(path)

    if export_dir:
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
    else:
        export_path = None

    for definition in screeners:
        name, screener = build_screener(definition, session=session, user_agent=user_agent)
        results[name] = screener

        target_csv = definition.get("export_csv")
        if export_path is not None:
            target_csv = str(export_path / f"{name}.csv")

        if target_csv:
            target_path = Path(target_csv)
            if target_path.parent != Path("."):
                target_path.parent.mkdir(parents=True, exist_ok=True)
            screener.to_csv(str(target_path))

    return results


def main():
    parser = argparse.ArgumentParser(description="Run multiple Finviz screeners from a JSON config")
    parser.add_argument(
        "--config",
        default="screeners.json",
        help="Path to screener config JSON file",
    )
    parser.add_argument(
        "--auth-env",
        action="store_true",
        help="Authenticate using FINVIZ_USER_NAME and FINVIZ_PASSWORD from the environment",
    )
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Optional directory to export each screener to CSV using its screener name",
    )
    args = parser.parse_args()

    results = run_screeners_from_config(
        path=args.config,
        auth_from_env=args.auth_env,
        export_dir=args.export_dir,
    )

    for name, screener in results.items():
        print(f"{name}: {len(screener.data)} rows")


if __name__ == "__main__":
    main()

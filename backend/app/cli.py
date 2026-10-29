import argparse
import sys
from datetime import date

from app.calendar_sync import push_deadlines
from app.config import get_settings
from app.fiscal.deadlines import fiscal_deadlines


def sync_calendar(year: int) -> int:
    settings = get_settings()
    deadlines = fiscal_deadlines(
        year,
        vat_regime=settings.vat_regime,
        viactt_interval_days=settings.viactt_reminder_interval_days,
    )
    report = push_deadlines(deadlines, settings)
    print(f"Pushed {report.pushed} deadlines for {year} to {report.calendar_url}")
    for failure in report.failed:
        print(f"FAILED {failure}", file=sys.stderr)
    return 1 if report.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pt-tax-assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser(
        "sync-calendar", help="Push fiscal deadlines to Nextcloud via CalDAV"
    )
    sync.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()

    if args.command == "sync-calendar":
        return sync_calendar(args.year)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

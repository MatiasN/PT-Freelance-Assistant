"""Regenerate the synthetic ECB `format=csvdata` fixtures (TARGET business days only).

    uv run python -m tests.fixtures.generate_ecb_fixture

Values are made up but deterministic; the live layout is in ecb_exr_usd_dataonly_live.csv.
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from app.ecb import target_closing_reason

HERE = Path(__file__).parent
HEADER = "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE"
STEPS = (3, -5, 7, -2, 4, -6, 1, 5, -3)


def rows(start: date, end: date, first_value: Decimal) -> list[str]:
    lines = [HEADER]
    value = first_value
    day, i = start, 0
    while day <= end:
        if target_closing_reason(day) is None:
            value += Decimal(STEPS[i % len(STEPS)]) / Decimal(10000)
            i += 1
            lines.append(f"EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,{day.isoformat()},{value}")
        day += timedelta(days=1)
    return lines


def main() -> None:
    (HERE / "ecb_exr_usd_2026.csv").write_text(
        "\n".join(rows(date(2026, 2, 16), date(2026, 4, 10), Decimal("1.0812"))) + "\n"
    )
    (HERE / "ecb_exr_usd_2026-12_2027.csv").write_text(
        "\n".join(rows(date(2026, 12, 1), date(2027, 12, 31), Decimal("1.1200"))) + "\n"
    )


if __name__ == "__main__":
    main()

"""
Read-only sanity check for a production SQLite snapshot (see DEPLOYMENT.md §10).

Answers the question "why does the app report more sales than actually
happened?" by re-deriving every reported number straight from the rows, and
flagging the usual culprits: duplicate submissions, arithmetic drift between
Sale totals and their items, voided-sale handling, timezone day-boundary
slippage, and implausible prices/quantities.

Usage::

    python scripts/db_sanity_check.py path/to/db-YYYYMMDD-HHMMSS.sqlite3
    python scripts/db_sanity_check.py snapshot.sqlite3 --day 2026-08-18

Opens the file read-only and never writes to it. Requires no Django, no
project imports, and no dependencies beyond the stdlib - it runs against a
bare snapshot file.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

# Must match settings.TIME_ZONE - reports and the Flutter app bucket days here.
SHOP_TZ = ZoneInfo("Asia/Beirut")

# Two sales of the identical basket landing within this window are treated as
# one double-submit (retry / double-tap), not two customers.
DUPLICATE_WINDOW_SECONDS = 120


def money(cents: int) -> str:
    """Render integer minor units as a signed decimal amount."""
    return f"{cents / 100:,.2f}"


def round_cents(value: Decimal) -> int:
    """Mirror common.money.round_cents (half away from zero)."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_dt(raw: str) -> datetime:
    """Parse a Django-stored UTC datetime string into an aware datetime."""
    if raw is None:
        return None
    text = raw.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=dt_timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unparseable datetime: {raw!r}")


def local(dt: datetime) -> datetime:
    return dt.astimezone(SHOP_TZ)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# --- loaders --------------------------------------------------------------


def load_sales(conn):
    sales = {}
    for row in conn.execute(
        "SELECT id, created_at, total_revenue_cents, total_cost_cents,"
        " total_profit_cents, status, voided_at, void_reason FROM sales_sale"
    ):
        sale = dict(row)
        sale["created_at_utc"] = parse_dt(row["created_at"])
        sale["created_at_local"] = local(sale["created_at_utc"])
        sale["items"] = []
        sales[row["id"]] = sale

    for row in conn.execute(
        "SELECT id, sale_id, product_id, product_name_snapshot, quantity,"
        " selling_price_cents_snapshot, cost_per_unit_cents_snapshot,"
        " line_revenue_cents, line_cost_cents, line_profit_cents"
        " FROM sales_saleitem ORDER BY id"
    ):
        sale = sales.get(row["sale_id"])
        if sale is not None:
            sale["items"].append(dict(row))
    return sales


# --- checks ---------------------------------------------------------------


def check_overview(conn, sales) -> None:
    section("1. OVERVIEW")
    completed = [s for s in sales.values() if s["status"] == "completed"]
    voided = [s for s in sales.values() if s["status"] == "voided"]
    other = [s for s in sales.values() if s["status"] not in ("completed", "voided")]

    print(f"Sales rows total      : {len(sales)}")
    print(f"  completed           : {len(completed)}")
    print(f"  voided              : {len(voided)}")
    if other:
        print(f"  !! unknown status   : {len(other)} -> {sorted({s['status'] for s in other})}")

    revenue = sum(s["total_revenue_cents"] for s in completed)
    cogs = sum(s["total_cost_cents"] for s in completed)
    print(f"\nAll-time completed revenue : {money(revenue)}")
    print(f"All-time completed COGS    : {money(cogs)}")
    print(f"All-time gross profit      : {money(revenue - cogs)}")
    if voided:
        print(f"(voided revenue excluded   : {money(sum(s['total_revenue_cents'] for s in voided))})")

    if completed:
        first = min(s["created_at_local"] for s in completed)
        last = max(s["created_at_local"] for s in completed)
        print(f"\nFirst completed sale : {first:%Y-%m-%d %H:%M:%S %Z}")
        print(f"Last completed sale  : {last:%Y-%m-%d %H:%M:%S %Z}")

    for table, label in (
        ("catalog_product", "products"),
        ("catalog_category", "categories"),
        ("expenses_expense", "expenses"),
        ("purchases_purchase", "purchases"),
        ("stock_stockmovement", "stock movements"),
    ):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{label:>16} rows : {count}")


def check_daily_breakdown(conn, sales) -> None:
    """Per-day revenue in shop time - this is what the dashboard should show."""
    section("2. DAILY REVENUE (Asia/Beirut days, completed sales only)")
    per_day = defaultdict(lambda: {"revenue": 0, "cost": 0, "count": 0, "items": 0})
    for sale in sales.values():
        if sale["status"] != "completed":
            continue
        day = sale["created_at_local"].date()
        bucket = per_day[day]
        bucket["revenue"] += sale["total_revenue_cents"]
        bucket["cost"] += sale["total_cost_cents"]
        bucket["count"] += 1
        bucket["items"] += len(sale["items"])

    if not per_day:
        print("No completed sales.")
        return

    print(f"{'day':<12}{'sales':>7}{'lines':>7}{'revenue':>14}{'cogs':>14}{'profit':>14}")
    for day in sorted(per_day):
        b = per_day[day]
        print(
            f"{day.isoformat():<12}{b['count']:>7}{b['items']:>7}"
            f"{money(b['revenue']):>14}{money(b['cost']):>14}"
            f"{money(b['revenue'] - b['cost']):>14}"
        )

    # Same buckets in UTC - a divergence means "today" depends on which zone
    # the client used to build its from/to bounds.
    utc_per_day = defaultdict(int)
    for sale in sales.values():
        if sale["status"] == "completed":
            utc_per_day[sale["created_at_utc"].date()] += sale["total_revenue_cents"]
    diverging = [
        d for d in set(per_day) | set(utc_per_day)
        if per_day.get(d, {"revenue": 0})["revenue"] != utc_per_day.get(d, 0)
    ]
    if diverging:
        print(
            f"\nNOTE: {len(diverging)} day(s) bucket differently in UTC vs Asia/Beirut."
        )
        for day in sorted(diverging):
            print(
                f"  {day}: Beirut {money(per_day.get(day, {'revenue': 0})['revenue'])}"
                f"  vs UTC {money(utc_per_day.get(day, 0))}"
            )


def check_totals_match_items(sales) -> list[str]:
    """Sale header totals must equal the sum of their item lines."""
    section("3. SALE TOTALS vs ITEM LINES")
    problems = []
    for sale in sorted(sales.values(), key=lambda s: s["id"]):
        item_revenue = sum(i["line_revenue_cents"] for i in sale["items"])
        item_cost = sum(i["line_cost_cents"] for i in sale["items"])
        if not sale["items"]:
            problems.append(f"Sale #{sale['id']} has NO items but totals {money(sale['total_revenue_cents'])}")
            continue
        if item_revenue != sale["total_revenue_cents"]:
            problems.append(
                f"Sale #{sale['id']}: header revenue {money(sale['total_revenue_cents'])}"
                f" != items {money(item_revenue)}"
            )
        if item_cost != sale["total_cost_cents"]:
            problems.append(
                f"Sale #{sale['id']}: header cost {money(sale['total_cost_cents'])}"
                f" != items {money(item_cost)}"
            )
        if sale["total_profit_cents"] != sale["total_revenue_cents"] - sale["total_cost_cents"]:
            problems.append(f"Sale #{sale['id']}: profit != revenue - cost")

    for sale in sales.values():
        for item in sale["items"]:
            qty = Decimal(str(item["quantity"]))
            expected_rev = round_cents(Decimal(item["selling_price_cents_snapshot"]) * qty)
            expected_cost = round_cents(Decimal(item["cost_per_unit_cents_snapshot"]) * qty)
            if expected_rev != item["line_revenue_cents"]:
                problems.append(
                    f"Sale #{sale['id']} item #{item['id']} ({item['product_name_snapshot']}):"
                    f" price {money(item['selling_price_cents_snapshot'])} x {qty}"
                    f" = {money(expected_rev)} but stored {money(item['line_revenue_cents'])}"
                )
            if expected_cost != item["line_cost_cents"]:
                problems.append(
                    f"Sale #{sale['id']} item #{item['id']}: cost line mismatch"
                    f" (expected {money(expected_cost)}, stored {money(item['line_cost_cents'])})"
                )

    print("OK - every sale total reconciles with its lines." if not problems else "\n".join(problems))
    return problems


def check_duplicates(sales) -> list[str]:
    """Identical baskets submitted back-to-back = retries, not real sales."""
    section("4. SUSPECTED DUPLICATE SUBMISSIONS")
    completed = sorted(
        (s for s in sales.values() if s["status"] == "completed"),
        key=lambda s: s["created_at_utc"],
    )

    def basket(sale):
        return tuple(sorted((i["product_id"], str(i["quantity"])) for i in sale["items"]))

    # Group runs of the same basket where each sale lands within the window of
    # the previous one, so a triple-submit counts as one cluster of 3 (2 extra),
    # not three separate pairs.
    clusters = []
    current = []
    for sale in completed:
        if (
            current
            and basket(sale)
            and basket(sale) == basket(current[-1])
            and (sale["created_at_utc"] - current[-1]["created_at_utc"]).total_seconds()
            <= DUPLICATE_WINDOW_SECONDS
        ):
            current.append(sale)
            continue
        if len(current) > 1:
            clusters.append(current)
        current = [sale]
    if len(current) > 1:
        clusters.append(current)

    findings = []
    inflated = 0
    for cluster in clusters:
        first, last = cluster[0], cluster[-1]
        span = (last["created_at_utc"] - first["created_at_utc"]).total_seconds()
        extra = sum(s["total_revenue_cents"] for s in cluster[1:])
        inflated += extra
        findings.append(
            f"{len(cluster)} identical sales at"
            f" {first['created_at_local']:%Y-%m-%d %H:%M:%S} within {span:.0f}s"
            f" - ids {', '.join('#' + str(s['id']) for s in cluster)},"
            f" {money(first['total_revenue_cents'])} each"
            f" -> {money(extra)} likely double-counted"
        )

    if findings:
        print("\n".join(findings))
        print(f"\nRevenue attributable to suspected duplicates: {money(inflated)}")
    else:
        print("No identical baskets within "
              f"{DUPLICATE_WINDOW_SECONDS}s of each other.")

    # Rapid-fire sales regardless of basket contents - still worth eyeballing.
    bursts = [
        (a, b, (b["created_at_utc"] - a["created_at_utc"]).total_seconds())
        for a, b in zip(completed, completed[1:])
        if (b["created_at_utc"] - a["created_at_utc"]).total_seconds() < 10
    ]
    if bursts:
        print(f"\nSales less than 10s apart ({len(bursts)}):")
        for a, b, gap in bursts:
            print(
                f"  #{a['id']} -> #{b['id']} ({gap:.1f}s):"
                f" {money(a['total_revenue_cents'])} then {money(b['total_revenue_cents'])}"
            )
    return findings


def check_outliers(conn, sales) -> None:
    """Prices/quantities that look like a unit-of-entry mistake."""
    section("5. PRICE / QUANTITY OUTLIERS")
    print("Products (current catalog):")
    print(f"{'id':>4}  {'name':<28}{'sell':>10}{'cost':>10}{'unit':>10}  track_stock")
    for row in conn.execute(
        "SELECT id, name, selling_price_cents, cost_per_unit_cents, selling_unit,"
        " track_stock, is_active FROM catalog_product ORDER BY id"
    ):
        flag = "" if row["is_active"] else "  [archived]"
        print(
            f"{row['id']:>4}  {row['name'][:28]:<28}"
            f"{money(row['selling_price_cents']):>10}{money(row['cost_per_unit_cents']):>10}"
            f"{row['selling_unit']:>10}  {bool(row['track_stock'])}{flag}"
        )

    notes = []
    for sale in sales.values():
        for item in sale["items"]:
            qty = Decimal(str(item["quantity"]))
            price = item["selling_price_cents_snapshot"]
            if qty > 20:
                notes.append(
                    f"Sale #{sale['id']}: quantity {qty} of {item['product_name_snapshot']}"
                    f" (line {money(item['line_revenue_cents'])})"
                )
            if price >= 10000:
                notes.append(
                    f"Sale #{sale['id']}: unit price {money(price)} for"
                    f" {item['product_name_snapshot']} - check for a x100 entry error"
                )
            if price and item["cost_per_unit_cents_snapshot"] > price:
                notes.append(
                    f"Sale #{sale['id']}: {item['product_name_snapshot']} sold below cost"
                    f" (price {money(price)}, cost {money(item['cost_per_unit_cents_snapshot'])})"
                )
            if price == 0:
                notes.append(
                    f"Sale #{sale['id']}: {item['product_name_snapshot']} has a zero price"
                )
    print("\n" + ("\n".join(notes) if notes else "No outlying prices or quantities."))


def check_void_and_stock(conn, sales) -> None:
    section("6. VOIDS & STOCK MOVEMENTS")
    voided = [s for s in sales.values() if s["status"] == "voided"]
    if voided:
        for sale in sorted(voided, key=lambda s: s["id"]):
            when = local(parse_dt(sale["voided_at"])) if sale["voided_at"] else None
            stamp = f"{when:%Y-%m-%d %H:%M}" if when else "(no timestamp)"
            print(
                f"Sale #{sale['id']} voided at {stamp}"
                f" - {money(sale['total_revenue_cents'])}"
                f" - reason: {sale['void_reason'] or '(none)'}"
            )
    else:
        print("No voided sales.")

    inconsistent = [
        s for s in sales.values()
        if (s["status"] == "voided") != (s["voided_at"] is not None)
    ]
    for sale in inconsistent:
        print(f"!! Sale #{sale['id']}: status={sale['status']} but voided_at={sale['voided_at']}")

    rows = list(conn.execute(
        "SELECT type, COUNT(*) n, SUM(quantity_change) q"
        " FROM stock_stockmovement GROUP BY type ORDER BY type"
    ))
    if rows:
        print("\nStock movements by type:")
        for row in rows:
            print(f"  {row['type']:<20}{row['n']:>5} rows, net qty {row['q']}")

    orphans = conn.execute(
        "SELECT COUNT(*) FROM stock_stockmovement m"
        " WHERE m.related_sale_id IS NOT NULL AND m.related_sale_id NOT IN"
        " (SELECT id FROM sales_sale)"
    ).fetchone()[0]
    if orphans:
        print(f"!! {orphans} stock movement(s) reference a missing sale.")


def check_day(sales, day_str: str) -> None:
    """Reproduce the report for one shop day, sale by sale."""
    section(f"7. SALE-BY-SALE DETAIL FOR {day_str} (Asia/Beirut)")
    try:
        target = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Bad --day value {day_str!r}; expected YYYY-MM-DD.")
        return

    start = datetime.combine(target, datetime.min.time(), tzinfo=SHOP_TZ)
    end = start + timedelta(days=1)
    print(f"Half-open range sent to the API: from={start.isoformat()} to={end.isoformat()}")
    print(f"  (in UTC: {start.astimezone(dt_timezone.utc)} .. {end.astimezone(dt_timezone.utc)})\n")

    day_sales = sorted(
        (s for s in sales.values() if start <= s["created_at_local"] < end),
        key=lambda s: s["created_at_utc"],
    )
    if not day_sales:
        print("No sales at all on this day.")
        return

    total = 0
    for sale in day_sales:
        marker = "" if sale["status"] == "completed" else f"  [{sale['status'].upper()} - excluded]"
        print(
            f"#{sale['id']:<4} {sale['created_at_local']:%H:%M:%S}"
            f"  {money(sale['total_revenue_cents']):>10}{marker}"
        )
        for item in sale["items"]:
            print(
                f"        {item['product_name_snapshot'][:26]:<26}"
                f" {item['quantity']:>10} x {money(item['selling_price_cents_snapshot']):>8}"
                f" = {money(item['line_revenue_cents']):>10}"
            )
        if sale["status"] == "completed":
            total += sale["total_revenue_cents"]

    print(f"\nReported revenue for {day_str}: {money(total)}"
          f" across {sum(1 for s in day_sales if s['status'] == 'completed')} completed sale(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path, help="Path to the SQLite snapshot")
    parser.add_argument(
        "--day",
        help="Shop day (YYYY-MM-DD, Asia/Beirut) to break down sale by sale",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No such file: {args.db}", file=sys.stderr)
        return 2

    conn = connect(args.db)
    print(f"Snapshot : {args.db.resolve()}")
    print(f"Size     : {args.db.stat().st_size:,} bytes")
    print(f"Shop TZ  : {SHOP_TZ}")

    sales = load_sales(conn)
    check_overview(conn, sales)
    check_daily_breakdown(conn, sales)
    total_problems = check_totals_match_items(sales)
    duplicates = check_duplicates(sales)
    check_outliers(conn, sales)
    check_void_and_stock(conn, sales)
    if args.day:
        check_day(sales, args.day)

    section("VERDICT")
    if total_problems:
        print(f"- {len(total_problems)} arithmetic inconsistency(ies) between sales and their lines.")
    else:
        print("- Sale arithmetic is internally consistent.")
    print(
        f"- {len(duplicates)} cluster(s) of repeated identical sales - see section 4."
        if duplicates
        else "- No duplicate submissions detected."
    )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

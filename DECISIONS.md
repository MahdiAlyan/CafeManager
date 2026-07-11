# Implementation Decisions

This backend implements the spec in [`README.md`](README.md) exactly, with
the deviations mandated by the build prompt's overrides and a few small
choices made where the spec left room. Overrides win over the spec; the
choices below are documented per the prompt's instruction to record
ambiguities rather than stop.

## Mandated overrides (from the build prompt)

1. **SQLite everywhere** (dev, tests, prod). No PostgreSQL, no
   `DATABASE_URL`, no `psycopg`. DB path is `BASE_DIR/db.sqlite3`,
   overridable via `SQLITE_PATH`. Every write path in the spec
   (`complete_sale`, `void_sale`, `record_purchase`, `adjust_stock`,
   `enable_stock_tracking`) is wrapped in an explicit `transaction.atomic()`
   in the relevant `services.py`; we do **not** rely on `ATOMIC_REQUESTS`.
2. **PythonAnywhere deployment** (no Docker/gunicorn/compose). See
   [`DEPLOYMENT.md`](DEPLOYMENT.md). Prod settings enable
   `SECURE_PROXY_SSL_HEADER`, secure cookies, HSTS, `CSRF_TRUSTED_ORIGINS`,
   and a `collectstatic` target (`STATIC_ROOT = staticfiles/`).
3. **Backups = SQLite file copy** via `python manage.py backup_db`, which
   uses the online backup API (`sqlite3.Connection.backup`) — safe under
   concurrent writes — writes a timestamped file to `~/backups/`, and prunes
   backups older than 30 days. Wired as a PythonAnywhere scheduled task
   (DEPLOYMENT.md). No restore-via-API endpoint (as the spec requires).
4. **DRF ViewSets + routers** for all resources; business-logic operations
   are `@action`s (`SaleViewSet.void`, `ProductViewSet.archive/restore/
   enable_stock_tracking`, `StockViewSet.movements/adjust`). Settings and
   reports are `APIView`/`@api_view` (allowed by the override) to keep their
   URLs exactly as §6. ViewSets stay thin; all transactional logic is in
   `services.py` and unit-tested directly.
5. **Locale**: `TIME_ZONE = Asia/Beirut`, `USE_TZ = True`. `AppSettings`
   pk=1 seeded with `My Coffee Shop` / `USD` / `$` / `2`. CORS wired via an
   optional `CORS_ALLOWED_ORIGINS` env var (empty by default).

## Version note

The spec (§2) lists Python 3.12 / Django 5.x. The provided virtualenv ships
**Python 3.13 / Django 6.0**, so `requirements.txt` targets Django 6.0 and
the code runs on 3.13. Everything is standard Django/DRF with no
version-specific tricks; it also runs on 3.12. DEPLOYMENT.md tells
PythonAnywhere to use the newest available Python 3.x (Django 6.0 needs
≥ 3.12).

## Small choices where the spec left room

- **Default-seeding is per-app.** Each app seeds its own defaults in its own
  data migration (`catalog` → product categories, `expenses` → expense
  categories, `shop_config` → `AppSettings` pk=1). Override 5 phrases this as
  "the same data migration"; keeping each app's seed inside that app avoids
  cross-app model coupling in migrations while producing the identical seeded
  state. All use `get_or_create`, so they're idempotent.
- **Purchase → stock increment amount.** A purchase of
  `quantity_purchased` of `purchase_unit`, each containing
  `units_per_purchase_unit` selling units, adds
  `quantity_purchased * units_per_purchase_unit` **base units** to stock
  (e.g. 2 cartons × 24 = 48 cans). The `purchase` StockMovement records that
  signed base-unit change.
- **`calculated_unit_cost_cents` on a zero denominator returns `0`**,
  matching the Flutter `Money.zero` behaviour (spec §7.3 offered 0-or-400 and
  said to match Flutter).
- **Rounding is half-away-from-zero** (`Decimal` + `ROUND_HALF_UP`) to match
  Dart's `num.round()`, not Python's banker's rounding.
- **`expense-categories` exposes full CRUD** (GET/POST/PATCH/DELETE), not
  only the GET/POST literally listed in §6.6. §8 requires that deleting an
  `ExpenseCategory` still referenced by an `Expense` fails with a clean 400,
  which needs a DELETE route; PATCH comes along with the `ModelViewSet`. The
  `ProtectedError`→400 translation is handled globally
  (`common/exceptions.py`).
- **`ProductUnit`/other enums** are `TextChoices`; `track_stock` and
  `current_stock` are read-only on the product serializer — stock is owned by
  the ledger and the `enable-stock-tracking` action, never by arbitrary
  product writes.
- **CSV sales export excludes voided sales.** §6.8 places the export
  endpoints under Reports, and §7.2 says voided sales are excluded from
  "every report/summary endpoint", so `sales.csv` reflects completed sales
  only. Purchases/expenses exports are unfiltered except by `?from/&to`.
  Each CSV is one row per line item (sales) or per record (purchases,
  expenses); all honour the `?from=&to=` half-open range.
- **Reports `gross_profit_margin_percent`** is a JSON number (float, rounded
  to 2 dp); `quantity_sold` is a decimal **string** (`"2.000"`), consistent
  with DRF's `DecimalField` serialization the Flutter client expects.
- **List pagination** is global (`?page=`, `?page_size=`, envelope
  `{count,next,previous,results}`) per §6, including for small collections
  like categories.
- **Oversell is allowed.** A sale of a tracked product may drive
  `current_stock` negative; the spec never asks the server to block this, and
  the Flutter client did not. The ledger stays correct either way.

## Known gaps (spec §12)

- **No password reset / account recovery** for the single owner (v1
  out-of-scope, spec §4/§12.3). Recreate the account via the Django admin or
  shell if needed.
- **`theme_mode` is client-only** (spec §12.1) — not stored server-side.
- Archived products are excluded from `/api/products/` by default; pass
  `?include_inactive=true` to include them (spec §12.2).

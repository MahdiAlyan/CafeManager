# Radwan Cafe — Backend Specification (Django + DRF)

This document specifies a Python/Django backend that becomes the **sole
source of truth** for the Radwan Cafe coffee shop management app,
replacing the local Drift/SQLite database currently used by the Flutter
client. It is written to be detailed enough for an AI or engineer to
implement the backend from scratch in a **separate project/repo**
(suggested name: `radwan-cafe-backend`). Once the backend exists, the
Flutter app in this repo will be updated to call it instead of its local
database.

> **Scope change note:** the original Flutter app was designed offline-first
> (no accounts, no cloud, local-only storage). This backend is a deliberate
> pivot to a client/server model: the app will require network
> connectivity to function, and gains a real login (single owner) in
> exchange for centralized, multi-device data. Anything not explicitly
> changed here should keep the same business rules already implemented
> and tested in the Flutter app's `core/finance/` layer.

> **See also:** [`BACKEND_INTEGRATION.md`](BACKEND_INTEGRATION.md) — the
> companion document for whoever migrates *this* Flutter codebase to
> consume the backend described below. Implement the backend from this
> file; implement the Flutter-side changes from that one.

---

## Running Locally (implementation)

This repository now **contains** the implemented backend. The spec below is
the contract it fulfils. See [`DECISIONS.md`](DECISIONS.md) for how the
build's SQLite/PythonAnywhere overrides were applied, and
[`DEPLOYMENT.md`](DEPLOYMENT.md) for production.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate                       # creates SQLite db + seeds defaults
python manage.py create_owner --username owner # prompts for a password
python manage.py runserver
```

- API: `http://127.0.0.1:8000/api/` · Swagger UI: `/api/docs/`
- Auth: `POST /api/auth/login/` → `{ token, shop_name }`; send
  `Authorization: Token <token>` on every other request.
- Tests: `pytest`

**Stack as built:** Python 3.13 · Django 6.0 · DRF · SQLite (dev/test/prod)
· `django-environ` config · `drf-spectacular` docs. Project layout:
`config/` (split settings), `apps/` (accounts, catalog, sales, purchases,
expenses, stock, reports, shop_config), `common/` (money, enums, pagination,
date-range, permissions), `tests/`.

---

## 1. Purpose & Non-Goals

**Purpose:** provide a REST API covering products, sales (POS), purchases,
expenses, stock, and financial reporting for one coffee shop owner, with
the exact same accounting model already built into the Flutter app
(capital vs. profit, immutable sale snapshots, void-not-delete, purchase
unit conversion).

**Non-goals for v1:**
- Multi-tenant support (multiple independent shops/owners). Single owner
  only — see §4.
- Real-time push (websockets). Simple request/response REST is enough.
- Payment processing / card integration.
- A built-in "restore full database" API endpoint — server-side backups
  are an ops concern (pg_dump/cron), not an API feature. See §9.

---

## 2. Tech Stack

| Concern            | Choice                                                            |
|---------------------|--------------------------------------------------------------------|
| Language / framework| Python 3.12, Django 5.x, Django REST Framework                    |
| Database            | PostgreSQL in production; SQLite acceptable for local dev/tests   |
| Auth                | DRF `TokenAuthentication` (single owner account)                  |
| Config              | `django-environ` (.env file), 12-factor style                     |
| API docs            | `drf-spectacular` (OpenAPI schema + Swagger UI)                   |
| Testing             | `pytest` + `pytest-django`                                        |
| Task runner (opt.)  | None required for v1 — all operations are synchronous request/response |
| Deployment          | Docker + `gunicorn`, `docker-compose` for local Postgres           |

Do not use Django's default `unittest`-only tooling if `pytest-django`
is available — prefer `pytest` for consistency with the terse, readable
test style already used in the Flutter test suite.

---

## 3. Project Structure

```
radwan-cafe-backend/
├── manage.py
├── pyproject.toml            # or requirements.txt + requirements-dev.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/            # owner login only, no registration flow
│   ├── catalog/             # Category, Product
│   ├── sales/                # Sale, SaleItem + complete_sale/void_sale services
│   ├── purchases/            # Purchase + record_purchase service
│   ├── expenses/             # ExpenseCategory, Expense
│   ├── stock/                 # StockMovement + adjust_stock service
│   ├── reports/               # no models — aggregation views/serializers
│   └── shop_config/          # singleton AppSettings
├── common/
│   ├── money.py               # Money helpers mirroring Flutter's core/utils/money.dart
│   ├── permissions.py         # IsOwner permission class
│   ├── pagination.py
│   └── enums.py               # ProductUnit, SaleStatus, StockMovementType
└── tests/
    └── ... (or co-located tests/ per app, see §10)
```

Each domain app owns its models, serializers, views, and a `services.py`
holding the transactional business logic (mirrors the Flutter
repositories in `lib/features/*/providers/*_repository.dart`) — **keep
business logic out of views/serializers** so it stays independently
testable, the same principle used on the client.

---

## 4. Authentication

Single owner, no self-registration, no multi-user roles.

- The owner account is created via a management command, not a signup
  endpoint:
  ```
  python manage.py create_owner --username owner --password <prompt>
  ```
- `POST /api/auth/login/` — body `{ "username": "...", "password": "..." }`
  → `{ "token": "...", "shop_name": "..." }`. Uses DRF's
  `ObtainAuthToken` view (or a thin custom wrapper that also returns the
  shop name from `AppSettings`).
- `POST /api/auth/logout/` — deletes the caller's token (requires
  `Authorization: Token <token>` header).
- Every other endpoint requires `Authorization: Token <token>` and uses a
  simple `IsAuthenticated` permission (there's only ever one user, so no
  ownership filtering is needed on querysets).
- No password reset flow needed for v1 (single local owner) — document
  this explicitly as a known gap rather than building it.

---

## 5. Data Model

All monetary fields are **integer minor units (cents)**, exactly matching
`Money` in the Flutter app — never use `FloatField` for money. Quantities
that can be fractional (kilograms, partial cartons) use
`DecimalField(max_digits=12, decimal_places=3)`.

### 5.1 Category
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| name | CharField(60) | unique |
| is_default | BooleanField | default False |
| created_at | DateTimeField | auto_now_add |

Seed on first migration (data migration): Beverages, Snacks, Coffee,
Tobacco, Cakes, Other — `is_default=True`.

### 5.2 Product
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| name | CharField(120) | |
| category | FK(Category, on_delete=PROTECT) | |
| selling_unit | CharField(20) | one of `ProductUnit` enum values |
| selling_price_cents | IntegerField | default 0, >= 0 |
| cost_per_unit_cents | IntegerField | default 0, >= 0 |
| barcode | CharField(64), null=True, blank=True | |
| notes | TextField, null=True, blank=True | |
| is_active | BooleanField | default True — **never hard-delete a product referenced by sales**; archive instead |
| track_stock | BooleanField | default False |
| current_stock | DecimalField(12,3) | default 0, denormalized running total kept in sync by the stock ledger |
| low_stock_threshold | DecimalField(12,3), null=True | |
| default_purchase_unit | CharField(20), null=True | prefill for purchase form |
| default_units_per_purchase_unit | DecimalField(12,3) | default 1 |
| created_at / updated_at | DateTimeField | auto_now_add / auto_now |

`ProductUnit` enum: `piece, pack, box, carton, cup, kilogram, gram,
bottle, can, other`.

### 5.3 Sale
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| created_at | DateTimeField | auto_now_add |
| total_revenue_cents | IntegerField | sum of line revenues |
| total_cost_cents | IntegerField | sum of line costs (= capital returned) |
| total_profit_cents | IntegerField | revenue - cost |
| status | CharField(20) | `completed` \| `voided`, default `completed` |
| voided_at | DateTimeField, null=True | |
| void_reason | TextField, null=True, blank=True | |

**Sales are never deleted or edited after creation** except for the
void transition (§7.2).

### 5.4 SaleItem
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| sale | FK(Sale, on_delete=CASCADE, related_name="items") | |
| product | FK(Product, on_delete=PROTECT) | |
| product_name_snapshot | CharField(120) | **immutable** copy of product name at sale time |
| unit_snapshot | CharField(20) | |
| quantity | DecimalField(12,3) | |
| selling_price_cents_snapshot | IntegerField | |
| cost_per_unit_cents_snapshot | IntegerField | |
| line_revenue_cents | IntegerField | |
| line_cost_cents | IntegerField | |
| line_profit_cents | IntegerField | |

**Critical rule**: once written, a `SaleItem`'s snapshot fields are
never recomputed from the current `Product` state. Later edits to a
product's price/cost must not change historical sales — this is the
single most important invariant in the whole system and must be covered
by tests (§10).

### 5.5 Purchase
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| product | FK(Product, on_delete=PROTECT) | |
| purchase_date | DateTimeField | default now, but client-settable |
| quantity_purchased | DecimalField(12,3) | > 0 |
| purchase_unit | CharField(20) | |
| units_per_purchase_unit | DecimalField(12,3) | default 1, e.g. 24 cans per carton |
| total_cost_cents | IntegerField | >= 0 |
| calculated_unit_cost_cents | IntegerField | server-computed, see §7.3 |
| supplier | CharField(120), null=True, blank=True | |
| notes | TextField, null=True, blank=True | |
| product_cost_updated | BooleanField | default False — whether this purchase updated the product's current cost |
| created_at | DateTimeField | auto_now_add |

### 5.6 ExpenseCategory
Same shape as `Category` (id, name unique, is_default, created_at).
Seed: Electricity, Rent, Delivery, Maintenance, Broken items, Expired
items, Free items, Personal use, Cleaning, Equipment, Other.

### 5.7 Expense
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| title | CharField(120) | |
| category | FK(ExpenseCategory, on_delete=PROTECT) | |
| amount_cents | IntegerField | >= 0 |
| occurred_at | DateTimeField | default now, client-settable |
| notes | TextField, null=True, blank=True | |
| created_at / updated_at | DateTimeField | |

Expenses are non-inventory operating costs. **Never** counted as cost of
goods sold; only reduce net profit (§8).

### 5.8 StockMovement
| Field | Type | Notes |
|---|---|---|
| id | AutoField | |
| product | FK(Product, on_delete=PROTECT) | |
| type | CharField(20) | see `StockMovementType` enum below |
| quantity_change | DecimalField(12,3) | signed: positive = increase |
| resulting_stock | DecimalField(12,3) | product's stock immediately after this movement |
| related_sale | FK(Sale, null=True, on_delete=SET_NULL) | |
| related_purchase | FK(Purchase, null=True, on_delete=SET_NULL) | |
| note | TextField, null=True, blank=True | |
| created_at | DateTimeField | auto_now_add |

`StockMovementType` enum and sign convention (must match exactly):
`opening`(+), `purchase`(+), `sale`(−), `sale_reversal`(+),
`manual_increase`(+), `manual_decrease`(−), `damaged`(−), `expired`(−),
`personal_use`(−).

This ledger is the source of truth for stock history; `Product.current_stock`
is a denormalized cache kept in sync inside the same DB transaction as
every movement insert.

### 5.9 AppSettings (singleton)
| Field | Type | Notes |
|---|---|---|
| id | IntegerField, pk, default 1 | enforce singleton (`pk=1` always) |
| shop_name | CharField(120) | default "My Coffee Shop" |
| currency_code | CharField(3) | default "USD" |
| currency_symbol | CharField(8) | default "$" |
| currency_decimal_digits | IntegerField | default 2 (0 for currencies like LBP) |
| updated_at | DateTimeField | auto_now |

(`theme_mode` is a client-only UI preference in the Flutter app — leave
it out of the backend unless you want cross-device theme sync; not
required for v1.)

---

## 6. API Overview

All endpoints are namespaced under `/api/`. All require
`Authorization: Token <token>` except `/api/auth/login/`. Use DRF
`ModelViewSet`s where CRUD is plain; use explicit `APIView`s for
business-logic-heavy actions (completing a sale, voiding a sale,
recording a purchase, adjusting stock).

Standard list endpoints support pagination (`?page=`, `?page_size=`) and,
where noted, `?from=<ISO date>&to=<ISO date>` for date-range filtering
(half-open range: `from` inclusive, `to` exclusive — matches
`DateRange` in the Flutter app).

### 6.1 Auth
```
POST   /api/auth/login/
POST   /api/auth/logout/
```

### 6.2 Categories
```
GET    /api/categories/
POST   /api/categories/
PATCH  /api/categories/{id}/
DELETE /api/categories/{id}/        # 400 if any product references it (PROTECT)
```

### 6.3 Products
```
GET    /api/products/?category=&search=&include_inactive=false
POST   /api/products/
GET    /api/products/{id}/
PATCH  /api/products/{id}/
POST   /api/products/{id}/archive/          # sets is_active=False
POST   /api/products/{id}/restore/          # sets is_active=True
POST   /api/products/{id}/enable-stock-tracking/
       body: { "opening_quantity": 10, "low_stock_threshold": 5 }
```
There is intentionally **no** `DELETE /api/products/{id}/` — products
referenced by historical sales must never be hard-deleted. If a product
has zero references anywhere, deleting via Django admin is acceptable,
but the API only exposes archive/restore.

### 6.4 Sales
```
GET    /api/sales/?from=&to=&status=completed|voided
GET    /api/sales/{id}/                     # includes nested items
POST   /api/sales/
       body: { "items": [ { "product_id": 1, "quantity": 2 }, ... ] }
       -> server looks up EACH product's CURRENT price/cost itself
          (never trust client-sent prices), computes line + sale totals,
          decrements stock for tracked products, all inside one
          transaction.atomic() block. Returns the created sale + items.
POST   /api/sales/{id}/void/
       body: { "reason": "optional string" }
       -> sets status=voided, voided_at=now, reverses any stock taken,
          writes a `sale_reversal` StockMovement per affected line.
```

### 6.5 Purchases
```
GET    /api/purchases/?from=&to=&product=
POST   /api/purchases/
       body: {
         "product_id": 1,
         "quantity_purchased": "1",
         "purchase_unit": "carton",
         "units_per_purchase_unit": "24",
         "total_cost_cents": 1200,
         "supplier": "optional",
         "notes": "optional",
         "update_product_cost": true
       }
       -> server computes calculated_unit_cost_cents = round(total_cost_cents
          / (quantity_purchased * units_per_purchase_unit)); if
          update_product_cost, updates Product.cost_per_unit_cents; if
          Product.track_stock, increments current_stock and writes a
          `purchase` StockMovement. All in one transaction.
```

### 6.6 Expense Categories & Expenses
```
GET/POST     /api/expense-categories/
GET          /api/expenses/?from=&to=&category=
POST         /api/expenses/
GET/PATCH    /api/expenses/{id}/
DELETE       /api/expenses/{id}/           # expenses CAN be deleted (unlike sales)
```

### 6.7 Stock
```
GET    /api/stock/                          # products with track_stock=true
GET    /api/stock/{product_id}/movements/
POST   /api/stock/{product_id}/adjust/
       body: { "type": "damaged", "quantity": "3", "note": "optional" }
       -> quantity is always a positive magnitude; sign is derived from
          `type` per the StockMovementType convention in §5.8.
```

### 6.8 Reports
```
GET /api/reports/summary/?from=&to=
    -> {
         "revenue_cents": ..., "cost_of_goods_sold_cents": ...,
         "capital_returned_cents": ...,   // == cost_of_goods_sold_cents
         "gross_profit_cents": ..., "expenses_cents": ...,
         "net_profit_cents": ...,          // gross_profit - expenses
         "sale_count": ..., "quantity_sold": "...",
         "average_sale_value_cents": ..., "gross_profit_margin_percent": ...
       }
GET /api/reports/products/?from=&to=&sort=revenue|profit|quantity
GET /api/reports/categories/?from=&to=
GET /api/reports/expenses/?from=&to=        # per expense-category totals
GET /api/reports/export/sales.csv?from=&to=
GET /api/reports/export/purchases.csv?from=&to=
GET /api/reports/export/expenses.csv?from=&to=
```
Voided sales are always excluded from every report/summary endpoint.

### 6.9 Settings
```
GET   /api/settings/
PATCH /api/settings/
```
Always operates on the single `AppSettings` row (`pk=1`); no id needed
in the URL.

---

## 7. Business Logic (must match the Flutter app exactly)

Port the pure calculation logic from `lib/core/finance/finance_calculator.dart`
and `lib/core/finance/reports_engine.dart` line-for-line into
`common/money.py` and `apps/reports/services.py`. Keep it in small, pure,
unit-testable functions — do not inline this math into views.

### 7.1 Sale line & totals
```
line_revenue = unit_price_cents * quantity   (round to nearest cent)
line_cost    = unit_cost_cents  * quantity
line_profit  = line_revenue - line_cost

sale_revenue = sum(line_revenue for each item)
sale_cost    = sum(line_cost for each item)
sale_profit  = sale_revenue - sale_cost
```
`POST /api/sales/` must:
1. Reject an empty `items` list (400, not a blank sale).
2. Re-fetch each `Product` server-side inside the transaction and use
   **its current** `selling_price_cents` / `cost_per_unit_cents` as the
   snapshot — never trust a price sent by the client.
3. Wrap sale + all sale items + stock decrements in one
   `transaction.atomic()` block — all or nothing.
4. For each tracked-stock product, write a `sale` StockMovement with
   `quantity_change = -quantity` and update `current_stock` in the same
   transaction.

### 7.2 Voiding a sale
```
POST /api/sales/{id}/void/
```
- Sets `status=voided`, `voided_at=now()`, stores `void_reason`.
- **Does not delete** the sale or its items — audit history must survive.
- For every line item on a tracked-stock product, writes a
  `sale_reversal` StockMovement with `quantity_change = +quantity` and
  restores `current_stock`.
- Voided sales are excluded from `/api/reports/*` and dashboard totals
  (filter `status='completed'` everywhere financial aggregation happens).
- Voiding an already-voided sale is a no-op (idempotent, 200 not 400).

### 7.3 Purchase unit cost conversion
```
calculated_unit_cost_cents = round(
    total_cost_cents / (quantity_purchased * units_per_purchase_unit)
)
```
Example: 1 carton of 24 cans for $12.00 (1200 cents) →
`1200 / (1 * 24) = 50` cents/can. Guard against division by zero
(`quantity_purchased * units_per_purchase_unit <= 0` → return 0 or 400,
pick one and document it — the Flutter side returns `Money.zero` for this
edge case; match that for consistency unless you have a reason not to).

### 7.4 Capital vs. profit reporting model
```
gross_profit = revenue - cost_of_goods_sold
net_profit   = gross_profit - operating_expenses
capital_returned = cost_of_goods_sold          # NOT profit — money recovered from inventory
```
Label net profit in API responses/docs as "potentially available profit"
— do not imply it equals cash on hand, since money may already be spent
or reinvested. This wording matters; keep it consistent with the
Flutter dashboard's disclaimer text.

### 7.5 Manual stock adjustments
```
POST /api/stock/{product_id}/adjust/
```
- `quantity` in the request body is always a **positive magnitude**.
- Sign is derived from `type` per the `StockMovementType.is_increase`
  convention in §5.8 (e.g. `damaged` → subtract, `manual_increase` → add).
- Write one `StockMovement` row and update `Product.current_stock` in
  the same transaction.

---

## 8. Validation Rules

- Money fields: integer, `>= 0`. Reject negative amounts with 400.
- Quantities: `> 0` for cart lines, purchase quantities, and stock
  adjustment magnitudes. `>= 0` allowed only for opening stock quantity
  (a brand-new tracked product can legitimately start at zero).
- A `Sale` must have at least one `SaleItem`.
- `Category`/`ExpenseCategory` names are unique (case-insensitive
  recommended, but exact-match unique is acceptable for v1).
- Deleting a `Category`/`ExpenseCategory` still referenced by a
  `Product`/`Expense` must fail with a clear 400, not a DB integrity
  error leaking to the client (catch `ProtectedError` and translate it).

---

## 9. Backups & Data Safety

Do **not** build an app-level "upload a file to replace the database"
endpoint for a relational Postgres backend — that pattern only made
sense for the old local-SQLite-file design and is unsafe/complex for a
shared server database. Instead:

- Production: scheduled `pg_dump` to object storage (or your host's
  managed Postgres backups), restored via `pg_restore` by an operator,
  not through the API.
- Local dev: `docker-compose` volume is sufficient.
- CSV export endpoints (§6.8) cover the "owner wants their data in a
  spreadsheet" need without touching backup/restore machinery.

---

## 10. Testing Requirements

Mirror the Flutter test suite (`test/business_logic/`) so both sides of
the system agree on the accounting rules. At minimum:

- Sale total calculation (single line, multiple lines, fractional
  quantities).
- Purchase unit conversion (carton→can example from §7.3, including the
  zero-quantity edge case).
- Gross profit / net profit / capital-returned math against the worked
  example from the spec (`revenue=100, cogs=65, expenses=5 → gross=35,
  net=30`).
- Historical snapshot immutability: create a sale, then change the
  product's price/cost, then assert the existing `SaleItem` snapshot
  fields are unchanged.
- Voiding a sale: excludes it from `/api/reports/summary/`, restores
  stock, is idempotent on double-void.
- Expenses reduce net profit but never `cost_of_goods_sold`/gross profit.
- Stock movement sign conventions for every `StockMovementType`.
- `POST /api/sales/` rejects an empty cart (400) and is atomic (a
  simulated failure partway through must not leave a partial sale in the
  DB — test with a transaction rollback assertion, e.g. force an error on
  the last item and assert zero `Sale` rows exist afterward).

Use `pytest-django` with `pytest.mark.django_db`. Prefer testing
`services.py` functions directly (no HTTP layer) for the pure business
logic, and a smaller set of `APIClient`-based tests per endpoint for
request/response shape and auth enforcement.

---

## 11. Environment & Deployment

`.env` (see `.env.example`):
```
DEBUG=False
SECRET_KEY=
ALLOWED_HOSTS=
DATABASE_URL=postgres://user:pass@host:5432/radwan_cafe
CORS_ALLOWED_ORIGINS=
```

- `docker-compose.yml` with two services: `web` (gunicorn) and `db`
  (postgres:16). Run migrations + `create_owner` as part of first
  deploy, not automatically on every container start.
- Seed default categories/expense categories via a **data migration**,
  matching `_seedDefaults` in the Flutter app's `database.dart`, so a
  fresh backend starts with the same defaults the app already expects
  (Beverages/Snacks/Coffee/Tobacco/Cakes/Other, etc.).
- Enable `drf-spectacular`'s schema + Swagger UI at `/api/docs/` so the
  Flutter integration work later has a live, browsable contract instead
  of only this document.

---

## 12. Open Questions to Resolve Before/During Implementation

These were deliberately left as defaults above — revisit if requirements
change:
1. Should `AppSettings` include `theme_mode` for cross-device sync, or
   stay a pure client-side preference? (Currently: client-side only.)
2. Should archived (`is_active=False`) products be filterable/excludable
   from `/api/products/` by default, or always require an explicit
   `include_inactive` flag? (Currently: excluded by default, opt-in via
   query param, matching the Flutter product list screen.)
3. Password reset / account recovery for the single owner — out of
   scope for v1; note it as a known gap rather than silently omitting it.
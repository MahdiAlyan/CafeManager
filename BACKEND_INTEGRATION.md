# Flutter ↔ Backend Integration Guide

This document tells whoever migrates this Flutter app **exactly how** to
switch it from local-only storage (Drift/SQLite) to the Django REST API
specified in [`README.md`](README.md). Read that file first — this one
assumes its data model and endpoint list as given and focuses on what
changes *in this Flutter codebase*, file by file.

Do not start this migration by deleting things. Follow the phased
checklist in §9 so the app keeps compiling and running at every step,
the same discipline used to build the rest of this app.

---

## 1. What changes, what stays the same

| Layer | Stays the same | Changes |
|---|---|---|
| UI screens (`lib/features/*/screens/`) | Almost entirely — widgets read from providers, not from the DB directly | Add pull-to-refresh; add loading/error states for network failures; add a login screen (new) |
| Riverpod providers (`lib/features/*/providers/*_providers.dart`) | Public shape (what screens `ref.watch`) | `StreamProvider` → `FutureProvider`/`AsyncNotifierProvider` (see §5 — Drift's live streams have no REST equivalent) |
| Repositories (`lib/features/*/providers/*_repository.dart`) | Method names/signatures, where possible | Implementation swaps Drift queries for `ApiClient` HTTP calls |
| `core/finance/*.dart` (pure calculation functions) | **Unchanged, keep as-is** | Still used for the POS cart's *local preview total* before submitting; the server remains the authoritative calculator after a sale posts |
| `core/utils/money.dart` | **Unchanged** | None — still the right way to represent money client-side |
| `core/database/*.dart` (Drift) | — | **Deleted** once migration is complete (§9, last step) |
| `core/routing/*.dart` | Route paths stay the same | Add `/login` route + auth redirect guard |
| Settings screen | Shop name / currency editing UX | Backup/Restore section removed (server owns backups now, see README §9); "Export CSV" buttons now call API download endpoints instead of local file writes |

---

## 2. New dependencies

Add to `pubspec.yaml` (remove Drift-only deps in the final cleanup step,
§9):

```yaml
dependencies:
  dio: ^5.7.0                      # HTTP client
  flutter_secure_storage: ^9.2.2   # stores the auth token
  # keep: flutter_riverpod, go_router, intl, file_picker (still used for
  # CSV *download* target selection), csv (only if you keep any
  # client-side CSV formatting — otherwise the server returns ready CSV
  # bytes and this can be dropped)

# remove once migration is complete:
#   drift, sqlite3_flutter_libs, path_provider (unless still needed for
#   caching, see §6), drift_dev, build_runner (if nothing else needs codegen)
```

`dio` over `http`: interceptors make attaching the auth token and
handling 401s in one place trivial (§4).

---

## 3. New core/network layer

Create `lib/core/network/`:

- **`api_client.dart`** — a thin wrapper around `Dio`:
  - `baseUrl` from a build-time config (`--dart-define=API_BASE_URL=...`),
    not hardcoded, so dev/staging/prod can point at different backends.
  - Request interceptor: attaches `Authorization: Token <token>` read
    from secure storage to every request except `/api/auth/login/`.
  - Response interceptor: on `401`, clears the stored token and routes
    to `/login` (see §4).
  - Timeout config (connect + receive, e.g. 10s) so the POS screen never
    hangs indefinitely on a bad connection — surface a clear "couldn't
    reach the server" error instead.

- **`api_exception.dart`** — a typed exception wrapping Dio errors into
  something the UI layer can pattern-match on: `NetworkException`
  (no connectivity / timeout), `ValidationException` (400, carries field
  errors from DRF's error body), `AuthException` (401/403),
  `ServerException` (5xx). Repositories should catch `DioException` and
  rethrow as one of these — screens should never need to know about Dio.

- **`api_endpoints.dart`** — one place listing every path from
  README.md §6 as a constant, so a typo in a URL string is a compile-time
  grep-away, not a runtime 404.

This mirrors how `core/database/database_provider.dart` centralized the
Drift connection — same idea, new transport.

---

## 4. Auth & session

The app currently has **no login** (by design, per the original offline
spec). This is the one genuinely new user-facing flow.

1. **New screen**: `lib/features/auth/screens/login_screen.dart` — shop
   name/logo, username + password fields, "Sign in" button, error text
   for bad credentials or network failure. Keep it as simple as the POS
   screen philosophy demands: minimal typing, big touch targets.
2. **New provider**: `lib/features/auth/providers/auth_providers.dart`
   holding an `AsyncNotifier<AuthState>` (`AuthState` = unauthenticated /
   authenticating / authenticated(token, shopName) / error). On success,
   write the token to `flutter_secure_storage`; on app launch, attempt to
   read a stored token and validate it (e.g. a cheap authenticated
   `GET /api/settings/` call) before deciding whether to show
   `/login` or the app shell.
3. **Router guard**: in `core/routing/app_router.dart`, add a
   `redirect:` callback on `GoRouter` that sends unauthenticated users to
   `/login` and authenticated users away from `/login`. `AppShell`
   (bottom nav) and all existing routes stay children of the same
   `ShellRoute` — only the redirect logic is new.
4. **Logout**: add to the Settings screen (§1) — calls
   `POST /api/auth/logout/`, clears secure storage, router redirect
   kicks in automatically.

There's no self-registration screen — the owner account is provisioned
server-side via the `create_owner` management command (README §4). Don't
build a signup form.

---

## 5. The reactivity problem — read this before touching repositories

This is the single biggest architectural change and the most common
mistake to make during this migration.

**Today**: every list screen (`ProductListScreen`, `SalesHistoryScreen`,
`ExpenseListScreen`, `StockScreen`, `DashboardScreen`, `ReportsScreen`,
...) watches a `StreamProvider` wrapping a Drift `.watch()` query. Drift
automatically re-emits that stream whenever *any* write touches the
underlying table — so completing a sale on the POS screen instantly
updates the Dashboard, Reports, and Stock screens with zero extra code.

**A REST API has no equivalent for free.** `GET /api/sales/` returns a
snapshot, once, on request. If you naively swap `StreamProvider` for
`FutureProvider` and change nothing else, the Dashboard will show stale
data after completing a sale until the user manually backgrounds and
reopens the screen.

**Required approach:**
1. Convert every `StreamProvider<List<T>>` in `lib/features/*/providers/
   *_providers.dart` to `FutureProvider<List<T>>` (or
   `AsyncNotifierProvider` if you want manual `.refresh()`/optimistic
   update methods — preferred for anything the POS screen touches).
2. **Every mutating repository call must invalidate the providers it
   affects.** Concretely:
   - `completeSale()` → invalidate `salesHistoryStreamProvider`
     (renamed, no longer a stream — keep the name or rename to
     `salesHistoryProvider`, your call, but grep all usages),
     `allSaleItemsStreamProvider`, `financeSummaryProvider` family (all
     currently-active date ranges — Riverpod will only recompute ranges
     actually being watched, so this is cheap), and if any tracked
     product was sold, `trackedProductsStreamProvider`.
   - `voidSale()` → same set as above, plus the specific
     `saleStreamProvider(id)`.
   - `recordPurchase()` → `purchasesStreamProvider`,
     `activeProductsStreamProvider`/`allProductsStreamProvider` (cost may
     have changed), `trackedProductsStreamProvider` (stock may have
     changed).
   - `createExpense()` / `updateExpense()` / `deleteExpense()` →
     `expensesStreamProvider`, `financeSummaryProvider` family.
   - `adjustStock()` → `trackedProductsStreamProvider`,
     `stockMovementsStreamProvider(productId)`.
   - Product create/update/archive → `activeProductsStreamProvider`,
     `allProductsStreamProvider`, `categoriesStreamProvider` if a
     category was added inline.

   Do this invalidation **inside the repository method**, not scattered
   across screens, by giving each repository a reference to `Ref` (or by
   moving the invalidation into a thin provider-layer wrapper that calls
   the repository then invalidates — either pattern is fine, pick one and
   apply it consistently). This keeps the "what needs refreshing after X"
   knowledge in one place per action, mirroring how the Drift version
   kept it implicit in the schema.

3. **Add pull-to-refresh** (`RefreshIndicator` wrapping the list/`ListView`
   in each list screen) as a manual escape hatch for any staleness the
   invalidation rules above don't catch (e.g. data changed by hitting
   the API from another device).
4. **Dashboard/Reports specifically**: these already use
   `Provider.family<T, DateRange>` reading `.value` off other providers
   (`lib/features/reports/providers/reports_providers.dart`). Once the
   underlying providers are `FutureProvider`s instead of `StreamProvider`s,
   this family logic still works almost unchanged — `AsyncValue.value`
   behaves the same way whether the upstream is a stream or a future.
   The only change is *when* it recomputes: now only on invalidation
   (step 2) or pull-to-refresh (step 3), not automatically on every DB
   write.
5. Consider `ref.invalidate` on `App` resume (`AppLifecycleState.resumed`)
   for the Dashboard specifically, since it's the first screen the owner
   sees and staleness there is most visible.

**Do not** attempt to build WebSocket/SSE-based live sync for v1 — the
backend spec explicitly excludes it (README §1). The invalidation
approach above is the correct v1 solution.

---

## 6. Offline behavior after the migration

The app is no longer offline-capable by design (this was an explicit,
confirmed trade-off — see README's scope-change note). Still, handle
network failure gracefully rather than crashing or hanging:

- Every `FutureProvider`/`AsyncNotifier` naturally exposes an `error`
  state via `AsyncValue` — the existing `.when(data:, loading:, error:)`
  pattern already used throughout every screen keeps working. Just make
  sure the `error:` branch shows a retry-friendly message
  (`ApiException` from §3 gives you the specific reason to show), not a
  raw stack trace.
- The POS screen (`pos_screen.dart`) is the highest-stakes surface: if
  `completeSale()` fails mid-request, the cart must **not** be cleared
  (currently it's only cleared in the `try` block after success — keep
  that behavior) so the owner can retry without re-entering the whole
  order.
- Optional, not required for v1: a lightweight local cache (e.g. cache
  the last successful `/api/products/` response in `shared_preferences`
  or a tiny Drift/sqflite table used *only* as a read cache) so the
  product grid isn't completely blank on a flaky connection. If you do
  this, keep it clearly separate from "offline-first" — it's a
  performance/resilience cache, not a second source of truth, and it
  must never be written to except by successful API responses.

---

## 7. Model/DTO layer

Drift currently generates data classes (`Product`, `Sale`, `SaleItem`,
etc. in `core/database/database.g.dart`) that the whole app imports
directly. These go away with Drift. Replace them with plain Dart model
classes in each feature's `models/` folder (some already exist, e.g.
`lib/features/sales/models/cart_item.dart` — follow that style):

- `lib/features/products/models/product.dart` — `Product` class with
  `fromJson`/`toJson` matching the API shape in README §5.2. Use
  `json_serializable` + `build_runner` (you're already set up for
  codegen from the Drift days) **or** hand-write `fromJson` — for a
  model set this small, hand-written is fine and keeps `build_runner`
  removable if nothing else needs it.
- Repeat for `Category`, `Sale`, `SaleItem`, `Purchase`,
  `ExpenseCategory`, `Expense`, `StockMovement`, `AppSettings`.
- Keep field names in **camelCase** on the Dart side even though the API
  is snake_case (`sellingPriceCents` ↔ `"selling_price_cents"`) — put the
  translation in `fromJson`/`toJson`, don't leak snake_case into the UI
  layer.
- Money fields decode straight into the existing `Money` class
  (`Money(json['selling_price_cents'] as int)`) — `Money` itself needs no
  changes.
- Quantity fields from the API are JSON numbers or decimal strings
  depending on how DRF serializes `DecimalField` — confirm with the
  actual backend response (DRF's default is a string, e.g. `"2.500"`) and
  parse with `double.parse(...)`, not a naive `as double` cast, or you'll
  get runtime type errors the first time a real backend sends a string.

---

## 8. Repository migration map

For each repository, keep the public method names/signatures where
practical — this is what limits the blast radius on screens/providers.

| Repository file | Old (Drift) | New (API) |
|---|---|---|
| `features/products/providers/products_repository.dart` | `db.select(db.products)...` | `GET /api/products/`, `POST /api/products/`, `PATCH /api/products/{id}/`, `POST /api/products/{id}/archive|restore/`, `POST /api/products/{id}/enable-stock-tracking/` |
| `features/sales/providers/sales_repository.dart` | `db.transaction(...)` building `Sale`+`SaleItem` rows locally | `POST /api/sales/` with `{"items": [{"product_id", "quantity"}]}` — **note the server now computes prices/totals**; `completeSale()` no longer takes price/cost off the local `CartItem`, only `productId` + `quantity`. `CartItem.unitPrice`/`unitCost` become **display-only** (for the local running total, §1), not authoritative. |
| `features/sales/providers/sales_repository.dart` (void) | local `voidSale()` transaction | `POST /api/sales/{id}/void/` |
| `features/purchases/providers/purchases_repository.dart` | local unit-cost calc + writes | `POST /api/purchases/` — server does the unit-cost calc (README §7.3); stop calling `calculatePurchaseUnitCost()` for the *authoritative* value, but you can still call it client-side to show a live preview in the form before submit (same "local preview vs. server truth" pattern as the cart) |
| `features/expenses/providers/expenses_repository.dart` | direct table CRUD | `GET/POST /api/expenses/`, `PATCH/DELETE /api/expenses/{id}/`, `GET/POST /api/expense-categories/` |
| `features/stock/providers/stock_repository.dart` | direct table CRUD | `GET /api/stock/`, `GET /api/stock/{id}/movements/`, `POST /api/stock/{id}/adjust/` |
| `features/reports/providers/reports_providers.dart` | client-side aggregation over locally-streamed tables (`reports_engine.dart`) | `GET /api/reports/summary|products|categories|expenses/?from=&to=` — **the aggregation moves server-side**; `core/finance/reports_engine.dart`'s aggregation functions (`aggregateProductStats`, etc.) become dead code and can be deleted once the reports screen is fully wired to the new endpoints. Keep `finance_calculator.dart` (still used for the local cart preview). |
| `features/settings/providers/settings_repository.dart` | local `AppSettings` row update | `GET/PATCH /api/settings/` |
| `features/settings/providers/backup_repository.dart` | local file export/import | **Delete.** No backend equivalent — remove the "Backup, restore & export" screen's backup/restore buttons entirely (keep CSV export, rewired below) |
| `features/settings/providers/csv_export_repository.dart` | builds CSV client-side from local tables | Call `GET /api/reports/export/sales|purchases|expenses.csv` and save the returned bytes via `file_picker`'s `saveFile` (same UX, different byte source) |

---

## 9. Phased migration checklist

Do these in order; the app should build and run after every phase.

1. Add `dio`, `flutter_secure_storage`; scaffold `core/network/` (§3).
   Nothing consumes it yet — just get it compiling.
2. Build the login screen + auth provider + router redirect (§4). App
   now requires login but every existing screen still reads local Drift
   data — this is the point where the app temporarily has *both* a login
   gate and a local DB, which is fine as an intermediate state.
3. Introduce plain Dart model classes (§7) alongside the existing Drift
   ones — don't delete Drift's generated classes yet.
4. Migrate **one feature at a time**, starting with Products (simplest,
   no cross-feature invalidation fan-out), then Expenses, then
   Purchases, then Stock, then Sales/POS (most invalidation fan-out, do
   it once you've proven the pattern elsewhere), then Reports/Dashboard,
   then Settings. For each feature:
   a. Rewrite the repository to call the API (§8).
   b. Convert its `StreamProvider`s to `FutureProvider`/`AsyncNotifier`
      (§5) and add the invalidation calls for every mutation.
   c. Add pull-to-refresh to its list screen(s).
   d. Update/replace its unit tests (§10) and manually smoke-test the
      screen against a running backend before moving to the next
      feature.
5. Once every feature is migrated: delete `core/database/`, remove
   `drift`/`sqlite3_flutter_libs`/`drift_dev` from `pubspec.yaml`, delete
   `features/settings/providers/backup_repository.dart` and the
   Backup/Restore UI section, run `flutter pub get`, then `flutter
   analyze` and fix whatever the deletions surface.
6. Final pass: re-run the full test suite, re-verify an Android debug
   build (`flutter build apk --debug`), and manually walk the golden
   path once more (login → add product → complete a sale → check
   dashboard updates → view sale in history → void it → check dashboard
   updates again → record a purchase → check product cost updated →
   check reports) since this is exactly the kind of change that can look
   fine per-screen while breaking the cross-screen reactivity that made
   the original app feel instant.

---

## 10. Testing changes

- `test/business_logic/repositories_test.dart` currently spins up
  `AppDatabase.forTesting(NativeDatabase.memory())` and exercises real
  repositories against an in-memory Drift DB. Once repositories talk to
  the API, replace this pattern with either:
  - a fake `ApiClient` (implements the same interface, returns canned
    JSON) injected into each repository under test, or
  - `dio`'s `DioAdapter` test double (via a mocking package) if you want
    to assert exact request shapes.
  Keep the *test names and scenarios* — empty cart rejected, historical
  snapshot immutable after product edit, void excludes from totals,
  purchase unit conversion, expense reduces net profit only — they're
  still the right things to verify, just against a mocked HTTP layer
  instead of a real embedded DB.
- `test/business_logic/finance_calculator_test.dart` and
  `test/business_logic/money_test.dart` need **no changes** — they test
  pure functions with no I/O dependency, and those functions are still
  used client-side for preview totals (§1).
- `test/widget_test.dart` needs a fake/mocked `ApiClient` override
  instead of a Drift `databaseProvider` override, and should additionally
  cover the new auth redirect (unauthenticated → `/login`).
# Plan: Single aggregated CLOSE order for a Portfolio bucket

## Repository / branch workflow (prerequisite — do this BEFORE coding)
The default branch is **`main`** (no `master` branch exists locally or on `origin`; `origin/HEAD ->
origin/main`). The feature must be developed on a dedicated branch, **not** directly on `main`.
Before branching, push the current working-tree baseline files that are required but not part of
this feature:
- `src/paytm/db/payTmMoney.db` (binary, ~1.6MB) — **must** be pushed.
- `utils/chromedriver.exe` (binary, ~18MB) — **preferably** pushed as well.
- (Optionally also the in-progress `dataset/*` scrip-master / security-master updates.)

Baseline status: commit `3af8145 "Baseline: update Paytm Money DB and chromedriver"` already exists
on `main` and **already contains both `src/paytm/db/payTmMoney.db` and `utils/chromedriver.exe`** (both
tracked). It is currently 1 commit ahead of `origin/main` and unpushed.

Steps:
1. Push the baseline: `git push origin main` (pushes commit `3af8145`). Do **not** stage/commit the
   unrelated working-tree changes (`src/paytm/appPaytm.py`, `dataset/*`) — they are separate work and
   must stay out of the baseline.
   - **Permission note:** in this session `git add/commit/push` are denied by the configured rule
     (`git *` deny, with only read-only `git` subcommands allowed). Do the push manually (or after
     granting git write permission) before branching.
 2. `git switch -c feature/portfolio-aggregated-close main`
 3. Implement tasks 1–4 below **on this branch**.
 4. Validate (unit + manual) on the branch.
 5. Open a PR / merge back to `main` when complete — do **not** commit directly to `main`.

## Context (why 10 orders appear today)
- `requestClosePortfolioBucket` (`ui/src/App.jsx:645`) loops over **every leg** of a bucket and calls
  `POST /api/trades/{id}/close` (App.jsx:660-666).
- `TradeService.close_trade` (`src/trade_manager/service.py:698`) only sets `REC_STATUS='CLOSE'`.
- The running broker app reacts via `__followOrders` → `__executeClosureSeq` → `__closePosition`
  (`src/common/workflow.py:739`), which places **one SELL order per record** (workflow.py:791).
- Result: a stock bought weekly for 10 weeks = 10 records = 10 SELL orders = 10x brokerage.

## Chosen approach (simplified, reuses existing close path)
Instead of distributing one fill across many legs, we **collapse the bucket into a single synthetic
record** and let the app's existing `REC_STATUS='CLOSE'` machinery place exactly one order.

Endpoint `POST /api/portfolio/close` does, in one synchronous call:
1. **Validate** the bucket (`close_portfolio_bucket`):
   - every leg `PRODUCT == 'CASH'`,
   - all share the same non-empty `SECURITY_ID`,
   - every leg is **fully held**: `POS_HOLD_STATUS == 'POSITION'`, `POS_HOLD_QTY > 0`, and no
     `OPEN_ORDERS` with `ORDER_STATUS == 'OPEN'` (so we never delete a leg with an in-flight BUY),
   - `REC_STATUS in ('OPEN','PARTIAL_CLOSE')`.
   - If validation fails → return `ValidationError` and the UI **falls back** to today's per-leg loop.
2. **Compute** `total = sum(leg['POS_HOLD_QTY'])` over the validated legs.
 3. **Create one aggregated record** reusing the existing `already_held` creation path
    (`apply_held_qty_to_trade`, service.py:72 / `create_trade`, service.py:698-area):
    - `MKT_SYMBOL`, `SECURITY_ID` from the legs (same), `PRODUCT='CASH'`, `BUY_SELL='BUY'`,
    - `QTY = POS_HOLD_QTY = total`,
    - representative `STRATEGY`/`SOURCE` (e.g. newest leg, or `'AGGREGATED'`/`'MANUAL'`),
    - **`REC_TIME` must be a real, valid time — NOT the placeholder `"xx:xx"`** (see REC_TIME note
      below). Use `datetime.now().strftime("%H:%M")` (or the current real time) and ensure the
      `(MKT_SYMBOL, STRATEGY, REC_DATE, REC_TIME)` tuple is unique (a current timestamp makes
      collision with an existing/sibling record effectively impossible). Do **not** copy `REC_TIME`
      from a leg, since legs frequently carry the `"xx:xx"` placeholder.
    - representative `REC_DATE` (e.g. oldest leg = acquisition date) is fine as a date string.
    - this yields `POS_HOLD_STATUS='POSITION'` with a dummy filled `OPEN_ORDERS` entry.
4. **Mark the new record for closing**: set `REC_STATUS='CLOSE'`, `updateDb`, `_invalidate()`.
   The running app's next reconcile sees `REC_STATUS='CLOSE'` + `POS_HOLD_STATUS='POSITION'` and
   calls `__closePosition` → **exactly one SELL market order** for `total` (workflow.py:885/891/
   841/739). No `workflow.py` / `appPaytm.py` changes are required.
 5. **Delete the original legs** so the DB does not double-count buys+sells:
    `self.__store.removeFromDb(decode_trade_id(id))` for each old leg, then `_invalidate()`.
    - **Use each leg's exact stored `REC_TIME`** (passed through `decode_trade_id`) — this may be the
      `"xx:xx"` placeholder for many legs; the removal query keys on the literal string, so no
      parsing is involved and deletions are unaffected by non-time `REC_TIME` values.
    (Deletion happens in the same endpoint call, so the UI/app never observes the intermediate
    double-count state.)

### Why this works / ties to existing code
- `__followOrders` (workflow.py:885): `REC_STATUS in ('PARTIAL_CLOSE','CLOSE')` →
  `__executeClosureSeq` → `__closePosition`, which places one order per record.
- `__closePosition` (workflow.py:778-800): `closeQty = posHoldQty` (full), one `placeOrder` call.
- After fill, `__getPosStatus` (workflow.py:497) sets the synthetic record to
  `POS_HOLD_STATUS='CLOSE'`. End state: one record showing bought `total` and sold `total`.

### Refinements vs. the raw proposal
- The raw idea suggested only setting old legs to `POS_HOLD_STATUS='CLOSE'`. That does **not** stick:
  `__getPosStatus` (workflow.py:497-523) recomputes `POS_HOLD_QTY` from orders and flips a leg with
  `POS_HOLD_QTY>0` back to `POSITION`. So we **delete** the old legs (proposal's step 3) instead.
- We require fully-held legs so deletion can't orphan an in-flight BUY order.

## Implementation tasks
1. `src/trade_manager/models.py`: add `PortfolioCloseRequest(BaseModel)` with
   `member_ids: list[str]` and `total_qty: int`.
2. `src/trade_manager/service.py`: add `close_portfolio_bucket(member_ids, total_qty)`:
   - load members via `get_trade`; validate (see above);
   - build the aggregated doc (reuse the `already_held` creation helper used by `create_trade`);
   - `insertDb`, then set `REC_STATUS='CLOSE'`, `updateDb`, `_invalidate()`;
   - `removeFromDb(decode_trade_id(id))` for each old leg; `_invalidate()`;
   - return `{agg_trade_id, member_count, total_qty, security_id}`.
3. `src/trade_manager/api.py`: `POST /api/portfolio/close` → `service.close_portfolio_bucket(...)`;
   wrap `ValidationError` with `_validation_http`.
4. `ui/src/App.jsx` `requestClosePortfolioBucket` (line 645): replace the per-leg loop with one
   `POST /api/portfolio/close` (`member_ids`, `total_qty: bucket.POS_HOLD_QTY`); on 422/error fall
   back to the current per-leg loop; update `closePortfolioSummaryLines` (App.jsx:109) to say
   "single aggregated SELL order for N shares across M legs".
- **No changes** to `src/common/workflow.py` or `src/paytm/appPaytm.py` / `appIciciBreeze.py`.

## Risks / edge cases
- **Partial fill / rejection:** handled by the existing `__closePosition` retry + `__getPosStatus`
  (same as today's per-record behavior) — the synthetic record is re-closed for any remainder.
- **Double-count:** avoided by deleting the original legs within the same synchronous call.
- **In-flight BUY on a leg:** excluded by the fully-held validation; such buckets fall back to
  per-leg close.
 - **Mixed product / different SECURITY_ID:** validation fails → per-leg fallback (FnO lots, which
   are not fungible, are never aggregated).
 - **`REC_TIME` is often the placeholder `"xx:xx"`, not a time** (default in `models.py:16`;
   `migrate_core_to_db.py:37`; many core/holdings records). The aggregated record must therefore be
   created with a **real** `REC_TIME` (current `HH:MM`) to stay unique and unambiguous; and the
   original legs must be deleted using their **exact stored** `REC_TIME` (which may be `"xx:xx"`).
   Note: `workflow.py` only `strptime`-parses `REC_TIME` for non-CASH paths (`__isLateAdd`,
   workflow.py:416) and for the non-CASH match branch (`__sameRecFromDiffSource`, workflow.py:383), so
   a CASH record with `"xx:xx"` never hits that parser — but we still set a real time on the synthetic
   record to avoid any ambiguity and key collisions.
- **App not running:** the aggregated record persists with `REC_STATUS='CLOSE'` and is closed on the
  app's next startup (same dependency model as today's `close_trade`).
- **Reporting:** the aggregated record's `STRATEGY`/`SOURCE`/`REC_DATE` are synthetic; accept this
  trade-off (history of individual legs is dropped). If per-leg history must be preserved later, the
  alternative is the "poll + distribute fill across legs" design (see note below).

## Validation
- Reuse `payTmMoneyMock` (`findOrderStatusAndQtyInfo`). Create 10 CASH records for the same
  `SECURITY_ID`, each `POS_HOLD_STATUS='POSITION'`, `POS_HOLD_QTY=100`.
   - Call `close_portfolio_bucket` with all 10 ids → assert **exactly one** `placeOrder` call with
     `qty=1000`; assert the 10 original records are gone (`getDb` returns only the aggregated one);
     assert aggregated record has `REC_STATUS='CLOSE'`, `POS_HOLD_STATUS='POSITION'`, `POS_HOLD_QTY=1000`.
   - Assert the aggregated record's `REC_TIME` is a real time string matching `^\d{2}:\d{2}$` (never
     `"xx:xx"`), and that its `(MKT_SYMBOL, STRATEGY, REC_DATE, REC_TIME)` tuple is unique in `getDb`.
   - Seed at least one original leg with `REC_TIME="xx:xx"`; assert that leg is still correctly
     deleted (deletion keys on the literal stored string, not a parsed time).
  - Mock the fill → run app reconcile → assert aggregated record `POS_HOLD_STATUS='CLOSE'`,
    `POS_HOLD_QTY=0`, single `CLOSE_ORDERS` entry of qty 1000.
- Negative: bucket containing one `OPTION` leg → `ValidationError`, UI falls back to 10 orders.
- Negative: a leg with a pending open BUY order → `ValidationError`, fallback.
- Manual: run `appPaytm`; open Trade Manager UI; Portfolio view; Close a multi-leg CASH bucket;
  confirm a single order in the broker order book and in `payTmMoney.db` `CLOSE_ORDERS`.

## Note (alternative, not chosen)
The originally considered design placed one order and **distributed** its fill back across the
original legs (keeping leg history). It is more "correct" but needs a new `AGG_CLOSE` field, a new
`Workflow.processAggregatedCloses` method, a new app-loop hook, and guards in `__updateRecStatus` /
`close_trade`. Prefer the simpler delete-and-recreate approach above unless per-leg history
preservation becomes a hard requirement.

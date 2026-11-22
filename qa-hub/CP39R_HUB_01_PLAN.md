# PAE-04 CP39R-HUB-01 — isolated QA HUB Codespaces plan (NO EXECUTION)

Status: **PLAN_READY / RUNTIME_NOT_RUN / RELEASE NO-GO**.
Approval scope: prepare a test plan and (if needed) an add-only GitHub branch; **no Codespace creation/start, no compute billing, no terminal commands, no deployment, no PR edits, no import/restore**.

## Exact references (read-only GitHub evidence)
- Existing PAE QA HUB branch: `pilot/pae04-qa-hub-codespaces-20261121`, SHA `c3e9a648aeb633b075d86abf3900fe61e160df96`, tree `e427b9d66b9d920b745ad909917cef3168718e9e`.
- Existing HUB devcontainer SHA `8735730ae8be2f78fd0a21bc1f6070d1f329022a`, Playwright image `mcr.microsoft.com/playwright:v1.65.1-noble`, private forwarded port 8765. **Existing configuration does not prove actual private visibility; inspect runtime setting.**
- Existing HUB runner `qa-hub/qa-hub.mjs` blob SHA `5d43dd3b1f4fe5be688789bd0a7e9391967dafa0`, pinned to OLD PR #15 SHA `3020e5c1278e5073c229a0ed36a35a9815658c15`; it MUST NOT be executed unchanged for R11E.
- Target draft PR #23 HEAD `c3da0816f48a81626ef25fb94dd653deab8533d3`; target baseline main `068bfc4f4bd39736a59c12bd37c56b647bd885cb`.
- Target new-app Git blob `6f76cd6b464216fc1402857c33b1b5a4614b3838`, new SW `14ed6da6242b59bc0ba71d589b48ded3aa1eb5ab`, new offline status `0d0665221303866f404ecd9e0dc0f05af12b482d`.
- Baseline old-app Git blob `3725145e5c48a23027723cc62de9572c0be7feec`, old SW `b1c1ce828ff7c552088b4e395f3fea7e05e9c7b0`; both refs must be verified immediately before a future run.
- Prior R11E: 4 synthetic IndexedDB stores unchanged; OLD app.js returned from Service Worker, NEW app.js in new cache, NEW worker WAITING. Evidence run `45071850824`; never delete past FAIL.
- No `qa-hub/.run/report.json` in GitHub tree; runtime report and Codespace state/billing are NOT independently accessible from the present connector.

## Preparation gates (not executed)
1. Owner separately authorizes one **2-core Codespace** or use of an existing explicitly identified Codespace. First inspect Billing/usage, remaining *free* compute and storage quotas and port visibility in GitHub UI. **Do not create/start when budget unavailable, charged usage possible or status unknown.** GitHub repository admin access alone is insufficient to confirm Codespaces permissions.
2. In a future *separate* isolated QA branch, adapt the pinned source manifest to target `c3da0816f48a81626ef25fb94dd653deab8533d3` with exactly **20 allowlisted nonpersonal site files**. Verify Git blob SHA-1 and byte lengths for each of the 20; fetch neither `site/personal_profile.json` nor `site/personal_adapter.js` from target or original site. Generate BOTH files as local synthetic, safe fixtures in a new staging folder. **Do not serve or read original repo paths.**
3. Keep the existing HUB runner and old `qa-hub/.run/` reports untouched. New staging/report paths: `qa-hub/.run/cp39r-hub01/site-old/`, `qa-hub/.run/cp39r-hub01/site-new/`, `qa-hub/.run/cp39r-hub01/report.json`; paths are placeholders until verified inside the authorized Codespace. Prevent overwrite, use add-only and private permissions. Ignore .run in Git.
4. Test only via a local loopback HTTP server and a **fresh browser profile** with synthetic entries. No external API or original source records. No GitHub token or issue report publisher; no network during browser QA except local loopback. Keep forwarded preview port 8765 **Private**, or do not forward it at all.
5. Before update, load OLD app/SW, verify app.js SHA-256, seeded `pressures`, `medications`, `intakes`, `intakeEvents` and snapshot each store under a consistent readonly transaction. Right-arm pressure only.
6. Switch the synthetic server to NEW files; call normal SW update, then record `registration.active/waiting/installing`, controller identity, cache names and content SHA-256. A new cache alone is **not** a release gate. **Do not call skipWaiting manually; do not clear Cache Storage, service workers or IndexedDB.** If the new worker is WAITING, close old controlled client tabs and reopen in the same profile to permit normal activation, with a bounded timeout. Wait for effective controller transition and new app.js loaded; distinguish old/new code with SHA-256 and `response.fromServiceWorker()`.
7. Gate separately: (A) four-store snapshot exact equality; (B) new SW controls reopened page AND NEW app.js SHA loaded. On first mismatch STOP_FIRST.
8. With NEW controller, test offline reload with loopback connection unavailable and exact four-store snapshot equality. Then restore OLD files **without changing or clearing persisted data**, wait for normal rollback SW lifecycle with old clients closed, verify OLD app.js SHA and four-store equality. Do not execute real backup import/restore.
9. Save a single private, add-only, strictly validated synthetic report with status, source SHA, old/new app.js hashes, SW states, cache names, store counts and test gates, but no record values, personal profile contents, secrets or URLs. Perform independent readback of report. If any FAIL, no retry and no deploy.

## Distinct acceptance criteria
- EXACT_SOURCE_20: 20/20 Git blobs validated; two personal files NOT fetched/read, only synthetic replacements created.
- OLD_BASELINE: OLD app.js SHA and OLD controller confirmed.
- UPGRADE: NEW controller actually controls the page; NEW app.js SHA loaded (not merely new cache present).
- INDEXEDDB: all 4 stores byte-equivalent before/after update and rollback (synthetic only).
- OFFLINE: offline reload with NEW app preserves 4 stores.
- ROLLBACK: OLD app.js restored via normal worker lifecycle; all 4 stores preserved.
- PRIVACY: no real medical files, secrets, original personal profile/adapter, import, restore, Mac, RDC or cloud writes.
- TEST REPORT: one report, valid JSON and independent readback; previous R11B–R11E FAIL evidence retained.
- Real iPhone Safari remains **NOT RUN**; Codespaces Linux WebKit cannot replace it.
- **Release stays NO-GO** pending full acceptance, protected main rules and separate release path.

## Current blockers
- Actual Codespace existence/status, feature entitlement, budget/free quota and runtime resources: **UNKNOWN** (GitHub connector cannot read Codespaces API).
- Existing QA HUB is pinned to PR #15; cannot directly test PR #23.
- This is a **planning-only** deliverable; no browser test, Codespace, CI, upload, Pages or main mutation occurred.

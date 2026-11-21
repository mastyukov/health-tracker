# PAE-04 Health Tracker — QA HUB Codespaces PILOT (TEST only)

**Status:** PREPARED / NOT RUN. No Codespace, GitHub Actions, runner, preview or deployment has been created by this commit.

## Safeguards
- Input: PAE-04 `mastyukov/health-tracker` Draft PR #15 HEAD `3020e5c1278e5073c229a0ed36a35a9815658c15`.
- `site/personal_profile.json` is **never downloaded or read** by the bootstrap. Instead, `qa-hub/.run/site/personal_profile.json` is generated with 10 `QA-` synthetic medicines following the original schema.
- The other 16 web assets are byte-for-byte Git SHA-1 blob verified from the pinned commit. Service Worker and original app code are unchanged.
- The test runs Chromium then Linux WebKit sequentially, including a scoped offline reload check. **Linux WebKit is not a physical iPhone Safari**.
- The preview is served only from `qa-hub/.run/site`. Keep forwarded port 8765 **Private**; GitHub authentication is required. Do not select Public.
- Do not use real pressure/intake, medical records, other accounts, secrets or production databases.
- No automatic post-create/install hooks, no GitHub workflows. `main`, CI, Pages, Dropbox, Mac and other PRs stay unchanged.
- `qa-hub/.run/` and `qa-hub/node_modules/` are ignored, never committed.

## After owner approval to run a 2-core Codespace
1. Open a Codespace from this **pilot branch only** and choose the existing `.devcontainer/devcontainer.json`. Check Billing budget before creating.
2. In the **Codespace terminal (NOT on Mac)** use the commands below; stop if anything unexpected happens.
3. In `qa-hub`: `npm install --ignore-scripts --no-audit --no-fund`.
4. In `qa-hub`: `npm run prepare` (fails closed if a file's SHA differs, preserves staging on error, no retry).
5. In `qa-hub`: `npm run qa` (one fail-fast run, report `.run/report.json`; browser QA not run during package preparation).
6. In `qa-hub`: `npm run serve` to open a private HTTPS forwarded port 8765 on the iPhone signed into the same GitHub account.
7. Verify port **Private**, confirm iPhone TEST preview version, then **Stop Codespace** after use to end compute billing.
8. Never turn on Public, never deploy/merge, never clear iPhone Safari data.

**Blocking conditions:** no free budget, unexpected Git blob, unexpected port visibility, missing Codespace permission, real data in preview, any smoke FAIL -> STOP_FIRST.

**Known limitation:** the synthetic fixture intentionally does not test the original profile values. The test only checks preview loading, origin isolation, synthetic profile, Service Worker and offline shell; it does not prove complete medical CRUD or iPhone Safari acceptance.

## PAE-04 source-pinned branch
This branch is created **directly in `mastyukov/health-tracker`**, starting from Draft PR #15 exact commit `3020e5c1278e5073c229a0ed36a35a9815658c15`. No `site/` file is changed. The `qa-hub` code serves only the staged synthetic copy, not `site/` or the committed original profile. The original profile belongs to the existing public source branch; Codespaces clones that repository but the preview server does not serve this original path. QA-PILOT is independent of CI/Pages and must remain unmerged.

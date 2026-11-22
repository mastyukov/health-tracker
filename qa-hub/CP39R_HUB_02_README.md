# PAE-04 CP39R-HUB-02 — Codespaces scoped synthetic QA runner

**Status: PREPARED / NOT RUN / NO DEPLOY.** This is an add-only runner in an isolated branch from HUB-01 PLAN. The owner confirmed free Codespaces quota exists, but **did not authorize starting or creating a Codespace in this step**.

## Fixed inputs
- Original QA HUB plan: `qa-hub/CP39R_HUB_01_PLAN.md`.
- Old release commit: `068bfc4f4bd39736a59c12bd37c56b647bd885cb`.
- New candidate Draft PR #23 HEAD: `c3da0816f48a81626ef25fb94dd653deab8533d3`.
- The script pins **20 nonpersonal assets** from candidate; fetches only **3 old nonpersonal assets** for baseline. All source blobs are Git SHA-1 and byte-size checked before staging. **Original personal_profile.json and personal_adapter.js are never fetched or read**. Both are replaced by locally generated synthetic fixtures.
- New staged paths: `qa-hub/.run/cp39r-hub02-one-shot-20261123/site-old/` and `site-new/`. Report: `qa-hub/.run/cp39r-hub02-one-shot-20261123/report.json`. All files create-only, private and ignored by Git.
- Does NOT touch `site/` or historical QA HUB tests, reports and branches.

## After separately approved Codespace activation
1. Inspect the existing Codespace identity and state, user-confirmed free quota, selected **2-core** machine and available storage. If not authorized, stop.
2. Select the new isolated branch, confirm its exact HEAD SHA and `.devcontainer/devcontainer.json`. Keep forwarded port 8765 **Private**, or disable port forwarding entirely (the scoped runner uses **127.0.0.1 with an ephemeral private port**).
3. In the **Codespace terminal, NOT Mac**, from repository root install the existing HUB `playwright@1.65.1` without scripts, audit, fund or updates, after showing a full resource passport and separate approval for software installation.
4. Only after an explicit **one-shot QA run approval**, execute `node qa-hub/cp39r-hub02.mjs` from repository root, exactly once; no retries on FAIL. Its report is add-only and private. Never serve the original repository site.
5. The runner stages pinned synthetic assets, launches one fresh Chromium context, verifies OLD app.js and right-arm synthetic readings, runs normal SW update, closes the old controlled page and waits up to 16 seconds for **normal new worker activation**; no manual skipWaiting or cache deletion.
6. Verify NEW app.js SHA and four IndexedDB stores unchanged; go offline and verify again; restore OLD site and wait for normal rollback SW transition; verify OLD app.js and stored records unchanged.
7. Perform independent report readback. The report contains only source SHAs, check names, app.js fingerprints, controller status and bounded error codes. **Never upload a personal JSON backup or medical data.** STOP_FIRST on FAIL.
8. Stop the Codespace after use to end compute billing. Do not select Public port visibility.

## Explicit non-goals
No GitHub Actions run; no Codespace creation or start in this preparation. No Pages deployment, merger, app changes, real import/restore, real user records, Vault, Mac/RDC, Dropbox/iCloud or GitHub report publication. This test remains **Chromium-only**; final physical iPhone Safari acceptance remains NOT RUN. Protected `main` rules and release gate remain unresolved.

**Historical failures must be retained:** R11B 45057352487; R11C 45057954340; R11D 45070816664; R11E 45071850824.

Full roadmap: https://github.com/mastyukov-cyber/pae04-health-tracker-test/issues/20

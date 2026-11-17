# PAE-04 — PERSONAL Strict Backup: 33 source-bound integration checks

**QA observation, 17 November 2026.** This note records one completed synthetic runtime check of the *exact* selected-file and restore handlers from `site/app.js` in QA branch commit `9491f0b07e52aafcac5b0b7954856ed872c22055`; Git blob SHA `9560c4295465f6fac9bc8e434fcb814760a36ce0`.

## Result and precise limits

**33/33 PASS_SOURCE_BOUND_MOCK_INTEGRATION.** An isolated JavaScript V8 run dynamically extracted the existing `verifyDownloadedBackup`, `previewImport`, `downloadImportCheckpoint`, and `applyImport` handlers, the approved strict external shape guard and unchanged validation/merge-preparation helpers. It supplied *synthetic in-memory storage*, a mock Blob and a deterministic **noncryptographic hash stub** for behavioral testing. The selected-file API was simulated with a `file.text()` test double. No real IndexedDB, browser File picker, WebCrypto SHA-256, Safari, iPhone or external file durability test was performed. This is a scoped handler-control-flow result, **not** a Security PASS or evidence of full restore.

Before this step, the QA branch had independently passed **23/23 strict shape scenarios on Node 26**; see prior `qa/personal-backup/strict_external_backup_qa.mjs` and MASTER ROADMAP #20. A real Chrome/IndexedDB attempt was stopped by the Mac 40% total-CPU guard (observed 52.45%), so no browser scenario passed or failed. Preserve that BLOCKED result.

## Exact 33 test observations

1. [x] `EMPTY_BEFORE` — PASS_SCOPED (synthetic source-bound mock)
2. [x] `VALID_EXTERNAL_SHA` — PASS_SCOPED (synthetic source-bound mock)
3. [x] `CORRUPTED_DIGEST_REJECT` — PASS_SCOPED (synthetic source-bound mock)
4. [x] `VERIFY_REJECT_envelope` — PASS_SCOPED (synthetic source-bound mock)
5. [x] `PREVIEW_REJECT_envelope` — PASS_SCOPED (synthetic source-bound mock)
6. [x] `NO_WRITE_envelope` — PASS_SCOPED (synthetic source-bound mock)
7. [x] `VERIFY_REJECT_store` — PASS_SCOPED (synthetic source-bound mock)
8. [x] `PREVIEW_REJECT_store` — PASS_SCOPED (synthetic source-bound mock)
9. [x] `NO_WRITE_store` — PASS_SCOPED (synthetic source-bound mock)
10. [x] `VERIFY_REJECT_pressure` — PASS_SCOPED (synthetic source-bound mock)
11. [x] `PREVIEW_REJECT_pressure` — PASS_SCOPED (synthetic source-bound mock)
12. [x] `NO_WRITE_pressure` — PASS_SCOPED (synthetic source-bound mock)
13. [x] `VERIFY_REJECT_intake` — PASS_SCOPED (synthetic source-bound mock)
14. [x] `PREVIEW_REJECT_intake` — PASS_SCOPED (synthetic source-bound mock)
15. [x] `NO_WRITE_intake` — PASS_SCOPED (synthetic source-bound mock)
16. [x] `VERIFY_REJECT_event` — PASS_SCOPED (synthetic source-bound mock)
17. [x] `PREVIEW_REJECT_event` — PASS_SCOPED (synthetic source-bound mock)
18. [x] `NO_WRITE_event` — PASS_SCOPED (synthetic source-bound mock)
19. [x] `VALID_IMPORT_PREVIEW` — PASS_SCOPED (synthetic source-bound mock)
20. [x] `CHECKPOINT_BLOB` — PASS_SCOPED (synthetic source-bound mock)
21. [x] `ACK_REQUIRED` — PASS_SCOPED (synthetic source-bound mock)
22. [x] `ACK_READY` — PASS_SCOPED (synthetic source-bound mock)
23. [x] `RESTORE_FOUR` — PASS_SCOPED (synthetic source-bound mock)
24. [x] `FOUR_STORE_VALUES_MATCH` — PASS_SCOPED (synthetic source-bound mock)
25. [x] `FILE_MATCHES_LOCAL_POST_RESTORE` — PASS_SCOPED (synthetic source-bound mock)
26. [x] `IDEMPOTENT_REPEAT` — PASS_SCOPED (synthetic source-bound mock)
27. [x] `ID_CONFLICT_BLOCKS` — PASS_SCOPED (synthetic source-bound mock)
28. [x] `STALE_CHECKPOINT_REFUSED` — PASS_SCOPED (synthetic source-bound mock)
29. [x] `STALE_CHECKPOINT_NO_WRITE` — PASS_SCOPED (synthetic source-bound mock)
30. [x] `LEGACY_V1_PREVIEW` — PASS_SCOPED (synthetic source-bound mock)
31. [x] `LEGACY_V2_PREVIEW` — PASS_SCOPED (synthetic source-bound mock)
32. [x] `OVERSIZE_REJECT` — PASS_SCOPED (synthetic source-bound mock)
33. [x] `OWNER_DECLINE_NO_WRITE` — PASS_SCOPED (synthetic source-bound mock)

## Safety and next required gate

- Existing `main` at `4100772e60def1046ab44c4d0cd1883de8e59843` and public PERSONAL v0.6.1.2 **unchanged**. No actual medical records, meds, patient profile, iPhone database or backup bytes were read, edited, uploaded or restored.
- External file strict checking currently exists **only in this QA branch**; do not merge or release without the separate full Security Gate.
- Next: run real isolated **IndexedDB** import/re-import/conflict/checkpoint/rollback and actual **Safari/WebKit** file-input checks at or below the owner-approved Mac CPU 40%/RAM 4 GiB/disk 500 MiB limits. Avoid repeated GUI launches while another project is consuming resources.
- Separately confirm that iPhone JSON is durably stored outside the PWA, then use **synthetic** data for a safe restore test. Never overwrite real health records.

**Reproducibility caveat:** The 33-case test was executed inside an ephemeral V8 test harness; this file preserves the exact case names and results, not an executable or independently archived browser log. Do not convert this evidence into a stronger QA claim. Failed packaging attempts of a standalone harness made **no change to this QA branch**.

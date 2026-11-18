# CP-UX02 — Nested quantity isolated candidate (18 Nov 2026)

Status: **SOURCE_BOUND_V8_44/44_PASS / NODE26_NOT_RUN / SAFARI_NOT_RUN / REAL_INDEXEDDB_NOT_RUN / RELEASE_NO-GO**.

- Source branch SHA: `a22224e1816460dd7e35dcf64dda132f48eafed0`.
- Original `site/app.js` Git blob SHA: `9560c4295465f6fac9bc8e434fcb814760a36ce0`.
- This isolated branch adds only a guard for unrecognized nested keys inside `intakes[].takenQuantity` to EXTERNAL backup validation, preserving the existing optional field and historical scalar/null values.
- Source-bound V8 preflight: prior 23/23 fixture cases plus 21/21 JSON quantity cases PASS.
- To replay on Node 26: run from the repository root `node qa/personal-backup/strict_external_backup_qa.mjs` then `node qa/personal-backup/nested_quantity_qa.mjs`. The second test imports the first, so for one combined invocation use only the second test.
- No changes to `DB_NAME`, `DB_VERSION`, `BACKUP_FORMAT`, local validators, medications, SW, profile or UI.
- **Open policy:** numeric ranges and non-fraction scalar formats for takenQuantity have intentionally NOT been changed or approved. The previous strict guard is source-only QA, not a release.
- **Open release gate:** real Safari/WebKit browser + actual IndexedDB checkpoint, file picker, re-import, conflict, rollback, offline; iPhone external JSON durability.
- Historical v2 symlink FAIL and other QA BLOCKED/FAIL are retained in the project MASTER ROADMAP, not erased.
- No Actions, PR, merge, Pages release, Mac/RDC or real medical records involved.

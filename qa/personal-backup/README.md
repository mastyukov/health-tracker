# PAE-04 Personal v0.6.1.2 — QA-only strict external backup candidate

**Never deploy this branch to GitHub Pages or merge without explicit owner approval and runtime Security Gate.**

Source: main commit `4100772e60def1046ab44c4d0cd1883de8e59843`, `site/app.js` Git blob `5456ca77ceb716c15aec7f475fb7277527b100eb`. Proposed change injects `validateExternalBackupShape(parsed)` after SHA-256 verification in exactly two external file paths: read-only verification and import preview. It rejects unknown top-level, store-level, pressure, intake and intakeEvent properties according to the owner's approved policy. Supports legacy v1/v2 (three stores) and v3 (four stores). Unknown medication extension fields remain handled by existing `validatedMedExtension`. The global `validateBackupData`, merge algorithms, IndexedDB identifiers, backup format, medicines, personal profile, and Service Worker are left untouched.

Run `node qa/personal-backup/strict_external_backup_qa.mjs` from repository root. These 23 tests are **pure schema tests only**. They are not proof of a real browser backup, IndexedDB rollback, or synthetic restore. For release: run isolated Safari + negative file-input/backup/restore/rollback QA with synthetic data, plus separately verified user acceptance. **Do not read or import real medical records**.

Previous branch source is published personal v0.6.1.2; this QA branch is an isolated security candidate only.

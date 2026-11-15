# PAE-04 · Health Tracker PERSONAL RC1 — release audit

**Release target:** personal iPhone Safari, https://mastyukov.github.io/health-tracker/
**Status at creation:** candidate; do not call published until GitHub Pages HTTPS verified.
**Verified source repository:** mastyukov-cyber/pae04-health-tracker-test
**Pinned source commit:** 39be9bea9b23098034f31506ed8418e3aed96056
**Copy boundary:** docs/** of pinned commit to site/** of this repository, byte-for-byte.
**App code/data layout:** IndexedDB schema 1; four stores; backups format v3 (unchanged).
**Release strategy:** maintain app under site/, tests under qa/, decisions under project/, as in Round Timer.

This preview contains real names and owner-reported doses of 10 medicines/supplements, with owner permission. It contains NO real pressure records, no intake log, no credentials, no transfer from any Safari origin. A label in the app and the backup filename still say "synthetic": an existing compatibility marker in the tested source, NOT a guarantee that user-entered records will be fictional.

**Important:** no automatic synchronization between this and the TEST domain. No deletion/reset of browser data. Before entering routine health records, complete iPhone Safari export/import and restore safety acceptance. Never merge other unreviewed PRs. No existing local Safari records are modified by this repository operation.

**Acceptance sequence:** verify source byte hashes; pass synthetic WebKit tests and original regression; open Draft PR; merge only after CI PASS; deploy Pages from site/ via GitHub Actions after owner-approved release; verify actual HTTPS and offline; owner acceptance on physical iPhone.

**Rollback:** release from previous main only after independent approval. Before later updates, export an on-device verified backup; never delete IndexedDB or blindly change DB_NAME.

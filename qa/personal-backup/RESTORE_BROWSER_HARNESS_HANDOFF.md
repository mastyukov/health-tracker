# PAE-04 — isolated real-browser restore QA harness

**Status:** PREPARED / STATIC_SYNTAX_PASS / REAL_BROWSER_NOT_RUN.

Exact source: synthetic harness from the prior blocked Chrome QA package in the authorised Mac CP-UX02 sandbox. Saved without medical content in `qa/personal-backup/restore_browser_harness_synthetic.js`. The original browser attempt stopped after Mac whole-CPU sample reached **52.45%** (owner limit 40%). No restore scenario passed or failed in that run.

The harness expects a *new isolated* test site copied from the exact QA branch, a local HTTP server bound to 127.0.0.1, a fresh browser profile, and the `personal_adapter.js` script disabled **only in that synthetic site copy**. It creates synthetic pressure, medicine, intake and audit-event JSON and exercises verify, checkpoint acknowledgement, four-store restore, repeat, unknown field rejection, conflict and stale-checkpoint handling.

**Do not:** inject this script into the public PERSONAL PWA; call it with real medical data; merge to `main`; run Chrome/Safari when the Mac resource guard would be exceeded; disable Mac protections or stop other projects. This harness has not been executed successfully in a real browser. The source-bound 33-case V8 test matrix is separate and cannot replace it.

Before execution, independently verify `site/app.js` and git SHA, run `node --check`, constrain CPU <=40% whole Mac, RAM <=4 GiB, disk <=500 MiB, run one simulator/browser at a time, log PASS/FAIL/BLOCKED, and separately perform Safari/WebKit acceptance. The active published v0.6.1.2 and patient data must remain unchanged.

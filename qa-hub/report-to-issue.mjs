#!/usr/bin/env node
/**
 * PAE-04 CP-QA-HUB-02: synthetic report -> fixed GitHub Issue #20.
 * SAFE DEFAULT: dry-run (no network, no GitHub write). No npm packages needed.
 * Live publish requires --publish --approve-issue-20 AND a separately authorized
 * fine-grained Issues-only token in PAE04_QA_REPORT_TOKEN.
 * The raw report and its error field are NEVER sent, printed, or logged.
 */
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOME = dirname(fileURLToPath(import.meta.url));
const REPORT_PATH = join(HOME, '.run', 'report.json');
const SOURCE = '3020e5c1278e5073c229a0ed36a35a9815658c15';
const TARGET = 'mastyukov-cyber/pae04-health-tracker-test';
const ISSUE = 20;
const API = 'https://api.github.com/repos/' + TARGET + '/issues/' + ISSUE + '/comments';
const CHECKS = new Set([
  'synthetic-profile', 'online-load', 'service-worker', 'offline-reload',
  'indexeddb-pressure', 'indexeddb-medications', 'indexeddb-intakes',
  'indexeddb-intake-events', 'reload-persistence',
  'crud-pressure', 'crud-medications', 'crud-intakes'
]);
const BROWSERS = new Set(['Chromium', 'WebKit']);
const STATUSES = new Set(['PASS_SCOPED', 'FAIL_STOP_FIRST', 'PARTIAL', 'BLOCKED']);
const TOP_FIELDS = new Set([
  'status', 'sourceCommit', 'synthetic', 'results',
  'startedAt', 'finishedAt', 'error'
]);
const ROW_FIELDS = new Set(['browser', 'status', 'checks']);
const ROW_STATUSES = new Set(['PASS', 'FAIL', 'PARTIAL', 'NOT_RUN']);
const TIMEOUT_MS = 15000;

function stop(code) {
  // Fixed error codes only: never reveal report contents, file paths or tokens.
  throw Error(code);
}
function exactFields(obj, allowed) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) stop('INVALID_OBJECT');
  if (Object.keys(obj).some(k => !allowed.has(k))) stop('UNAPPROVED_FIELD');
}
function validInstant(s) {
  return typeof s === 'string' &&
    /^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z$/.test(s) &&
    Number.isFinite(Date.parse(s)) && new Date(s).toISOString() === s;
}
async function loadAndSanitize() {
  const meta = await stat(REPORT_PATH);
  if (!meta.isFile() || meta.size > 16384 || meta.size < 60) stop('REPORT_SIZE_OR_TYPE');
  const raw = JSON.parse(await readFile(REPORT_PATH, 'utf8'));
  exactFields(raw, TOP_FIELDS);
  if (raw.synthetic !== true || raw.sourceCommit !== SOURCE) stop('UNPINNED_OR_NOT_SYNTHETIC');
  if (!STATUSES.has(raw.status)) stop('INVALID_REPORT_STATUS');
  if (!validInstant(raw.startedAt) || !validInstant(raw.finishedAt) ||
      Date.parse(raw.finishedAt) < Date.parse(raw.startedAt)) stop('INVALID_REPORT_TIME');
  if (!Array.isArray(raw.results) || raw.results.length > 2) stop('INVALID_BROWSER_RESULTS');
  const seen = new Set();
  const results = raw.results.map(row => {
    exactFields(row, ROW_FIELDS);
    if (!BROWSERS.has(row.browser) || seen.has(row.browser) || !ROW_STATUSES.has(row.status))
      stop('INVALID_BROWSER_OR_DUPLICATE');
    seen.add(row.browser);
    if (!Array.isArray(row.checks) || row.checks.length > CHECKS.size ||
        row.checks.some(c => typeof c !== 'string' || !CHECKS.has(c)) ||
        new Set(row.checks).size !== row.checks.length) stop('UNAPPROVED_CHECKS');
    if (row.status !== 'PASS' && row.checks.length) stop('UNVERIFIED_CHECK_RESULT');
    return { browser: row.browser, status: row.status, checks: [...row.checks].sort() };
  }).sort((a,b) => a.browser.localeCompare(b.browser));
  if (raw.status === 'PASS_SCOPED' &&
      (results.length !== 2 || results.some(r => r.status !== 'PASS' || r.checks.length === 0)))
    stop('UNSUPPORTED_PASS');
  return {
    version: 1,
    sourceCommit: SOURCE,
    synthetic: true,
    status: raw.status,
    startedAt: raw.startedAt,
    finishedAt: raw.finishedAt,
    results
  };
}
function makeMessage(report) {
  // SHA is computed exclusively from the sanitized, allowlisted JSON.
  const canonical = JSON.stringify(report);
  const digest = createHash('sha256').update(canonical).digest('hex');
  const handoff = 'PAE04-QH02-' + digest.slice(0,20).toUpperCase();
  const lines = [
    '<!-- PAE04_QA_HUB_REPORT_V1 -->',
    'PAE-04 QA HUB / CP-QA-HUB-02',
    'HANDOFF_ID=' + handoff,
    'REPORT_SHA256=' + digest,
    'SOURCE_COMMIT=' + SOURCE,
    'SYNTHETIC=true',
    'STATUS=' + report.status
  ];
  for (const row of report.results) {
    lines.push(row.browser.toUpperCase() + '=' + row.checks.length + '/' +
      row.checks.length + ' ' + row.status);
    lines.push(row.browser.toUpperCase() + '_CHECKS=' + row.checks.join(','));
  }
  lines.push('CRUD_INDEXEDDB=' +
    (report.results.every(r => r.checks.includes('crud-pressure') &&
      r.checks.includes('crud-medications') && r.checks.includes('crud-intakes'))
      ? 'SCOPED_CHECKS_REPORTED' : 'NOT_VERIFIED'));
  lines.push('IPHONE_SAFARI=NOT_RUN');
  lines.push('SANITIZED_ONLY=true');
  return { digest, handoff, body: lines.join('\\n') };
}
function headers(token) {
  return {
    Accept: 'application/vnd.github+json',
    Authorization: 'Bearer ' + token,
    'X-GitHub-Api-Version': '2022-11-28',
    'Content-Type': 'application/json',
    'User-Agent': 'PAE04-QAHUB02-SyntheticReporter'
  };
}
async function request(url, token, options={}) {
  const res = await fetch(url, {
    ...options,
    headers: headers(token),
    signal: AbortSignal.timeout(TIMEOUT_MS),
    redirect: 'error'
  });
  if (!res.ok) stop('GITHUB_HTTP_' + res.status);
  return res;
}
async function readAllComments(token) {
  const output = [];
  for (let page=1; page<=20; page++) {
    const res = await request(API + '?per_page=100&page=' + page, token);
    const rows = await res.json();
    if (!Array.isArray(rows) || rows.length > 100) stop('INVALID_ISSUE_RESPONSE');
    for (const item of rows) {
      if (typeof item.body !== 'string') stop('INVALID_ISSUE_COMMENT');
      output.push(item.body);
    }
    if (rows.length < 100) return output;
  }
  stop('COMMENT_PAGINATION_LIMIT');
}
function duplicateState(comments, handoff, digest) {
  const marker = 'HANDOFF_ID=' + handoff;
  const sha = 'REPORT_SHA256=' + digest;
  const matches = comments.filter(c => c.split('\\n').includes(marker));
  if (matches.length > 1) stop('DUPLICATE_EXISTING_COMMENTS');
  if (matches.length === 1) {
    if (!matches[0].split('\\n').includes(sha)) stop('HANDOFF_DIGEST_CONFLICT');
    return 'ALREADY_POSTED';
  }
  return 'NEW';
}
async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.length === 0 || (args.length === 1 && args[0] === '--dry-run');
  const publish = args.length === 2 &&
    args[0] === '--publish' && args[1] === '--approve-issue-20';
  if (!dryRun && !publish) stop('INVALID_FLAGS_DEFAULT_IS_DRY_RUN');
  const report = await loadAndSanitize();
  const msg = makeMessage(report);
  if (dryRun) {
    console.log(JSON.stringify({
      status: 'DRY_RUN_ONLY', destination: TARGET + '#' + ISSUE,
      reportStatus: report.status, handoffId: msg.handoff,
      sha256OfSanitizedReport: msg.digest, commentPreview: msg.body
    }, null, 2));
    return;
  }
  const token = process.env.PAE04_QA_REPORT_TOKEN;
  if (!token || token.length < 20) stop('MISSING_AUTHORIZED_TOKEN');
  const before = await readAllComments(token);
  const state = duplicateState(before, msg.handoff, msg.digest);
  if (state === 'ALREADY_POSTED') {
    console.log('ALREADY_POSTED ' + msg.handoff);
    return;
  }
  // One writer only. GitHub Issue comments do not provide an atomic uniqueness lock.
  // Never automatically retry a POST with an ambiguous timeout/result.
  let response;
  try {
    response = await request(API, token, {method:'POST', body:JSON.stringify({body:msg.body})});
  } catch {
    stop('PUBLISH_UNCERTAIN_STOP_FIRST_CHECK_ISSUE_BEFORE_ANY_RETRY');
  }
  const created = await response.json();
  if (typeof created.html_url !== 'string' ||
      !created.html_url.startsWith('https://github.com/' + TARGET + '/issues/' + ISSUE + '#'))
    stop('UNEXPECTED_CREATED_COMMENT_URL');
  const after = await readAllComments(token);
  if (duplicateState(after, msg.handoff, msg.digest) !== 'ALREADY_POSTED')
    stop('READBACK_MISSING_STOP_FIRST');
  console.log(JSON.stringify({status:'PASS_READBACK',handoffId:msg.handoff,
    sha256OfSanitizedReport:msg.digest, commentUrl:created.html_url}));
}
main().catch(e => {
  const code = /^([A-Z0-9_]+)$/.test(e?.message||'') ? e.message : 'UNEXPECTED_ERROR_STOP_FIRST';
  console.error('BLOCKED_REPORT_DELIVERY ' + code);
  process.exitCode = 1;
});

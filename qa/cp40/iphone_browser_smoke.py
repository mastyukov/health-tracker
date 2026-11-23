#!/usr/bin/env python3
"""PAE-04 CP40 iPhone UI browser QA: synthetic in-memory fixtures only.

Tests exact CP40 code through its real HTML/CSS/JS under Chromium.
No personal profile, no medical records, no IndexedDB writes, no release.
"""
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback

from playwright.sync_api import sync_playwright

BASE_SHA = "cb99659a23f61e0eae68785d0846d2112a920d9a"
PINNED = {
    "site/app.js": "21a1cf58b6aca9718d343b175df7cb3175b12e36",
    "site/home.js": "aed8cc18dce93555014f22287070d00dc79ce4fa",
    "site/styles.css": "89c218d2b5b2b23e4911068de9a0892cf0288e2d",
    "site/index.html": "08b241a615da56297d4982a7ac5a2c36f0c8c0ca",
    "site/sw.js": "b1c1ce828ff7c552088b4e395f3fea7e05e9c7b0",
}
ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "qa" / "cp40" / "results"
RESULTS = []
BROWSER_ERRORS = []

def check(label, actual, expected=True):
    ok = actual == expected
    RESULTS.append({"name": label, "result": "PASS" if ok else "FAIL",
                    "actual": repr(actual)[:140], "expected": repr(expected)[:140]})
    if not ok:
        raise AssertionError(f"{label}: observed {actual!r}; expected {expected!r}")

def page_values(page, selector):
    return [s.strip() for s in page.locator(selector).all_text_contents()]

def seed(page):
    return page.evaluate("""() => {
      const current = new Date();
      const iso = dateLocal(current);
      const subtract = (n) => {const t=new Date(current.getFullYear(),current.getMonth(),current.getDate()-n,12);return dateLocal(t);};
      const stamp = (day,hhmm) => day+'T'+hhmm;
      const yesterday = subtract(1), older = subtract(15);
      const created = new Date().toISOString();
      const p = (id, day, hhmm, s, d, pulse) => ({id,arm:'right',dateTime:stamp(day,hhmm),
        createdAt:created,systolic:s,diastolic:d,pulse,note:''});
      const meds = [
        {id:'SYN_REG_0001',name:'Синтетический А',kind:'regular',dose:'1 условная единица',
         from:null,to:null,createdAt:created,dailyIntakes:1},
        {id:'SYN_COURSE_01',name:'Синтетический Б',kind:'course',dose:'1 условная единица',
         from:subtract(2),to:subtract(-5),createdAt:created,dailyIntakes:1},
        {id:'SYN_PRN_0001',name:'Синтетический В',kind:'asNeeded',dose:'условная единица',
         from:null,to:null,createdAt:created}
      ];
      snapshot={pressures:[
          p('SYN_BP_OLD_01',older,'16:00',130,85,70),
          p('SYN_BP_YESTERDAY',yesterday,'18:50',123,78,68),
          p('SYN_BP_TODAY_01',iso,'08:10',107,68,60),
          p('SYN_BP_TODAY_02',iso,'11:35',118,75,null)
        ],medications:meds,intakes:[],intakeEvents:[]};
      render();
      window.PAE04CPUI01.render();
      return {day:iso,count:snapshot.pressures.length,meds:snapshot.medications.length};
    }""")

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

def run():
    assert os.environ.get("PAE04_SYNTHETIC_ONLY") == "true", "Synthetic-only flag missing"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # The QA-file commits may advance HEAD, but the original application blobs must be immutable.
    for rel, expected in PINNED.items():
        blob = subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()
        check("pinned-source:" + rel, blob, expected)
    check("run-on-sandbox-only", subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pae04_cp40_synthetic_") as tmp:
        isolated = Path(tmp) / "site"
        shutil.copytree(ROOT / "site", isolated)
        # Browser sees no real personal profile or adapter.
        (isolated / "personal_profile.json").write_text(
            '{"schema":"CP40_SYNTHETIC_QA","syntheticOnly":true,"medicines":[]}', encoding="utf-8")
        (isolated / "personal_adapter.js").write_text(
            "'use strict';window.PAE04QAProfile={syntheticOnly:true};", encoding="utf-8")
        (isolated / "offline_status.js").write_text(
            "'use strict'; /* QA only: no offline cache modification */", encoding="utf-8")
        handler = functools.partial(QuietHandler, directory=str(isolated))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True,
                                             args=["--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    context = browser.new_context(viewport={"width":390,"height":844},
                        device_scale_factor=2, is_mobile=True, has_touch=True,
                        service_workers="block", locale="ru-RU")
                    page = context.new_page()
                    page.on("pageerror", lambda e: BROWSER_ERRORS.append(str(e)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
                              wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_function(
                        "() => !!window.PAE04CPUI01 && typeof render === 'function' && typeof db !== 'undefined' && !!db",
                        timeout=20000)
                    fixture = seed(page)
                    check("synthetic-fixture-count", fixture["count"], 4)
                    check("synthetic-medication-count", fixture["meds"], 3)
                    check("home-latest-actual", "118 / 75" in page.locator(
                        "#ui01-pressure .ui01-v7-bp-primary").inner_text())
                    check("home-average-today", "113 / 72" in page.locator(
                        "#ui01-pressure").inner_text())
                    check("home-pulse-absent-is-not-zero", "Пульс не указан" in page.locator(
                        "#ui01-pressure").inner_text())
                    check("approved-tonometer-home",
                          page.locator("#ui01-pressure .ui01-tonometer-icon svg rect").count(), 3)
                    check("med-groups-three",page.locator(
                        "#ui01-meds .ui01-med-group").count(),3)
                    check("med-category-outline-SVG",page.locator(
                        "#ui01-meds .ui01-group-title .ui01-kind-icon svg").count(),3)
                    page.locator('.nav-item[data-page="pressure"]').click()
                    check("chart-visible",page.locator("#pressure-chart svg").count(),1)
                    check("chart-selected-latest",page_values(page,
                        "#pressure-chart .ux23-chart-metric-value"), ["118","75","—"])
                    check("chart-blue-pressure-dots",
                          page.locator("#pressure-chart svg circle[fill='#5486B9']").count(),3)
                    check("chart-green-pressure-dots",
                          page.locator("#pressure-chart svg circle[fill='#59A48C']").count(),3)
                    check("chart-red-pulse-dots",
                          page.locator("#pressure-chart svg circle[fill='#DF5263']").count(),2)
                    chart_box=page.locator("#pressure-chart").bounding_box()
                    check("compact-chart-viewport-height",bool(chart_box and chart_box["height"]<520))
                    page.locator("#pressure-chart svg circle[fill='#5486B9']").first.click(force=True)
                    check("chart-point-selection",page_values(page,
                        "#pressure-chart .ux23-chart-metric-value"), ["123","78","68"])
                    page.locator(
                        '[data-period-target="pressure-chart-period"] button[data-period="90"]').click()
                    check("chart-3-month-window",
                          page.locator("#pressure-chart svg circle[fill='#5486B9']").count(),4)
                    check("list-independent-before-switch",
                          page.locator("#pressure-list .history-row").count(),4)
                    page.locator(
                        '[data-period-target="pressure-list-period"] button[data-period="7"]').click()
                    check("list-own-7-day-window",
                          page.locator("#pressure-list .history-row").count(),3)
                    check("chart-remains-3-months",
                          page.locator("#pressure-chart svg circle[fill='#5486B9']").count(),4)
                    page.screenshot(path=str(REPORT_DIR/"CP40_pressure_synthetic.png"), full_page=True)
                    page.locator('.nav-item[data-page="meds"]').click()
                    page.locator(".v232-med-tab[data-med-view='history']").click()
                    check("history-category-buttons",page.locator(
                        "#page-meds .v232-kind-button").count(),3)
                    check("history-buttons-all-outline-SVG",page.locator(
                        "#page-meds .v232-kind-button svg").count(),3)
                    page.screenshot(path=str(REPORT_DIR/"CP40_medicines_synthetic.png"), full_page=True)
                    page.locator('.nav-item[data-page="overview"]').click()
                    page.evaluate("""() => {snapshot.pressures=snapshot.pressures.filter(
                        p=>p.dateTime.slice(0,10)!==dateLocal(new Date()));render();}""")
                    check("yesterday-last-actual-not-mean",
                          "123 / 78" in page.locator(
                              "#ui01-pressure .ui01-v7-bp-primary").inner_text())
                    check("yesterday-actual-label",
                          "Вчера · 18:50" in page.locator("#ui01-pressure").inner_text())
                    check("no-raw-med-category-glyphs",
                          not any(g in page.locator("#ui01-meds").inner_text()
                                  for g in ("▦","ϟ")))
                    check("no-uncaught-js-errors", BROWSER_ERRORS, [])
                    context.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()

if __name__ == "__main__":
    report = {"project":"PAE-04","checkpoint":"CP40","base_commit":BASE_SHA,
              "environment":"GitHub Linux Chromium; 390x844 iPhone viewport",
              "mode":"SYNTHETIC_IN_MEMORY_NO_INDEXEDDB_WRITES",
              "tests":[],"status":"NOT_RUN","errors":[]}
    try:
        run()
        report["status"] = "PASS" if RESULTS else "NOT_RUN"
    except Exception as exc:
        report["status"] = "FAIL" if RESULTS else "BLOCKED"
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
        traceback.print_exc()
    finally:
        report["tests"] = RESULTS
        report["browser_errors"] = BROWSER_ERRORS
        REPORT_DIR.mkdir(parents=True,exist_ok=True)
        (REPORT_DIR/"CP40_BROWSER_QA.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("CP40_BROWSER_QA " + json.dumps(
            {"status":report["status"],"passed":sum(x["result"]=="PASS" for x in RESULTS),
             "failed":sum(x["result"]=="FAIL" for x in RESULTS),
             "error":report["errors"]},ensure_ascii=False))
    sys.exit(0 if report["status"]=="PASS" else 1)

#!/usr/bin/env python3
"""PAE-04 CP40 approved iPhone visual R1: narrow synthetic Chromium UI QA.

Only visual changes introduced after Chromium 32/32 are tested. The browser
uses a temporary site copy; fixture is injected into memory, not IndexedDB.
"""
import functools
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
from iphone_browser_smoke import seed

ROOT=Path(__file__).resolve().parents[2]
RESULTS=ROOT/"qa"/"cp40"/"visual_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
PINNED={
 "site/app.js":"21a1cf58b6aca9718d343b175df7cb3175b12e36",
 "site/home.js":"2a05af6b8de04cf5d0e125b1e4b73fbe479a716b",
 "site/styles.css":"9014218883eb307cc1cde61b12342ce99969a0e3",
 "site/home.css":"e49331b5da9c1632f1d4b384ac05bc57506f50f9",
 "site/index.html":"08b241a615da56297d4982a7ac5a2c36f0c8c0ca"
}
CHECKS=[]
ERRORS=[]

def check(name, condition, evidence=None):
  result="PASS" if condition else "FAIL"
  CHECKS.append({"name":name,"result":result,"evidence":evidence})
  if not condition: raise AssertionError(name+": "+str(evidence))

class NoLogHandler(http.server.SimpleHTTPRequestHandler):
  def log_message(self, fmt, *args): pass

def run():
  check("synthetic-only-env",os.environ.get("PAE04_SYNTHETIC_ONLY")=="true")
  check("sandbox-ref",os.environ.get("GITHUB_REF")==BRANCH)
  for path,sha in PINNED.items():
    got=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
    check("pinned-source:"+path,got==sha,{"expected":sha,"actual":got})
  RESULTS.mkdir(exist_ok=True,parents=True)
  with tempfile.TemporaryDirectory(prefix="pae04_cp40_visual_") as tmp:
    site=Path(tmp)/"site"
    shutil.copytree(ROOT/"site",site)
    (site/"personal_profile.json").write_text(
      '{"schema":"CP40_SYNTHETIC_VISUAL","syntheticOnly":true,"medicines":[]}',encoding="utf-8")
    (site/"personal_adapter.js").write_text(
      "'use strict';window.PAE04QAProfile={syntheticOnly:true};",encoding="utf-8")
    (site/"offline_status.js").write_text(
      "'use strict'; /* QA only: no offline cache modification */",encoding="utf-8")
    server=http.server.ThreadingHTTPServer(
      ("127.0.0.1",0),functools.partial(NoLogHandler,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(channel="chrome",headless=True,
          args=["--no-sandbox","--disable-dev-shm-usage"])
        try:
          context=browser.new_context(viewport={"width":390,"height":844},
            device_scale_factor=2,is_mobile=True,has_touch=True,
            locale="ru-RU",service_workers="block")
          page=context.new_page()
          page.on("pageerror",lambda e:ERRORS.append(str(e)))
          page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
            wait_until="domcontentloaded",timeout=30000)
          page.wait_for_function(
            "() => !!window.PAE04CPUI01 && !!document.querySelector('.status-dot.online')",
            timeout=20000)
          fixture=seed(page)
          check("fixture-count",fixture["count"]==4)
          pressure=page.locator("#ui01-pressure")
          avg=page.locator("#ui01-pressure-average")
          check("last-card-title-approved","Последний замер" in pressure.locator("h2").inner_text())
          check("last-card-actual","118 / 75" in pressure.inner_text())
          check("today-average-own-card",avg.is_visible() and
            "113 / 72" in avg.inner_text() and
            "113 / 72" not in pressure.inner_text())
          check("today-average-calendar-SVG",avg.locator(".ux23-average-icon svg").count()==1)
          check("missing-pulse-not-zero","Пульс не указан" in pressure.inner_text())
          page.screenshot(path=str(RESULTS/"CP40_VR1_today.png"),full_page=True)

          page.locator('.nav-item[data-page="pressure"]').click()
          head=page.locator("#page-pressure .pressure-chart-panel .v23-segmented").bounding_box()
          values=page.locator("#page-pressure .ux23-chart-metrics").bounding_box()
          gap=None if not head or not values else values["y"]-(head["y"]+head["height"])
          check("chart-gap-at-most-50px",gap is not None and 0<=gap<=50,
                {"gap_px":gap})
          check("pressure-three-selected-values",
            [x.strip() for x in page.locator(".ux23-chart-metric-value").all_text_contents()]==
            ["118","75","—"])
          page.screenshot(path=str(RESULTS/"CP40_VR1_pressure.png"),full_page=True)

          page.locator('.nav-item[data-page="meds"]').click()
          check("medicine-today-default",
            page.locator(".v232-med-tab[data-med-view='today']").get_attribute("aria-selected")=="true")
          page.screenshot(path=str(RESULTS/"CP40_VR1_medicines_today.png"),full_page=True)
          page.locator(".v232-med-tab[data-med-view='history']").click()
          check("history-icon-buttons",
            page.locator("#page-meds .v232-kind-button svg").count()==3)
          check("duplicate-type-select-hidden",
            not page.locator("#page-meds .ux23-duplicate-kind-filter").is_visible())
          check("fixed-period-select-hidden",
            not page.locator("#page-meds .ux23-fixed-history-period").is_visible())
          page.locator("#page-meds .v232-kind-button[data-kind='asNeeded']").click()
          check("PRN-choice-of-period-visible",
            page.locator("#med-history-period").is_visible())
          page.screenshot(path=str(RESULTS/"CP40_VR1_history_prn.png"),full_page=True)

          page.locator('.nav-item[data-page="overview"]').click()
          page.evaluate("""() => {snapshot.pressures=snapshot.pressures.filter(
            p=>p.dateTime.slice(0,10)!==dateLocal(new Date()));render();}""")
          check("no-today-average-card",
            not page.locator("#ui01-pressure-average").is_visible())
          check("yesterday-last-actual","123 / 78" in
            page.locator("#ui01-pressure").inner_text())
          check("zero-browser-exceptions",not ERRORS,ERRORS)
          context.close()
        finally: browser.close()
    finally: server.shutdown()

if __name__=="__main__":
  status="NOT_RUN"
  try:
    run()
    status="PASS"
  except Exception as e:
    status="FAIL"
    ERRORS.append(type(e).__name__+": "+str(e))
    traceback.print_exc()
  finally:
    RESULTS.mkdir(parents=True,exist_ok=True)
    (RESULTS/"CP40_VISUAL_R1_QA.json").write_text(
      json.dumps({"status":status,"checks":CHECKS,"errors":ERRORS,
        "mode":"SYNTHETIC_IN_MEMORY_NO_INDEXEDDB_WRITES",
        "viewport":"390x844 Chromium","baseline":"CP40 32/32 preserved"},
        ensure_ascii=False,indent=2),encoding="utf-8")
    print("CP40_VISUAL_R1 "+json.dumps({"status":status,
      "pass":sum(x["result"]=="PASS" for x in CHECKS),
      "fail":sum(x["result"]=="FAIL" for x in CHECKS),
      "errors":ERRORS},ensure_ascii=False))
  sys.exit(0 if status=="PASS" else 1)

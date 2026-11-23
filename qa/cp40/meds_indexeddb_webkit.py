#!/usr/bin/env python3
"""PAE-04 CP40 IndexedDB WebKit-R1: targeted real UI mark/reload/cancel/audit.
All records are synthetic; new temporary localhost origin and browser context.
Not Safari-on-iPhone certification, not a backup/restore test.
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

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/"qa/cp40/idb_webkit_r1_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
PINNED={
 "site/app.js":"cbc0d3b54dbb6a96e70c4aea370b69d3a86c5f29",
 "site/home.js":"16f083fdb3fdb4d84a3d6db422cb4d57e232783b",
 "site/styles.css":"317ab104834442516a3ad9e1be9811206e728762",
 "site/index.html":"08b241a615da56297d4982a7ac5a2c36f0c8c0ca"
}
TESTS=[]
ERRORS=[]
def check(name, observed, expected=True):
    ok=observed==expected
    TESTS.append({"name":name,"result":"PASS" if ok else "FAIL",
                  "actual":repr(observed)[:140], "expected":repr(expected)[:140]})
    if not ok: raise AssertionError(f"{name}: {observed!r} != {expected!r}")

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):pass

def snapshot_db(page):
    return page.evaluate("""async () => {
      const stores=['pressures','medications','intakes','intakeEvents'];
      const all=await Promise.all(stores.map(name=>getAll(name)));
      return Object.fromEntries(stores.map((name,i)=>[name,all[i].sort((a,b)=>a.id.localeCompare(b.id))]));
    }""")

def wait_ready(page):
    page.wait_for_function("""() => !!window.PAE04CPUI01 &&
        typeof db !== 'undefined' && !!db &&
        !!document.querySelector('.status-dot.online')""",timeout=20000)
    page.evaluate("async () => {await Promise.all(STORE_NAMES.map(getAll))}")

def run():
    check("branch-only",os.environ.get("GITHUB_REF"),BRANCH)
    check("synthetic-only-flag",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
    for path,sha in PINNED.items():
        got=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
        check("pinned-source:"+path,got,sha)
    check("UI handler mark exists",
        "await changeIntake('marked',record)" in (ROOT/"site/app.js").read_text())
    check("UI handler cancel exists",
        "await changeIntake('cancelled',{...taken" in (ROOT/"site/app.js").read_text())
    REPORT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pae04_idb_webkit_r1_") as tmp:
        isolated=Path(tmp)/"site"
        shutil.copytree(ROOT/"site",isolated)
        # Never copy a personal profile into the browser. Always replace in temp origin.
        (isolated/"personal_profile.json").write_text(
            '{"schema":"CP40_SYNTHETIC_INDEXEDDB_WEBKIT_R1","syntheticOnly":true,"medicines":[]}',encoding="utf-8")
        (isolated/"personal_adapter.js").write_text(
            "'use strict';window.PAE04QAProfile={syntheticOnly:true};",encoding="utf-8")
        (isolated/"offline_status.js").write_text(
            "'use strict'; /* QA only: no offline cache modification */",encoding="utf-8")
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
            functools.partial(QuietHandler,directory=str(isolated)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.webkit.launch(headless=True)
                try:
                    context=browser.new_context(viewport={"width":390,"height":844},
                        device_scale_factor=2,is_mobile=True,has_touch=True,
                        locale="ru-RU",service_workers="block")
                    page=context.new_page()
                    page.on("pageerror",lambda e:ERRORS.append(str(e)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
                              wait_until="domcontentloaded",timeout=30000)
                    wait_ready(page)
                    check("clean-isolated-IndexedDB", {k:len(v) for k,v in snapshot_db(page).items()},
                        {"pressures":0,"medications":0,"intakes":0,"intakeEvents":0})
                    seeded=page.evaluate("""async () => {
                      const now=new Date(),day=dateLocal(now),created=now.toISOString();
                      const medA={id:'SYN_MED_ALPHA_01',name:'Синтетический А',
                        kind:'regular',dose:'условная единица',from:null,to:null,
                        dailyIntakes:2,createdAt:created};
                      const medB={id:'SYN_MED_COURSE1',name:'Синтетический Б',
                        kind:'course',dose:'условная единица',from:day,to:day,
                        dailyIntakes:1,createdAt:created};
                      const medC={id:'SYN_MED_PRN_001',name:'Синтетический В',
                        kind:'asNeeded',dose:'условная единица',from:null,to:null,
                        createdAt:created};
                      const pressure={id:'SYN_BP_SENTINEL1',arm:'right',dateTime:day+'T00:00',
                        systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
                      for(const m of [medA,medB,medC]){validateMed(m);await addRecord('medications',m);}
                      validatePressure(pressure);await addRecord('pressures',pressure);
                      const previous={id:'SYN_PREEXIST_001',medId:medB.id,date:day,
                        takenAtLocal:day+'T00:00',markedAt:created,status:'active',dailySlot:1};
                      await changeIntake('marked',previous);
                      await reload();
                      return {day,medicationIds:[medA.id,medB.id,medC.id],pressureId:pressure.id,
                              previousId:previous.id};
                    }""")
                    initial=snapshot_db(page)
                    check("three-persisted-synthetic-medications",len(initial["medications"]),3)
                    check("one-persisted-sentinel-pressure",len(initial["pressures"]),1)
                    check("preexisting-fact",len(initial["intakes"]),1)
                    check("preexisting-audit",len(initial["intakeEvents"]),1)
                    check("initial-progress-1-of-3",
                          page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"1 / 3")
                    page.locator('.nav-item[data-page="meds"]').click()
                    row=page.locator("#v232-meds-today .med-block").filter(has_text="Синтетический А")
                    check("target-medication-unique",row.count(),1)
                    check("two-independent-checkboxes",row.locator(".med-schedule-slot input").count(),2)
                    row.locator("input.intake-time-input").fill("00:00")
                    row.locator(".med-schedule-slot input").first.check()
                    page.wait_for_function("""() => snapshot.intakes.some(i =>
                      i.medId==='SYN_MED_ALPHA_01' && i.dailySlot===1 &&
                      i.status==='active')""",timeout=20000)
                    after_mark=snapshot_db(page)
                    added=[i for i in after_mark["intakes"] if i["medId"]=="SYN_MED_ALPHA_01"]
                    events=[e for e in after_mark["intakeEvents"] if e["intakeId"]==added[0]["id"]] if added else []
                    check("real-IndexedDB-intake-inserted",len(added),1)
                    check("record-stored-actual-time",added[0].get("takenAtLocal"),seeded["day"]+"T00:00")
                    check("stored-daily-slot",added[0].get("dailySlot"),1)
                    check("record-active-after-transaction",added[0].get("status"),"active")
                    check("atomic-mark-audit-created",len(events),1)
                    check("mark-audit-action",events[0]["action"],"marked")
                    check("mark-audit-time",events[0].get("newTakenAtLocal"),seeded["day"]+"T00:00")
                    check("mark-progress-2-of-3",
                          page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"2 / 3")
                    check("other-pressure-unchanged-after-mark",after_mark["pressures"],initial["pressures"])
                    check("all-medications-unchanged-after-mark",after_mark["medications"],initial["medications"])
                    check("other-intake-unchanged-after-mark",
                          [x for x in after_mark["intakes"] if x["id"]==seeded["previousId"]],
                          initial["intakes"])
                    check("other-audit-unchanged-after-mark",
                          [e for e in after_mark["intakeEvents"] if e["intakeId"]==seeded["previousId"]],
                          initial["intakeEvents"])
                    # Reload the real page; JS globals reset, only IndexedDB can restore the fact.
                    page.reload(wait_until="domcontentloaded",timeout=30000)
                    wait_ready(page)
                    post_reload=snapshot_db(page)
                    check("persisted-fact-survives-page-reload",post_reload,after_mark)
                    page.locator('.nav-item[data-page="meds"]').click()
                    row=page.locator("#v232-meds-today .med-block").filter(has_text="Синтетический А")
                    check("checkbox-reflects-persisted-mark",row.locator(".med-schedule-slot input").first.is_checked())
                    check("actual-time-visible-after-reload",
                          "00:00" in row.locator(".med-schedule-slot").first.inner_text())
                    page.screenshot(path=str(REPORT/"CP40_IDB_WK_R1_marked_after_reload.png"),
                        full_page=True)
                    dialogs=[]
                    def confirm_dialog(dialog):
                        dialogs.append(dialog.message)
                        dialog.accept()
                    page.on("dialog",confirm_dialog)
                    row.locator(".med-schedule-slot input").first.uncheck()
                    page.wait_for_function("""() => snapshot.intakes.some(i =>
                      i.medId==='SYN_MED_ALPHA_01' && i.status==='cancelled')""",timeout=20000)
                    cancelled_db=snapshot_db(page)
                    cancelled=[i for i in cancelled_db["intakes"] if i["medId"]=="SYN_MED_ALPHA_01"]
                    trail=[e for e in cancelled_db["intakeEvents"] if e["intakeId"]==cancelled[0]["id"]]
                    check("explicit-confirmation-was-shown",len(dialogs),1)
                    check("cancel-status-persisted",cancelled[0].get("status"),"cancelled")
                    check("same-intake-ID-after-cancel",cancelled[0]["id"],added[0]["id"])
                    check("original-markedAt-preserved",cancelled[0].get("markedAt"),added[0].get("markedAt"))
                    check("original-actual-time-preserved",cancelled[0].get("takenAtLocal"),added[0].get("takenAtLocal"))
                    check("cancel-timestamp-stored",isinstance(cancelled[0].get("cancelledAt"),str))
                    check("cancelled-record-not-deleted",len(cancelled_db["intakes"]),2)
                    check("two-atomic-audit-events",len(trail),2)
                    check("mark-and-cancel-actions",sorted(e["action"] for e in trail),
                          ["cancelled","marked"])
                    check("cancel-old-time-tracked",
                          next(e for e in trail if e["action"]=="cancelled").get("oldTakenAtLocal"),
                          seeded["day"]+"T00:00")
                    check("cancelled-progress-1-of-3",
                          page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"1 / 3")
                    check("other-pressure-unchanged-after-cancel",cancelled_db["pressures"],initial["pressures"])
                    check("all-medications-unchanged-after-cancel",cancelled_db["medications"],initial["medications"])
                    check("preexisting-intake-unchanged-after-cancel",
                          [x for x in cancelled_db["intakes"] if x["id"]==seeded["previousId"]],
                          initial["intakes"])
                    check("preexisting-audit-unchanged-after-cancel",
                          [e for e in cancelled_db["intakeEvents"] if e["intakeId"]==seeded["previousId"]],
                          initial["intakeEvents"])
                    page.reload(wait_until="domcontentloaded",timeout=30000)
                    wait_ready(page)
                    check("cancel-and-audit-survive-second-reload",snapshot_db(page),cancelled_db)
                    page.locator('.nav-item[data-page="meds"]').click()
                    row=page.locator("#v232-meds-today .med-block").filter(has_text="Синтетический А")
                    check("cancelled-checkbox-off-after-reload",
                          not row.locator(".med-schedule-slot input").first.is_checked())
                    advanced=row.locator(".ux23-med-advanced")
                    advanced.locator("summary").click()
                    check("cancelled-fact-present-in-history",
                          "Отменено" in advanced.locator(".med-record-list").inner_text())
                    check("audit-shows-both-actions",
                          all(word in advanced.locator(".med-record-list").inner_text()
                          for word in ["Отмечено:","Отменено"]))
                    page.screenshot(path=str(REPORT/"CP40_IDB_WK_R1_cancelled_after_reload.png"),
                        full_page=True)
                    check("no-uncaught-js-errors",ERRORS,[])
                    context.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()

if __name__=="__main__":
    status="NOT_RUN";errors=[]
    try: run();status="PASS"
    except Exception as exc:
        status="FAIL" if TESTS else "BLOCKED"
        errors.append(type(exc).__name__+": "+str(exc))
        traceback.print_exc()
    REPORT.mkdir(parents=True,exist_ok=True)
    result={"checkpoint":"CP40 IndexedDB WebKit-R1","status":status,
            "environment":"Linux Playwright 1.65.1 WebKit; simulated iPhone 390x844",
            "scope":"Real IndexedDB writes in temporary synthetic localhost origin only",
            "tests":TESTS,"errors":errors,"browser_errors":ERRORS}
    (REPORT/"CP40_IDB_WK_R1_report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CP40_IDB_WEBKIT_R1 "+json.dumps({"status":status,
        "passed":sum(x["result"]=="PASS" for x in TESTS),
        "failed":sum(x["result"]=="FAIL" for x in TESTS),
        "errors":errors},ensure_ascii=False))
    sys.exit(0 if status=="PASS" else 1)

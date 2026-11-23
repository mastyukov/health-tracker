#!/usr/bin/env python3
"""PAE-04 CP40 OFFLINE WEBKIT-R1: one synthetic-only offline restart QA.
Initial online Service Worker install -> full browser profile restart without
network or HTTP server -> independent IndexedDB readback -> offline write/reload.
No personal profile, no medical data, no production or TEST deployment.
"""
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/"qa/cp40/offline_webkit_r1_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
PINNED={
    "site/app.js":"c1adc5545d175ed2456a18d4febd00c095f423f1",
    "site/home.js":"16f083fdb3fdb4d84a3d6db422cb4d57e232783b",
    "site/styles.css":"317ab104834442516a3ad9e1be9811206e728762",
    "site/index.html":"08b241a615da56297d4982a7ac5a2c36f0c8c0ca",
    "site/sw.js":"b1c1ce828ff7c552088b4e395f3fea7e05e9c7b0",
    "site/offline_status.js":"d287ba87f900dd43c9b83ab463d21fa9aca13d7e"
}
FILES=["./","./index.html","./app.js","./styles.css","./home.js","./home.css",
       "./med_guard.mjs","./med_matcher.mjs","./med_guard.css",
       "./personal_adapter.js","./personal_profile.json","./offline_status.js",
       "./manifest.webmanifest","./icons/icon.svg","./icons/apple-touch-icon.png",
       "./icons/icon-192.png","./icons/icon-512.png"]
CACHE="pae04-ht-stable-candidate-synthetic-schema1-cache-personal-home-v71-cachefix-20261122"
CHECKS=[]
ERRORS=[]
FACTS={}

def check(label, actual, expected=True):
    good=actual==expected
    CHECKS.append({"name":label,"result":"PASS" if good else "FAIL",
                   "actual":repr(actual)[:125], "expected":repr(expected)[:125]})
    if not good:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(",",":")).encode("utf-8")).hexdigest()

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

def read_db(page):
    return page.evaluate("async () => await readBackupSnapshot()")

def wait_db(page):
    page.wait_for_function("""() => typeof db!=='undefined' && !!db &&
        !!document.querySelector('.status-dot.online') &&
        typeof readBackupSnapshot === 'function'""",timeout=20000)
    page.evaluate("async () => {await Promise.all(STORE_NAMES.map(getAll))}")

def sw_health(page):
    return page.evaluate("""async ({files,cacheName}) => {
      const keys=await caches.keys();
      const cache=await caches.open(cacheName);
      const found=await Promise.all(files.map(p=>cache.match(p).then(Boolean)));
      const registration=await navigator.serviceWorker.getRegistration('./');
      return {registered:!!registration,active:!!registration?.active,
        controlled:!!navigator.serviceWorker.controller,
        cached:keys.includes(cacheName),all:found.every(Boolean),
        cachedCount:found.filter(Boolean).length,
        total:files.length,
        status:document.querySelector('#pae04-offline-status')?.dataset.ready||'missing',
        online:navigator.onLine};
    }""",{"files":FILES,"cacheName":CACHE})

def ready_sw(page):
    page.wait_for_function("""async ({cacheName}) => {
      try {
        const status=document.querySelector('#pae04-offline-status');
        const keys=await caches.keys();
        const registration=await navigator.serviceWorker.getRegistration('./');
        return keys.includes(cacheName) && !!registration?.active &&
          !!navigator.serviceWorker.controller && status?.dataset.ready==='true';
      } catch(_) {return false;}
    }""",arg={"cacheName":CACHE},timeout=35000)

def launch_webkit(pw,profile):
    return pw.webkit.launch_persistent_context(str(profile),headless=True,
        viewport={"width":390,"height":844},device_scale_factor=2,
        is_mobile=True,has_touch=True,locale="ru-RU",service_workers="allow",
        accept_downloads=False)

def seed_online(page):
    return page.evaluate("""async () => {
      const now=new Date(),date=dateLocal(now),created=now.toISOString();
      const pressure={id:'SYN_OFFLINE_BP_0001',arm:'right',dateTime:date+'T00:01',
         systolic:119,diastolic:74,pulse:61,note:'',createdAt:created};
      const med={id:'SYN_OFFLINE_MED_0001',name:'Синтетический контроль А',
         kind:'regular',dose:'условная единица',from:null,to:null,
         dailyIntakes:2,createdAt:created};
      const prn={id:'SYN_OFFLINE_PRN_0001',name:'Синтетический контроль Б',
         kind:'asNeeded',dose:'условная единица',from:null,to:null,
         createdAt:created};
      validatePressure(pressure);validateMed(med);validateMed(prn);
      await addRecord('pressures',pressure);
      await addRecord('medications',med);
      await addRecord('medications',prn);
      await changeIntake('marked',{
        id:'SYN_OFFLINE_INTAKE_01',medId:med.id,date,
        takenAtLocal:date+'T00:02',markedAt:created,status:'active',dailySlot:1
      });
      await reload();
      return {date,pressureId:pressure.id,medId:med.id};
    }""")

def offline_insert(page,day):
    return page.evaluate("""async ({day}) => {
      const created=new Date().toISOString();
      await changeIntake('marked',{
        id:'SYN_OFFLINE_INTAKE_02',medId:'SYN_OFFLINE_MED_0001',date:day,
        takenAtLocal:day+'T00:03',markedAt:created,status:'active',dailySlot:2
      });
      await reload();
      return {intakes:snapshot.intakes.length,
         events:snapshot.intakeEvents.length};
    }""",{"day":day})

def run():
    check("sandbox-branch",os.environ.get("GITHUB_REF"),BRANCH)
    check("synthetic-only-env",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
    for path,sha in PINNED.items():
        observed=subprocess.check_output(["git","hash-object",path],
            cwd=ROOT,text=True).strip()
        check("pinned-source:"+path,observed,sha)
    for path in FILES:
        check("local-shell-file:"+path, (ROOT/"site"/path).exists())
    sw=(ROOT/"site"/"sw.js").read_text(encoding="utf-8")
    check("SW static cache only","Never accesses IndexedDB" in sw)
    check("SW cache version", "const CACHE=CACHE_PREFIX+'personal-home-v71-cachefix-20261122'" in sw and "const CACHE_PREFIX='pae04-ht-stable-candidate-synthetic-schema1-cache-'" in sw)
    check("SW explicit offline fetch", "self.addEventListener('fetch'" in sw)
    REPORT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pae04_cp40_offline_webkit_") as tmp:
        isolated=Path(tmp)/"site"
        profile=Path(tmp)/"webkit-profile"
        shutil.copytree(ROOT/"site",isolated)
        # Replace personal files *before* SW caching; never cache real user data.
        (isolated/"personal_profile.json").write_text(
            '{"schema":"CP40_SYNTHETIC_OFFLINE_WEBKIT_R1","syntheticOnly":true,"medicines":[]}',
            encoding="utf-8")
        (isolated/"personal_adapter.js").write_text(
            "'use strict';window.PAE04QAProfile={syntheticOnly:true};",encoding="utf-8")
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
            functools.partial(QuietHandler,directory=str(isolated)))
        server.daemon_threads=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f"http://127.0.0.1:{server.server_port}/index.html"
        FACTS["service_port"]=server.server_port
        try:
            with sync_playwright() as pw:
                context=launch_webkit(pw,profile)
                try:
                    page=context.new_page()
                    page.on("pageerror",lambda e:ERRORS.append(str(e)))
                    page.goto(url,wait_until="domcontentloaded",timeout=30000)
                    wait_db(page)
                    check("clean-initial-storage",
                        {n:len(v) for n,v in read_db(page).items()},
                        {"pressures":0,"medications":0,"intakes":0,"intakeEvents":0})
                    ready_sw(page)
                    online_sw=sw_health(page)
                    check("service-worker-active-online",online_sw["active"])
                    check("service-worker-controlling-online",online_sw["controlled"])
                    check("offline-status-ready-online",online_sw["status"],"true")
                    check("app-shell-fully-cached-online",online_sw["cachedCount"],len(FILES))
                    check("browser-online-before-disconnection",online_sw["online"])
                    seeded=seed_online(page)
                    before=read_db(page)
                    check("4-store-synthetic-seed-counts",
                        {n:len(v) for n,v in before.items()},
                        {"pressures":1,"medications":2,"intakes":1,"intakeEvents":1})
                    original_sha=digest(before)
                    FACTS["pre_offline_sha256"]=original_sha
                    check("synthetic-reading-valid",before["pressures"][0]["arm"],"right")
                    check("online-medication-UI-progress",
                        page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"1 / 2")
                    page.close()
                finally:
                    context.close()
                # The actual HTTP listener is closed before the browser relaunch.
                server.shutdown()
                server.server_close()
                check("server-socket-stopped",server.socket.fileno(),-1)
                # Relaunch the SAME persisted WebKit profile, with network disabled
                # BEFORE any navigation. No HTTP server exists to fall back to.
                restarted=launch_webkit(pw,profile)
                try:
                    restarted.set_offline(True)
                    offline_page=restarted.new_page()
                    offline_page.on("pageerror",lambda e:ERRORS.append(str(e)))
                    result=offline_page.goto(url,wait_until="domcontentloaded",
                        timeout=30000)
                    check("offline-app-http-status",result.status if result else None,200)
                    wait_db(offline_page)
                    check("browser-really-offline",
                          offline_page.evaluate("navigator.onLine"),False)
                    check("app-shell-is-original-ui",
                          offline_page.title(),"Health Tracker · Compact v7.1")
                    offline_sw=sw_health(offline_page)
                    check("SW-controlling-after-restart",offline_sw["controlled"])
                    check("cache-still-present-after-restart",offline_sw["cached"])
                    check("all-shell-assets-after-restart",
                          offline_sw["cachedCount"],len(FILES))
                    check("cached-status-after-restart",offline_sw["status"],"true")
                    check("no-false-offline-warning-after-restart",
                          "офлайн-кэш не включился" not in offline_page.locator("#messages").inner_text())
                    recovered=read_db(offline_page)
                    check("unchanged-4-store-records-offline",recovered,before)
                    check("independent-stored-data-SHA256",
                          digest(recovered),original_sha)
                    check("offline-UI-pressure-count",
                          offline_page.locator("#stat-pressure").inner_text(),"1")
                    check("offline-UI-med-count",
                          offline_page.locator("#stat-meds").inner_text(),"2")
                    check("offline-UI-active-intake-count",
                          offline_page.locator("#stat-intakes").inner_text(),"1")
                    check("offline-intake-progress",
                          offline_page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"1 / 2")
                    new=offline_insert(offline_page,seeded["date"])
                    check("offline-saved-new-intake",new["intakes"],2)
                    check("offline-created-audit",new["events"],2)
                    offline_data=read_db(offline_page)
                    check("offline-writes-preserve-old-pressure",
                          offline_data["pressures"],before["pressures"])
                    check("offline-writes-preserve-medications",
                          offline_data["medications"],before["medications"])
                    check("offline-writes-preserve-first-intake",
                          [x for x in offline_data["intakes"] if x["id"]=="SYN_OFFLINE_INTAKE_01"],
                          before["intakes"])
                    check("offline-only-new-intake-ID",
                          len([x for x in offline_data["intakes"] if x["id"]=="SYN_OFFLINE_INTAKE_02"]),1)
                    check("offline-new-event-marked",
                          len([x for x in offline_data["intakeEvents"] if
                               x["intakeId"]=="SYN_OFFLINE_INTAKE_02" and x["action"]=="marked"]),1)
                    after_sha=digest(offline_data)
                    FACTS["offline_write_sha256"]=after_sha
                    offline_page.reload(wait_until="domcontentloaded",timeout=30000)
                    wait_db(offline_page)
                    check("still-offline-after-reload",
                          offline_page.evaluate("navigator.onLine"),False)
                    durable=read_db(offline_page)
                    check("offline-write-survives-offline-reload",durable,offline_data)
                    check("offline-write-SHA-matches",digest(durable),after_sha)
                    check("offline-UI-progress-2-of-2",
                          offline_page.locator("#v232-meds-today .ux23-meds-today-count").inner_text(),"2 / 2")
                    check("no-false-offline-warning-after-reload",
                          "офлайн-кэш не включился" not in offline_page.locator("#messages").inner_text())
                    offline_page.screenshot(path=str(REPORT/"CP40_OFFLINE_WK_R1_after_relaunch.png"),
                        full_page=True)
                    check("no-JS-page-errors",ERRORS,[])
                    offline_page.close()
                finally:
                    restarted.close()
        finally:
            # Idempotent cleanup; the online phase may have failed before shutdown.
            try:server.shutdown()
            except Exception:pass
            try:server.server_close()
            except Exception:pass

if __name__=="__main__":
    status="NOT_RUN";errors=[]
    try: run();status="PASS"
    except Exception as exc:
        status="FAIL" if CHECKS else "BLOCKED"
        errors.append(type(exc).__name__+": "+str(exc))
        traceback.print_exc()
    REPORT.mkdir(parents=True,exist_ok=True)
    safe_facts={k:v for k,v in FACTS.items() if k.endswith("sha256")}
    result={"checkpoint":"CP40 Offline WebKit-R1","status":status,
        "mode":"Linux WebKit persistent profile; server shutdown + network offline",
        "scope":"synthetic-only, real SW CacheStorage and 4-store IndexedDB",
        "checks":CHECKS,"errors":errors,"browser_errors":ERRORS,
        "sha256":safe_facts}
    (REPORT/"CP40_OFFLINE_WK_R1_report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CP40_OFFLINE_WEBKIT_R1 "+json.dumps({
        "status":status,"passed":sum(x["result"]=="PASS" for x in CHECKS),
        "failed":sum(x["result"]=="FAIL" for x in CHECKS),
        "errors":errors},ensure_ascii=False))
    sys.exit(0 if status=="PASS" else 1)

#!/usr/bin/env python3
"""PAE-04 CP41-SG01. Four correctly signed UNKNOWN-field backups -> fail closed.
Only synthetic temporary localhost + real Playwright WebKit IndexedDB.
UI file verification AND import preview tested, readback each time.
No personal profile, no medical records, no production deployment.
"""
import functools,hashlib,http.server,json,os,shutil,subprocess,sys,tempfile,threading,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/"qa/cp41/sg01_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
APP_BLOB="5b7432415d8c2c35000c3d4bd219de583e20e09c"
CHECKS=[];PAGE_ERRORS=[];REPORT_META={}
CASES=[
 ("SG01-E","backup","Неизвестное поле backup.cp41_unknown_field"),
 ("SG01-P","pressure","Неизвестное поле pressures.cp41_unknown_field"),
 ("SG01-I","intake","Неизвестное поле intakes.cp41_unknown_field"),
 ("SG01-A","intakeEvent","Неизвестное поле intakeEvents.cp41_unknown_field")
]
def check(name,got,want=True):
    good=got==want
    CHECKS.append({"name":name,"status":"PASS" if good else "FAIL",
                   "actual":repr(got)[:160],"expected":repr(want)[:160]})
    if not good:raise AssertionError(name+": "+repr(got)+" != "+repr(want))
def canon(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
def db_read(page):
    return page.evaluate("async ()=> await readBackupSnapshot()")
def ready(page):
    page.wait_for_function("""()=>typeof db!=='undefined'&&!!db&&
       !!document.querySelector('.status-dot.online')&&
       typeof createBackup==='function'&&
       typeof validateExternalBackupShape==='function'""",timeout=20000)
def build_case(page,kind):
    return page.evaluate("""async kind=>{
      const v=JSON.parse(JSON.stringify(await createBackup()));
      if(kind==='backup')v.cp41_unknown_field=true;
      else if(kind==='pressure')v.data.pressures[0].cp41_unknown_field=true;
      else if(kind==='intake')v.data.intakes[0].cp41_unknown_field=true;
      else if(kind==='intakeEvent')v.data.intakeEvents[0].cp41_unknown_field=true;
      else throw Error('unapproved QA scenario');
      delete v.sha256;v.sha256=await sha256(v);
      return v;
    }""",kind)
def file_payload(signed,name):
    return {"name":name+".json","mimeType":"application/json",
            "buffer":json.dumps(signed,ensure_ascii=False,separators=(",",":")).encode("utf-8")}
def run():
    check("sandbox guard",os.environ.get("GITHUB_REF"),BRANCH)
    check("synthetic guard",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
    got=subprocess.check_output(["git","hash-object","site/app.js"],cwd=ROOT,text=True).strip()
    check("exact modified app blob",got,APP_BLOB)
    src=(ROOT/"site/app.js").read_text(encoding="utf-8")
    check("validator and two callsites",src.count("validateExternalBackupShape(parsed)"),3)
    check("donor nested quantity guard","['numerator','denominator']" in src)
    REPORT.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix="pae04_cp41_sg01_") as tmp:
      site=Path(tmp)/"site"
      shutil.copytree(ROOT/"site",site)
      (site/"personal_profile.json").write_text(
        '{"schema":"CP41_SYNTHETIC_ONLY","medicines":[]}',encoding="utf-8")
      (site/"personal_adapter.js").write_text(
        "'use strict';window.PAE04SG01={syntheticOnly:true};",encoding="utf-8")
      (site/"offline_status.js").write_text(
        "'use strict';/* isolated QA, no service-worker mutation */",encoding="utf-8")
      server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
        functools.partial(Quiet,directory=str(site)))
      server.daemon_threads=True
      threading.Thread(target=server.serve_forever,daemon=True).start()
      try:
        with sync_playwright() as pw:
          browser=pw.webkit.launch(headless=True)
          try:
            ctx=browser.new_context(viewport={"width":390,"height":844},
              device_scale_factor=2,is_mobile=True,has_touch=True,
              locale="ru-RU",service_workers="block",accept_downloads=True)
            page=ctx.new_page()
            page.on("pageerror",lambda e:PAGE_ERRORS.append(str(e)))
            downloads=[]
            page.on("download",lambda d:downloads.append(d.suggested_filename))
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
              wait_until="domcontentloaded",timeout=30000)
            ready(page)
            initial=db_read(page)
            check("new isolated IndexedDB empty",
              {k:len(v) for k,v in initial.items()},
              {"pressures":0,"medications":0,"intakes":0,"intakeEvents":0})
            page.evaluate("""async()=>{
              const now=new Date(),date=dateLocal(now),created=now.toISOString();
              const bp={id:'SYN_SG01_PRESSURE_001',arm:'right',dateTime:date+'T00:01',
                systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
              const med={id:'SYN_SG01_MEDICINE_001',name:'Синтетический препарат А',
                dose:'условная единица',kind:'regular',from:null,to:null,
                dailyIntakes:1,createdAt:created};
              validatePressure(bp);validateMed(med);
              await addRecord('pressures',bp);
              await addRecord('medications',med);
              await changeIntake('marked',{
                id:'SYN_SG01_INTAKE_001',medId:med.id,date,
                takenAtLocal:date+'T00:02',markedAt:created,status:'active',dailySlot:1
              });
              await reload();
            }""")
            baseline=db_read(page)
            check("baseline has four tables and linked synthetic rows",
               {k:len(v) for k,v in baseline.items()},
               {"pressures":1,"medications":1,"intakes":1,"intakeEvents":1})
            baseline_hash=digest(baseline)
            check("original intake event is marked",baseline["intakeEvents"][0]["action"],"marked")
            REPORT_META["baseline_sha256"]=baseline_hash
            page.locator('.nav-item[data-page="settings"]').click()
            for index,(case_id,kind,reason) in enumerate(CASES):
              signed=build_case(page,kind)
              check(case_id+" signed SHA256 independently valid",
                 signed.get("sha256"),
                 digest({k:v for k,v in signed.items() if k!="sha256"}))
              check(case_id+" signature unchanged after adding unknown field",
                 len(signed["sha256"]),64)
              before=db_read(page)
              check(case_id+" pretest baseline remains intact",before,baseline)
              payload=file_payload(signed,case_id)
              submitted=payload["buffer"]
              page.locator("#verify-file").set_input_files(payload)
              page.wait_for_function("""reason=>{
                  return !!document.querySelector('#verify-result .verify-fail') &&
                    document.querySelector('#verify-result').textContent.includes(reason)
              }""",arg=reason,timeout=15000)
              check(case_id+" verify input rejected with exact reason",
                   reason in page.locator("#verify-result").inner_text())
              check(case_id+" verify PASS not shown",
                   page.locator("#verify-result .verify-pass").count(),0)
              page.locator("#import-file").set_input_files(payload)
              page.wait_for_function("""reason=>document.querySelector('#import-preview')
                 ?.textContent.includes('Ошибка: '+reason)""",
                 arg=reason,timeout=15000)
              check(case_id+" import preview rejected with exact reason",
                    "Ошибка: "+reason in page.locator("#import-preview").inner_text())
              check(case_id+" pending import cleared",
                    page.evaluate("pendingImport===null"))
              check(case_id+" checkpoint cannot be downloaded",
                    page.locator("#checkpoint-button").is_disabled())
              check(case_id+" checkpoint ack disabled",
                    page.locator("#checkpoint-ack").is_disabled())
              check(case_id+" checkpoint not acknowledged",
                    not page.locator("#checkpoint-ack").is_checked())
              check(case_id+" import remains disabled",
                    page.locator("#import-button").is_disabled())
              check(case_id+" checkpoint status empty",
                    page.locator("#checkpoint-status").inner_text().strip(),"")
              check(case_id+" no protective download triggered",
                    downloads,[])
              check(case_id+" test file byte buffer untouched",
                    payload["buffer"],submitted)
              post=db_read(page)
              check(case_id+" all IndexedDB rows byte-equivalent",
                    post,before)
              check(case_id+" independent IndexedDB SHA256 unchanged",
                    digest(post),baseline_hash)
              if index==0:
                 page.screenshot(path=str(REPORT/"CP41_SG01_rejection_synthetic_webkit.png"),
                   full_page=False)
              page.reload(wait_until="domcontentloaded",timeout=30000)
              ready(page)
              after_reload=db_read(page)
              check(case_id+" unchanged after WebKit reload",
                    after_reload,baseline)
              check(case_id+" audit preserved after WebKit reload",
                    after_reload["intakeEvents"],baseline["intakeEvents"])
              page.locator('.nav-item[data-page="settings"]').click()
            # Narrow positive control: a valid signed backup still passes both
            # read-only previews. Never click checkpoint or import.
            valid=page.evaluate("async()=>await createBackup()")
            check("valid v3 signature independently correct",
                valid["sha256"],digest({k:v for k,v in valid.items() if k!="sha256"}))
            page.locator("#verify-file").set_input_files(file_payload(valid,"SG01_POSITIVE"))
            page.locator("#verify-result .verify-pass").wait_for(timeout=15000)
            check("valid signed v3 verify accepted",
                "SHA-256 совпадает" in page.locator("#verify-result").inner_text())
            page.locator("#import-file").set_input_files(file_payload(valid,"SG01_POSITIVE_IMPORT"))
            page.wait_for_function("""()=>document.querySelector('#import-preview')
                ?.textContent.includes('Конфликтов: 0')""",timeout=15000)
            check("valid signed v3 import preview accepted",
                 "Конфликтов: 0" in page.locator("#import-preview").inner_text())
            check("positive control still cannot import without checkpoint",
                 page.locator("#import-button").is_disabled())
            check("positive control causes no writes",db_read(page),baseline)
            check("no uncaught JavaScript page errors",PAGE_ERRORS,[])
            check("no download during negative cases or positive control",downloads,[])
            REPORT_META["case_ids"]=[x[0] for x in CASES]
            REPORT_META["cases_exercised"]=len(CASES)
            REPORT_META["positive_control"]="VERIFY_AND_PREVIEW_ONLY"
            ctx.close()
          finally:
            browser.close()
      finally:
        server.shutdown();server.server_close()
if __name__=="__main__":
    status="NOT_RUN";errors=[]
    try: run();status="PASS"
    except Exception as exc:
      status="FAIL" if CHECKS else "BLOCKED"
      errors.append(type(exc).__name__+": "+str(exc))
      traceback.print_exc()
    REPORT.mkdir(exist_ok=True,parents=True)
    payload={"checkpoint":"CP41-SG01 Strict External Backup WebKit",
      "status":status,"scope":"4 unknown-field cases x 2 actual UI file inputs + independent 4-store IndexedDB readback",
      "environment":"Linux Playwright 1.65.1 WebKit; iPhone viewport 390x844",
      "synthetic_only":True,"tests":CHECKS,"errors":errors,"page_errors":PAGE_ERRORS,
      "data_hashes":REPORT_META}
    (REPORT/"CP41_SG01_WEBKIT_REPORT.json").write_text(
      json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CP41_SG01_WEBKIT "+json.dumps({
      "status":status,"pass":sum(x["status"]=="PASS" for x in CHECKS),
      "fail":sum(x["status"]=="FAIL" for x in CHECKS),
      "cases_completed":REPORT_META.get("cases_exercised",0),
      "errors":errors},ensure_ascii=False))
    sys.exit(0 if status=="PASS" else 1)

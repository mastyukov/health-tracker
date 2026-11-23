#!/usr/bin/env python3
"""PAE-04 CP40 Backup WebKit-R1: two synthetic IndexedDB origins, real UI export
and additive import, independent SHA-256, pre-import checkpoint, verified readback.
Only temporary origins. No user data, no deployment, no Safari certification.
"""
import functools,hashlib,http.server,json,os,subprocess,shutil,tempfile,threading,traceback,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
RESULTS=ROOT/"qa/cp40/backup_webkit_r1_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
PINNED={
    "site/app.js":"cbc0d3b54dbb6a96e70c4aea370b69d3a86c5f29",
    "site/home.js":"16f083fdb3fdb4d84a3d6db422cb4d57e232783b",
    "site/styles.css":"317ab104834442516a3ad9e1be9811206e728762",
    "site/index.html":"08b241a615da56297d4982a7ac5a2c36f0c8c0ca"
}
CHECKS=[];PAGE_ERRORS=[];FACTS={}
def check(label, observed, expected=True):
    good=observed==expected
    CHECKS.append({"name":label,"result":"PASS" if good else "FAIL",
                   "actual":repr(observed)[:135],"expected":repr(expected)[:135]})
    if not good:raise AssertionError(f"{label}: {observed!r} != {expected!r}")
class Silent(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def canonical_json(v):
    # All fields are synthetic strings, ints, nulls and dicts; independent of app JS.
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v):
    return hashlib.sha256(canonical_json(v).encode("utf-8")).hexdigest()
def load_verified_backup(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    h=data.get("sha256","")
    body={k:v for k,v in data.items() if k!="sha256"}
    check("independent SHA256 "+Path(path).name, digest(body),h)
    check("v3 backup "+Path(path).name, data.get("version"),3)
    check("all four tables "+Path(path).name,
          sorted(data.get("data",{}).keys()),sorted(["pressures","medications","intakes","intakeEvents"]))
    return data

def raw_db(page):
    return page.evaluate("async () => await readBackupSnapshot()")
def wait_ready(page):
    page.wait_for_function("""() => typeof db!=='undefined' && !!db &&
      !!document.querySelector('.status-dot.online') &&
      typeof createBackup === 'function'""",timeout=20000)
    page.evaluate("async()=>{await Promise.all(STORE_NAMES.map(getAll))}")
def prepare_origin(tmp,label):
    dest=Path(tmp)/label
    shutil.copytree(ROOT/"site",dest)
    (dest/"personal_profile.json").write_text(
      '{"syntheticOnly":true,"medicines":[]}',encoding="utf-8")
    (dest/"personal_adapter.js").write_text(
      "'use strict';window.PAE04QAProfile={syntheticOnly:true};",encoding="utf-8")
    (dest/"offline_status.js").write_text(
      "'use strict';/* purely synthetic QA */",encoding="utf-8")
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
        functools.partial(Silent,directory=str(dest)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

def seed(page,prefix):
    return page.evaluate("""async prefix => {
      const t=new Date(),date=dateLocal(t),created=t.toISOString();
      const p={id:'SYN_'+prefix+'_PRESSURE_01',arm:'right',dateTime:date+'T00:01',
        systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
      const m={id:'SYN_'+prefix+'_MEDICINE_01',name:'Синтетический '+prefix,
        kind:'regular',dose:'условная единица',from:null,to:null,
        dailyIntakes:1,createdAt:created};
      validatePressure(p);validateMed(m);
      await addRecord('pressures',p);await addRecord('medications',m);
      const i={id:'SYN_'+prefix+'_INTAKE_001',medId:m.id,date,
        takenAtLocal:date+'T00:02',markedAt:created,status:'active',dailySlot:1};
      await changeIntake('marked',i);
      await reload();
      return {medId:m.id,intakeId:i.id,pressureId:p.id};
    }""",prefix)

def open_site(context,server):
    page=context.new_page()
    page.on("pageerror",lambda e:PAGE_ERRORS.append(str(e)))
    page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
              wait_until="domcontentloaded",timeout=30000)
    wait_ready(page)
    return page

def run():
    check("exact sandbox ref",os.environ.get("GITHUB_REF"),BRANCH)
    check("synthetic guard",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
    for path,sha in PINNED.items():
        got=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
        check("source blob "+path,got,sha)
    check("WebKit backup path retained","async function createBackup()" in (ROOT/"site/app.js").read_text())
    check("atomic merge path retained","function atomicMerge(data)" in (ROOT/"site/app.js").read_text())
    RESULTS.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pae04_cp40_backup_webkit_") as tmp:
        a=prepare_origin(tmp,"source");b=prepare_origin(tmp,"destination")
        try:
            with sync_playwright() as pw:
                browser=pw.webkit.launch(headless=True)
                try:
                    context=browser.new_context(viewport={"width":390,"height":844},
                        device_scale_factor=2,is_mobile=True,has_touch=True,
                        locale="ru-RU",service_workers="block",accept_downloads=True)
                    try:
                        source=open_site(context,a)
                        check("source origin starts empty",sum(len(v) for v in raw_db(source).values()),0)
                        src_ids=seed(source,"ALPHA")
                        src_data=raw_db(source)
                        check("source has 4 synthetic records",sum(len(v) for v in src_data.values()),4)
                        source.locator('.nav-item[data-page="settings"]').click()
                        with source.expect_download(timeout=20000) as action:
                            source.locator("#export-button").click()
                        backup_download=action.value
                        backup_path=Path(tmp)/"source_export.json"
                        backup_download.save_as(str(backup_path))
                        check("export file exists",backup_path.is_file())
                        check("export file nonempty",backup_path.stat().st_size>100)
                        export=load_verified_backup(backup_path)
                        check("backup data byte-equivalent to source",export["data"],src_data)
                        check("backup has expected format",export["format"],
                              "pae04.healthtracker.synthetic-backup")
                        FACTS["export_sha256"]=export["sha256"]
                        source.locator("#verify-file").set_input_files(str(backup_path))
                        source.locator("#verify-result .verify-pass").wait_for(timeout=15000)
                        check("UI independently verifies exported JSON",
                              "SHA-256 совпадает" in source.locator("#verify-result").inner_text())
                        source.close()

                        dest=open_site(context,b)
                        check("destination origin starts empty",sum(len(v) for v in raw_db(dest).values()),0)
                        dst_ids=seed(dest,"BETA")
                        baseline=raw_db(dest)
                        check("destination has 4 different synthetic records",
                              sum(len(v) for v in baseline.values()),4)
                        check("source and target are different origins",a.server_port!=b.server_port)
                        dest.locator('.nav-item[data-page="settings"]').click()
                        # Intentionally corrupt file contents without changing signed SHA.
                        tampered=json.loads(backup_path.read_text(encoding="utf-8"))
                        tampered["data"]["pressures"][0]["systolic"]=160
                        corrupt_path=Path(tmp)/"tampered_qa_only.json"
                        corrupt_path.write_text(json.dumps(tampered,ensure_ascii=False),encoding="utf-8")
                        dest.locator("#import-file").set_input_files(str(corrupt_path))
                        dest.wait_for_function("""() => document.querySelector('#import-preview')?.textContent.includes('SHA-256')""",
                                               timeout=15000)
                        check("corrupted JSON rejected",
                              "Ошибка:" in dest.locator("#import-preview").inner_text())
                        check("import stays disabled after invalid SHA",
                              dest.locator("#import-button").is_disabled())
                        check("no writes on tamper",raw_db(dest),baseline)

                        dest.locator("#import-file").set_input_files(str(backup_path))
                        dest.locator("#checkpoint-button").wait_for(state="visible")
                        dest.wait_for_function("""() => !document.querySelector('#checkpoint-button').disabled""",timeout=15000)
                        check("preview reports four new records",
                              "Новых: 4" in dest.locator("#import-preview").inner_text())
                        check("preview has zero conflicts",
                              "Конфликтов: 0" in dest.locator("#import-preview").inner_text())
                        check("owner ack unchecked by default",
                              not dest.locator("#checkpoint-ack").is_checked())
                        check("import locked before checkpoint",
                              dest.locator("#import-button").is_disabled())
                        check("preview caused no database changes",raw_db(dest),baseline)
                        with dest.expect_download(timeout=20000) as download_info:
                            dest.locator("#checkpoint-button").click()
                        checkpoint_path=Path(tmp)/"checkpoint_before_import.json"
                        download_info.value.save_as(str(checkpoint_path))
                        check("checkpoint file exists",checkpoint_path.is_file())
                        checkpoint=load_verified_backup(checkpoint_path)
                        check("checkpoint exactly matches destination baseline",
                              checkpoint["data"],baseline)
                        FACTS["checkpoint_sha256"]=checkpoint["sha256"]
                        check("import blocked until user acknowledges checkpoint",
                              dest.locator("#import-button").is_disabled())
                        check("checkpoint ack enabled",dest.locator("#checkpoint-ack").is_enabled())
                        # Only after the file exists and independent SHA is verified,
                        # simulate the owner's explicit acknowledgement in isolated QA.
                        dest.locator("#checkpoint-ack").check()
                        check("import enabled after verified checkpoint",
                              dest.locator("#import-button").is_enabled())
                        dialogs=[]
                        def accept(dialog):
                            dialogs.append(dialog.message)
                            dialog.accept()
                        dest.on("dialog",accept)
                        dest.locator("#import-button").click()
                        dest.wait_for_function("""() =>
                           document.querySelector('#import-preview')?.textContent.includes('Добавлено 4 записей')""",
                           timeout=20000)
                        check("explicit import confirm happened",len(dialogs),1)
                        check("added exactly 4 records",
                              "Добавлено 4 записей" in dest.locator("#import-preview").inner_text())
                        merged=raw_db(dest)
                        check("restored database has 8 records",
                              sum(len(v) for v in merged.values()),8)
                        for table in sorted(src_data):
                            by_id={x["id"]:x for x in merged[table]}
                            check("imported "+table,all(by_id.get(x["id"])==x for x in src_data[table]))
                            check("preserved baseline "+table,
                                  all(by_id.get(x["id"])==x for x in baseline[table]))
                        check("all original audit events remain",
                              len(merged["intakeEvents"]),2)
                        check("import contains both medication IDs",
                              sorted(x["id"] for x in merged["medications"]),
                              sorted([src_ids["medId"],dst_ids["medId"]]))
                        FACTS["merged_db_sha256"]=digest(merged)
                        dest.reload(wait_until="domcontentloaded",timeout=30000)
                        wait_ready(dest)
                        independent=raw_db(dest)
                        check("all records survived WebKit page reload",independent,merged)
                        check("independent post-reload SHA-256",
                              digest(independent),FACTS["merged_db_sha256"])
                        dest.locator('.nav-item[data-page="settings"]').click()
                        dest.screenshot(path=str(RESULTS/"CP40_BACKUP_WK_R1_verified_ui.png"),full_page=True)
                        check("no JS page errors",PAGE_ERRORS,[])
                        dest.close()
                    finally:context.close()
                finally:browser.close()
        finally:
            a.shutdown();b.shutdown()

if __name__=="__main__":
    status="NOT_RUN";errors=[]
    try:run();status="PASS"
    except Exception as exc:
        status="FAIL" if CHECKS else "BLOCKED"
        errors.append(type(exc).__name__+": "+str(exc))
        traceback.print_exc()
    RESULTS.mkdir(parents=True,exist_ok=True)
    report={"checkpoint":"CP40 Backup WebKit-R1","status":status,
            "environment":"Linux Playwright 1.65.1 WebKit; iPhone viewport 390x844",
            "scope":"Two isolated synthetic IndexedDB origins; real export, verified checkpoint, additive import",
            "checks":CHECKS,"errors":errors,"browser_errors":PAGE_ERRORS,
            "synthetic_only":True,"hashes":FACTS}
    (RESULTS/"CP40_BACKUP_WK_R1_report.json").write_text(
      json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CP40_BACKUP_WEBKIT_R1 "+json.dumps({
      "status":status,"passed":sum(x["result"]=="PASS" for x in CHECKS),
      "failed":sum(x["result"]=="FAIL" for x in CHECKS),"errors":errors},
      ensure_ascii=False))
    sys.exit(0 if status=="PASS" else 1)

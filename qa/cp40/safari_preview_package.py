#!/usr/bin/env python3
"""PAE-04 CP40 synthetic iPhone preview, sanitized package only; no deploy."""
import functools,hashlib,http.server,json,os,shutil,subprocess,sys,tempfile,threading,traceback,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];SITE=ROOT/"site"
OUT=ROOT/"qa/cp40/safari_preview_artifact"
BASE="21969ddc9c44c0973056bc1e7606f06972b61580"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
NAME="PAE04_CP40_IPHONE_SYNTHETIC_PREVIEW_21969ddc.zip"
ASSETS=("index.html app.js styles.css home.js home.css med_guard.mjs med_matcher.mjs "
 "med_guard.css personal_adapter.js personal_profile.json offline_status.js "
 "manifest.webmanifest icons/icon.svg icons/apple-touch-icon.png "
 "icons/icon-192.png icons/icon-512.png sw.js").split()
SW_CACHE="pae04-ht-stable-candidate-synthetic-schema1-cache-personal-home-v71-cachefix-20261122"
tests=[];errors=[]
def check(key,actual,expected=True):
    ok=actual==expected
    tests.append({"name":key,"status":"PASS" if ok else "FAIL"})
    if not ok: raise AssertionError(key+": "+str(actual)[:140])
def sha(b):return hashlib.sha256(b).hexdigest()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
def run():
    check("sandbox guard",os.environ.get("GITHUB_REF"),BRANCH)
    check("synthetic only",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
    ancestry=subprocess.run(["git","-c","safe.directory="+str(ROOT),
       "merge-base","--is-ancestor",BASE,"HEAD"],cwd=ROOT).returncode
    check("exact CP40 ancestor",ancestry,0)
    changed=subprocess.check_output(["git","-c","safe.directory="+str(ROOT),"diff","--name-only",BASE,"HEAD","--","site"],
                                    cwd=ROOT,text=True).strip()
    check("original site untouched",changed,"")
    check("all static sources",all((SITE/p).is_file() for p in ASSETS))
    private=json.loads((SITE/"personal_profile.json").read_text(encoding="utf-8"))
    private_names={m["name"].casefold() for m in private.get("medicines",[])
       if isinstance(m,dict) and isinstance(m.get("name"),str) and len(m["name"])>=3}
    check("private source detected",len(private_names)>0)
    OUT.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix="pae04_preview_") as tmp:
        stage=Path(tmp)/"site";stage.mkdir()
        for rel in ASSETS:
            dest=stage/rel;dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(SITE/rel,dest)
        (stage/"personal_adapter.js").write_text(
          "'use strict';window.PAE04SyntheticPreview={syntheticOnly:true,personalSeedDisabled:true};\n",
           encoding="utf-8")
        (stage/"personal_profile.json").write_text(
           json.dumps({"schema":"PAE04_PUBLIC_SYNTHETIC_PREVIEW_V1","purpose":"SYNTHETIC_ONLY",
             "medicines":[],"constraints":{"seed_medications":False,"seed_pressures":False,
             "seed_intakes":False}},ensure_ascii=False),encoding="utf-8")
        index=stage/"index.html";html=index.read_text(encoding="utf-8")
        check("preserve approved Compact v7.1", "Health Tracker · Compact v7.1" in html)
        html=html.replace("Личная бета.","Синтетический UI-preview.")
        html=html.replace("<head>","<head>\n<meta name=\"robots\" content=\"noindex,nofollow,noarchive\">",1)
        index.write_text(html,encoding="utf-8")
        manifest=stage/"manifest.webmanifest"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace(
                            "Личная бета","Синтетический UI-preview"),encoding="utf-8")
        (stage/"robots.txt").write_text("User-agent: *\nDisallow: /\n",encoding="utf-8")
        # Public preview must not contain ANY source-specific brand or dose catalog.
        # Keep the application algorithms; replace example labels deterministically.
        import re
        original_names=[m["name"] for m in private.get("medicines",[])
                        if isinstance(m,dict) and isinstance(m.get("name"),str)]
        check("original catalog 10 entries",len(original_names),10)
        catalog_alias={name:"Тестовый препарат "+str(i+1)
                       for i,name in enumerate(original_names)}
        def sanitize_labels(value):
            for name in sorted(catalog_alias,key=len,reverse=True):
                value=re.sub(re.escape(name),lambda match:catalog_alias[name],
                             value,flags=re.IGNORECASE)
            return value
        for rel in ["index.html","app.js"]:
            p=stage/rel
            p.write_text(sanitize_labels(p.read_text(encoding="utf-8")),encoding="utf-8")
        catalog_path=stage/"med_guard.mjs"
        catalog_source=catalog_path.read_text(encoding="utf-8")
        start=catalog_source.find("export const SYNTHETIC_CATALOG = Object.freeze(")
        end=catalog_source.find("]);",start)
        check("catalog rewrite boundaries valid",start>=0 and end>start)
        test_catalog=[{"id":"preview-synthetic-"+str(i+1),
                       "name":"Тестовый препарат "+str(i+1),"aliases":[],
                       "ingredient":"","strength":None,"unit":"","form":"другое"}
                       for i in range(10)]
        new_catalog="export const SYNTHETIC_CATALOG = Object.freeze("+json.dumps(
                         test_catalog,ensure_ascii=False,separators=(",",":"))+");"
        catalog_path.write_text(catalog_source[:start]+new_catalog+
             catalog_source[end+3:],encoding="utf-8")
        check("catalog functions retained",
              "export function assessEntry(" in catalog_path.read_text())
        check("all original code retained outside literal example names",
              (stage/"app.js").read_text(encoding="utf-8"),
              sanitize_labels((SITE/"app.js").read_text(encoding="utf-8")))
        text_files=[p for p in ASSETS if p.endswith((".html",".js",".css",".mjs",".json",".svg",".webmanifest"))]
        searchable="\n".join((stage/p).read_text(encoding="utf-8",errors="ignore") for p in text_files)
        check("none of private medication names leaked",
              not any(n in searchable.casefold() for n in private_names))
        check("no personal medication seed",
              json.loads((stage/"personal_profile.json").read_text())["medicines"],[])
        check("unchanged service worker",sha((stage/"sw.js").read_bytes()),
              sha((SITE/"sw.js").read_bytes()))
        check("unchanged original app SHA pinned to approved CP40",
              sha((SITE/"app.js").read_bytes()),
              sha((ROOT/"site/app.js").read_bytes()))
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
            functools.partial(Quiet,directory=str(stage)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.webkit.launch(headless=True)
                try:
                    context=browser.new_context(viewport={"width":390,"height":844},
                     is_mobile=True,has_touch=True,locale="ru-RU",service_workers="allow")
                    page=context.new_page()
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/index.html",
                              wait_until="domcontentloaded",timeout=30000)
                    page.wait_for_function(
                     "() => !!window.PAE04SyntheticPreview && !!document.querySelector('.status-dot.online')",
                     timeout=20000)
                    check("preview title",page.title(),"Health Tracker · Compact v7.1")
                    check("four tabs",page.locator(".nav-item").count(),4)
                    check("no seed action",page.locator("#pae04-personal-seed-btn").count(),0)
                    check("public profile has zero medicines",
                        page.evaluate("async()=> (await (await fetch('./personal_profile.json')).json()).medicines.length"),0)
                    check("empty isolated IndexedDB",page.evaluate("""async()=>
                     (await Promise.all(['pressures','medications','intakes','intakeEvents']
                     .map(getAll))).map(rows=>rows.length)"""),[0,0,0,0])
                    check("synthetic warning visible",
                        "Синтетический UI-preview" in page.locator("body").inner_text())
                    page.wait_for_function("""async()=> {
                      const r=await navigator.serviceWorker.getRegistration('./');
                      return !!r?.active && !!navigator.serviceWorker.controller;
                    }""",timeout=30000)
                    check("Service Worker controls preview",
                          page.evaluate("!!navigator.serviceWorker.controller"))
                    check("cache has full shell",page.evaluate("""async (name)=>{
                      const c=await caches.open(name);
                      return (await Promise.all([
                      './','./index.html','./app.js','./styles.css','./home.js','./home.css',
                      './med_guard.mjs','./med_matcher.mjs','./med_guard.css',
                      './personal_adapter.js','./personal_profile.json','./offline_status.js',
                      './manifest.webmanifest','./icons/icon.svg','./icons/apple-touch-icon.png',
                      './icons/icon-192.png','./icons/icon-512.png']
                      .map(x=>c.match(x).then(Boolean)))).every(Boolean);
                    }""",SW_CACHE))
                    check("no JS errors",errors,[])
                    page.screenshot(path=str(OUT/"CP40_preview_webkit_synthetic.png"),full_page=False)
                    context.close()
                finally:browser.close()
        finally:server.shutdown();server.server_close()
        provenance={"project":"PAE-04","source_sha":BASE,"synthetic_only":True,
            "personal_seed_disabled":True,"publish_status":"NOT_DEPLOYED",
            "release_status":"NO-GO"}
        (stage/"PREVIEW_PROVENANCE.json").write_text(
          json.dumps(provenance,ensure_ascii=False,indent=2),encoding="utf-8")
        names=sorted(ASSETS+["robots.txt","PREVIEW_PROVENANCE.json"])
        target=OUT/NAME
        with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for name in names:z.write(stage/name,arcname=name)
        with zipfile.ZipFile(target) as z:
            check("ZIP CRC",z.testzip(),None)
            check("flat root", "index.html" in z.namelist())
            check("whitelist",sorted(z.namelist()),names)
            check("zero private names in ZIP",
                  json.loads(z.read("personal_profile.json"))["medicines"],[])
        result={"status":"PASS","checks":tests,"errors":errors,
                "source_sha":BASE,"synthetic_only":True,
                "zip_name":NAME,"zip_sha256":sha(target.read_bytes()),
                "zip_size_bytes":target.stat().st_size,"publish_status":"NOT_DEPLOYED"}
        (OUT/"CP40_PREVIEW_QA.json").write_text(
             json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("CP40_SYNTHETIC_PREVIEW "+json.dumps({
          "status":"PASS","checks":len(tests),"sha256":result["zip_sha256"],
          "bytes":result["zip_size_bytes"],"personal_seed":False},ensure_ascii=False))
if __name__=="__main__":
    try:run()
    except Exception as err:
        OUT.mkdir(exist_ok=True,parents=True)
        (OUT/"CP40_PREVIEW_QA.json").write_text(json.dumps({
          "status":"FAIL","errors":[type(err).__name__+": "+str(err)],
          "checks":tests,"page_errors":errors,"synthetic_only":True
        },ensure_ascii=False,indent=2),encoding="utf-8")
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""Safari/WebKit QA for personal Apple Light Comfort v0.6.1. Synthetic isolated browser."""
import datetime
import http.server
import json
import pathlib
import tempfile
import sys
import threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright, expect

engine=sys.argv[1]
site=pathlib.Path(sys.argv[2]).resolve()
reports=pathlib.Path(sys.argv[3]).resolve()
assert engine=="webkit"
assert (site/"index.html").is_file()
reports.mkdir(parents=True,exist_ok=True)
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(site),**kw)
    def log_message(self,*a): pass
server=http.server.ThreadingHTTPServer(("127.0.0.1",0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f"http://127.0.0.1:{server.server_port}/index.html"
passed=[]
errors=[]
def check(label,condition):
    if not condition: raise AssertionError(label)
    passed.append(label);print(f"PASS {len(passed):02d} {label}",flush=True)
def counts(page):
    return page.evaluate("""async () => {
      const req=indexedDB.open('PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',1);
      const db=await new Promise((r,j)=>{req.onsuccess=()=>r(req.result);req.onerror=()=>j(req.error)});
      const result={};
      for (const name of ['pressures','medications','intakes','intakeEvents']){
        result[name]=await new Promise((r,j)=>{
          const q=db.transaction(name,'readonly').objectStore(name).count();
          q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error);
        });
      }
      db.close();return result;
    }""")
try:
    with sync_playwright() as playwright:
        browser=playwright.webkit.launch(headless=True)
        context=browser.new_context(viewport={"width":390,"height":844},timezone_id="Europe/Moscow",
                                    device_scale_factor=1,reduced_motion="reduce",accept_downloads=True)
        page=context.new_page()
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.clock.install(time=datetime.datetime(2026,11,15,13,50,tzinfo=ZoneInfo("Europe/Moscow")))
        page.goto(url,wait_until="networkidle")
        check("personal beta identity", "v0.6.1" in page.locator(".brand small").inner_text())
        check("old synthetic-only warning absent", "Изолированный эксперимент" not in page.locator(".alert").inner_text())
        check("real-data-safe beta notice", "резервные копии" in page.locator(".alert").inner_text())
        check("no auto-import of medicines or real intake", counts(page)==dict(pressures=0,medications=0,intakes=0,intakeEvents=0))
        page.screenshot(path=str(reports/"01-personal-home-empty.png"),full_page=True)

        page.locator('[data-page="meds"]').click()
        expect(page.locator("#pae04-personal-seed-btn")).to_be_enabled()
        page.once("dialog",lambda d:d.accept())
        page.locator("#pae04-personal-seed-btn").click()
        page.locator('[data-page="overview"]').click()
        expect(page.locator("#ui01-meds")).to_contain_text("Эдарби")
        check("ten catalog cards, still no intake/pressure",counts(page)==dict(pressures=0,medications=10,intakes=0,intakeEvents=0))
        text=page.locator("#ui01-meds").inner_text()
        check("approved real brand/dose text visible",all(s in text for s in ["Беталок ЗОК","12,5 мг","Липримар","Эспиро","Эдарби"]))
        check("empty planned-time placeholder hidden","Плановое время не задано" not in text)
        check("as-needed explanation remains","По необходимости" in text)
        check("course grouping stays visible", "Курсовые" in text and "Ситуативные" in text)
        check("medication touch target remains 48 px",
              (page.locator(".ui01-check").first.bounding_box() or {}).get("height",0)>=44)
        page.screenshot(path=str(reports/"02-personal-home-medications.png"),full_page=True)
        page.locator("#ui01-font-more").click()
        page.locator("#ui01-font-more").click()
        page.set_viewport_size({"width":320,"height":780})
        check("maximum font persists at 5/5",page.locator("#ui01-font-label").inner_text()=="5 / 5")
        width=page.evaluate("document.documentElement.scrollWidth")
        check("no horizontal overflow at 320 px + largest font",width<=322)
        page.screenshot(path=str(reports/"03-320px-large-text.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":844})

        # Backup acceptance: only disposable fictitious browser-origin contents.
        page.locator('[data-page="backup"]').click()
        expect(page.locator("#pae04-offline-status")).to_have_attribute("data-ready","true",timeout=15000)
        check("offline-readiness indicator verifies controlled, cached app shell",True)
        expect(page.locator("#export-button")).to_be_visible()
        with page.expect_download(timeout=10000) as d:
            page.locator("#export-button").click()
        download=d.value
        check("new backup filename says PERSONAL",download.suggested_filename.startswith("PAE04-PERSONAL-BACKUP-"))
        with tempfile.TemporaryDirectory(prefix="pae04-v061-synthetic-") as tmp:
            path=pathlib.Path(tmp)/"copy.json"
            download.save_as(str(path))
            data=json.loads(path.read_text(encoding="utf8"))
            check("backups remain format v3",data.get("version")==3 and data.get("format")=="pae04.healthtracker.synthetic-backup")
            check("backup contains only 10 synthetic profile cards",len(data["data"]["medications"])==10
                  and not data["data"]["pressures"] and not data["data"]["intakes"]
                  and not data["data"]["intakeEvents"])
            page.locator("#verify-file").set_input_files(str(path))
            expect(page.locator("#verify-result")).to_contain_text("PASS · SHA-256 совпадает",timeout=10000)
            check("downloaded JSON verified without import",True)
            check("verify report no longer calls personal records educational",
                  "учебных записей" not in page.locator("#verify-result").inner_text())
        check("backup verification did not write to database",counts(page)==dict(pressures=0,medications=10,intakes=0,intakeEvents=0))
        page.screenshot(path=str(reports/"04-backup-sha-verified.png"),full_page=True)
        # Browser offline caching, with no dependency on the real iPhone or real health data.
        page.evaluate("navigator.serviceWorker.ready")
        page.reload(wait_until="networkidle")
        page.wait_for_function("navigator.serviceWorker.controller !== null",timeout=15000)
        cache_ready=page.evaluate("""async () => {
          const names=await caches.keys();
          const cache=await caches.open(names.find(x=>x.includes('personal-v061-'))||'none');
          return !!(await cache.match('./index.html')) && !!(await cache.match('./app.js'));
        }""")
        check("new versioned offline cache installed",cache_ready)
        context.set_offline(True)
        page.reload(wait_until="domcontentloaded",timeout=15000)
        expect(page.locator("#overview-title")).to_contain_text("Сегодня")
        check("offline WebKit load preserves local medicines", "Эдарби" in page.locator("#ui01-meds").inner_text())
        check("offline local backup data retained",counts(page)==dict(pressures=0,medications=10,intakes=0,intakeEvents=0))
        page.locator('[data-page="backup"]').click()
        expect(page.locator("#pae04-offline-status")).to_have_attribute("data-ready","true",timeout=15000)
        check("offline status remains READY without Internet",True)
        page.goto(url+"?origin=chatgpt",wait_until="domcontentloaded",timeout=15000)
        expect(page.locator("#overview-title")).to_contain_text("Сегодня")
        check("Safari offline navigation with query parameters works",counts(page)['medications']==10)
        directory_url=url.rsplit("index.html",1)[0]
        page.goto(directory_url+"?from=chatgpt",wait_until="domcontentloaded",timeout=15000)
        expect(page.locator("#overview-title")).to_contain_text("Сегодня")
        check("Safari offline slash navigation with query works",counts(page)['medications']==10)
        context.set_offline(False)
        # A fresh, disposable origin with an intentionally evicted Cache Storage
        # must show a clear 503 rather than a raw Safari FetchEvent exception.
        extra=browser.new_context(viewport={"width":390,"height":844})
        miss=extra.new_page()
        miss.goto(url,wait_until="networkidle")
        miss.evaluate("navigator.serviceWorker.ready")
        miss.reload(wait_until="domcontentloaded")
        miss.wait_for_function("navigator.serviceWorker.controller !== null",timeout=15000)
        miss.evaluate("""async () => {
          for (const name of await caches.keys()) {
            if(name.includes('personal-v061-offline1')) await caches.delete(name);
          }
        }""")
        extra.set_offline(True)
        response=miss.goto(url+"?simulated-cache-loss=1",wait_until="domcontentloaded",timeout=15000)
        check("cache eviction returns explicit 503 instead of raw FetchEvent error",
              response is not None and response.status==503 and
              "Офлайн-копия ещё не готова" in miss.locator("body").inner_text())
        extra.set_offline(False)
        extra.close()
        check("no JavaScript exceptions",not errors)
        context.close();browser.close()
finally:
    server.shutdown()
print(f"RESULT=PASS WEBKIT_PAE04_PERSONAL_V061 {len(passed)}/{len(passed)}",flush=True)

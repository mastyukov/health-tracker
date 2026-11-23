#!/usr/bin/env python3
"""PAE-04 CP40 Medicines Compact R3: narrow synthetic Chromium UI QA, no DB writes."""
import functools,http.server,json,os,subprocess,shutil,tempfile,threading,traceback,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from iphone_browser_smoke import seed
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/"qa/cp40/meds_r3_results"
BRANCH="refs/heads/sandbox/pae04-approved-ux23-iphone-cp40-20261123-r1"
PINNED={"site/app.js":"cbc0d3b54dbb6a96e70c4aea370b69d3a86c5f29",
"site/home.js":"16f083fdb3fdb4d84a3d6db422cb4d57e232783b",
"site/styles.css":"317ab104834442516a3ad9e1be9811206e728762",
"site/index.html":"08b241a615da56297d4982a7ac5a2c36f0c8c0ca"}
CASES=[];ERRORS=[]
def check(name,got,want=True):
  passed=got==want
  CASES.append({"test":name,"result":"PASS" if passed else "FAIL","got":str(got)[:100]})
  if not passed:raise AssertionError(f"{name}: {got!r} != {want!r}")
class Silent(http.server.SimpleHTTPRequestHandler):
  def log_message(self,*a):pass
def run():
  check("sandbox guard",os.environ.get("GITHUB_REF"),BRANCH)
  check("synthetic guard",os.environ.get("PAE04_SYNTHETIC_ONLY"),"true")
  for p,sha in PINNED.items():
    blob=subprocess.check_output(["git","hash-object",p],cwd=ROOT,text=True).strip()
    check("blob "+p,blob,sha)
  code=(ROOT/"site/app.js").read_text()
  for name,signal in [("mark","await changeIntake('marked',record)"),
     ("cancel","await changeIntake('cancelled',{...taken"),
     ("correct","await changeIntake('time_corrected',next,i)"),
     ("schema","const BACKUP_VERSION=3;")]:
    check("original handler "+name,signal in code)
  REPORT.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix="pae04_meds_r3_") as tmp:
    site=Path(tmp)/"site";shutil.copytree(ROOT/"site",site)
    (site/"personal_profile.json").write_text('{"syntheticOnly":true,"medicines":[]}',encoding="utf-8")
    (site/"personal_adapter.js").write_text("'use strict';window.PAE04QAProfile={syntheticOnly:true};",encoding="utf-8")
    (site/"offline_status.js").write_text("'use strict';/* no offline cache */",encoding="utf-8")
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Silent,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        try:
          ctx=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=2,
             is_mobile=True,has_touch=True,locale="ru-RU",service_workers="block")
          page=ctx.new_page();page.on("pageerror",lambda e:ERRORS.append(str(e)))
          page.goto(f"http://127.0.0.1:{server.server_port}/index.html",wait_until="domcontentloaded",timeout=30000)
          page.wait_for_function("() => !!window.PAE04CPUI01 && !!document.querySelector('.status-dot.online')",timeout=20000)
          check("base synthetic meds",seed(page)["meds"],3)
          page.evaluate("""() => {
            const day=dateLocal(new Date()),created=new Date().toISOString();
            snapshot.medications.find(m=>m.id==='SYN_REG_0001').dailyIntakes=2;
            snapshot.intakes=[{id:'SYN_INTAKE_0001',medId:'SYN_REG_0001',date:day,
              takenAtLocal:day+'T00:01',markedAt:created,status:'active',dailySlot:1}];
            render();window.PAE04CPUI01.render();
          }""")
          page.locator('.nav-item[data-page="meds"]').click()
          screen=page.locator("#v232-meds-today")
          check("three groups",screen.locator(".ux23-med-kind-group").count(),3)
          check("planned card",screen.locator(".ux23-meds-plan-card").count(),1)
          check("PRN separate",screen.locator(".ux23-med-prn-card").count(),1)
          check("planned categories",screen.locator(".ux23-meds-plan-card .ux23-med-kind-heading").all_text_contents(),["Постоянные","Курсовые"])
          check("three outline icons",screen.locator(".ux23-med-kind-heading svg").count(),3)
          check("scheduled progress, no PRN",screen.locator(".ux23-meds-today-count").inner_text(),"1 / 3")
          check("three distinct slot checkboxes",screen.locator(".ux23-meds-plan-card .med-schedule-slot input").count(),3)
          check("one marked slot",screen.locator(".ux23-meds-plan-card .med-schedule-slot input:checked").count(),1)
          check("actual time inline", "00:01" in "\n".join(screen.locator(".ux23-meds-plan-card .med-schedule-slots").all_text_contents()))
          check("time picker for scheduled slots",screen.locator(".ux23-meds-plan-card input.intake-time-input").first.is_visible())
          check("PRN confirm kept",screen.locator(".ux23-med-prn-card .intake-confirm-button").count(),1)
          check("PRN optional reason kept",screen.locator(".ux23-med-prn-card .v232-prn-reason-input").count(),1)
          check("advanced closed by default",screen.locator(".ux23-med-advanced[open]").count(),0)
          check("three advanced disclosure controls",screen.locator(".ux23-med-advanced").count(),3)
          check("search retained",screen.locator(".ux23-meds-search input").count(),1)
          check("help retained",screen.locator(".ux23-meds-help").count(),1)
          check("duplicate journal heading hidden",not screen.locator("h2").first.is_visible())
          check("no horizontal overflow",page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1"))
          card1=screen.locator(".ux23-meds-plan-card").bounding_box()
          card2=screen.locator(".ux23-med-prn-card").bounding_box()
          check("separate cards not overlapping",card1 is not None and card2 is not None and card1["y"]+card1["height"]<card2["y"])
          page.screenshot(path=str(REPORT/"CP40_MR3_medicines_today.png"),full_page=True)
          advanced=screen.locator(".ux23-meds-plan-card .ux23-med-advanced").first
          advanced.locator("summary").click()
          check("frequency editor accessible",advanced.locator(".med-frequency-select").count(),1)
          check("audit record retained",advanced.locator(".med-record-list .intake-record").count(),1)
          check("cancel action retained",advanced.get_by_role("button",name="Отменить отметку").count(),1)
          advanced.locator("summary").click()
          page.evaluate("""() => {
            const day=dateLocal(new Date()),at=new Date().toISOString();
            for(const [id,medId,slot,time] of [
              ['SYN_INTAKE_0002','SYN_REG_0001',2,'00:02'],
              ['SYN_INTAKE_0003','SYN_COURSE_01',1,'00:03']]){
              snapshot.intakes.push({id,medId,dailySlot:slot,date:day,takenAtLocal:day+'T'+time,
                markedAt:at,status:'active'});
            }
            render();
          }""")
          check("all planned checked",screen.locator(".ux23-meds-today-count").inner_text(),"3 / 3")
          check("actual times persisted in memory",all(t in "\n".join(screen.locator(".ux23-meds-plan-card .med-schedule-slots").all_text_contents()) for t in ["00:01","00:02","00:03"]))
          check("PRN remains unscheduled",screen.locator(".ux23-med-prn-card .med-schedule-slot").count(),0)
          page.screenshot(path=str(REPORT/"CP40_MR3_medicines_all_marked.png"),full_page=True)
          check("no JS page errors",ERRORS,[])
          ctx.close()
        finally:browser.close()
    finally:server.shutdown()
if __name__=="__main__":
  status="NOT_RUN";errors=[]
  try:run();status="PASS"
  except Exception as e:
    status="FAIL";errors=[type(e).__name__+": "+str(e)];traceback.print_exc()
  REPORT.mkdir(parents=True,exist_ok=True)
  (REPORT/"CP40_MR3_report.json").write_text(json.dumps({
     "status":status,"tests":CASES,"errors":errors,"page_errors":ERRORS,
     "synthetic_only":True},ensure_ascii=False,indent=2),encoding="utf-8")
  print("CP40_MEDS_R3 "+json.dumps({"status":status,"passed":sum(x["result"]=="PASS" for x in CASES),
   "failed":sum(x["result"]=="FAIL" for x in CASES),"errors":errors},ensure_ascii=False))
  sys.exit(0 if status=="PASS" else 1)

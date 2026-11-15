#!/usr/bin/env python3
"""PAE-04 v0.6.1: immutable storage invariants and exact cosmetic JS diff."""
import json
import subprocess
import sys
from pathlib import Path

site=Path(sys.argv[1]).resolve()
base="a87acafeecb6a41ac1779e65d2740b4e16cb9a5f"
def old(name):
    return subprocess.check_output(["git","show",f"{base}:site/{name}"],text=True)
def current(name):
    return (site/name).read_text(encoding="utf8")
def check(label,cond):
    if not cond:raise AssertionError("FAIL "+label)
    print("PASS "+label,flush=True)
def once(source, old, new):
    assert source.count(old)==1,(old[:100],source.count(old))
    return source.replace(old,new,1)

app=old("app.js")
for a,b in (
    ("PAE04-SYNTHETIC-BACKUP-","PAE04-PERSONAL-BACKUP-"),
    ("PAE04-SYNTHETIC-PREIMPORT-CHECKPOINT-","PAE04-PERSONAL-PREIMPORT-CHECKPOINT-"),
):
    app=once(app,a,b)
check("Two old educational-result labels",app.count(" учебных записей")==2)
app=app.replace(" учебных записей"," записей")
check("All application logic identical except three backup labels",app==current("app.js"))
home=once(old("home.js"),
    "desc.append(element('span','ui01-muted',m.kind==='asNeeded'?'По необходимости':'Плановое время не задано'));",
    "if(m.kind==='asNeeded')desc.append(element('span','ui01-muted','По необходимости'));")
check("Home medicine time display logic untouched except missing schedule hint",home==current("home.js"))
adapter=once(old("personal_adapter.js"),"Мои препараты · персональный предпросмотр","Мои препараты · личный справочник")
check("Personal profile transaction code untouched",adapter==current("personal_adapter.js"))
sw=once(old("sw.js"),"cache-cpreal01-20261115","cache-personal-v061-20261115")
check("Service Worker unchanged except versioned cache",sw==current("sw.js"))
css0=old("home.css");css=current("home.css")
check("Original Apple Light Comfort CSS preserved",css.startswith(css0))
check("Added only light-theme styling, no removed rules",
      "approved Apple Light Comfort" in css[len(css0):] and "display:none" not in css[len(css0):])
manifest0=json.loads(old("manifest.webmanifest"))
manifest=json.loads(current("manifest.webmanifest"))
for key in ("name","short_name","description"):manifest0.pop(key);manifest.pop(key)
check("App identity/scope/icons unchanged",manifest0==manifest)
html0=old("index.html");html=current("index.html")
check("Version visible and old synthetic-only warning gone",
      'v0.6.1' in html and 'Личная бета-версия.' in html
      and 'Изолированный эксперимент.' not in html
      and 'Только тестовые данные' not in html
      and 'Настоящие медицинские сведения вводить нельзя.' not in html)
check("Protected HTML structure unchanged",
      all(html0.count(s)==html.count(s) for s in (
          'id="page-overview"','id="page-pressure"','id="page-meds"',
          'id="page-backup"','id="export-button"','id="verify-file"',
          'id="import-button"','id="checkpoint-button"'))
      and html0.count("<script")==html.count("<script"))
check("Internal backup format v3 and database name unchanged",
      "const BACKUP_VERSION=3" in app and
      "const DB_VERSION=1" in app and
      "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app and
      "const BACKUP_FORMAT='pae04.healthtracker.synthetic-backup'" in app and
      "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app)
check("No remote telemetry added to JS",all("https://" not in current(n) for n in ("app.js","home.js","personal_adapter.js","sw.js")))
diff=subprocess.check_output(["git","diff","--name-only",base,"HEAD","--","site/"],text=True).splitlines()
allowed={
"site/index.html","site/home.js","site/home.css","site/app.js",
"site/manifest.webmanifest","site/personal_adapter.js","site/sw.js"
}
check("Only seven approved site source files changed",set(diff)==allowed)
print("RESULT=PASS PAE04_UI_V061_INVARIANTS",flush=True)

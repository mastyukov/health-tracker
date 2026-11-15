#!/usr/bin/env python3
"""PAE-04 RC1: independently verify copied, pinned personal PWA without modifying data."""
import json
import subprocess
import sys
from pathlib import Path
site=Path(sys.argv[1]).resolve()
expected={
"index.html":"64ade7e750222278801b31de2b64bcede855bbd9",
"app.js":"78cfbc856c410ce0014ab603af705b40ae73ae75",
"sw.js":"4618786c3211e82385ea6e2ec181bc8b486c3ad6",
"manifest.webmanifest":"a9d5dec79742d94eb62193c2c7e4abe4ab3df23c",
"home.js":"4c9e0c2dbb463e6fba0a512df2a780faf7dfbee7",
"personal_profile.json":"5b21b52962b8ff2ebc48e5a394ef3cd308d50b4c",
"personal_adapter.js":"37c1888938e8484ad43256efc60fe6d13549217f",
"med_guard.mjs":"9435ec752a887f0e6e5b696be6eaefc7d6999704"
}
assert site.is_dir(),"No static site"
for name,sha in expected.items():
    file=site/name
    assert file.is_file(),f"Missing {name}"
    blob=subprocess.check_output(["git","hash-object",str(file)],text=True).strip()
    assert blob==sha,f"Refuse unexpected bytes for {name}: {blob} != {sha}"
    print("PINNED PASS",name,blob,flush=True)
html=(site/"index.html").read_text(encoding="utf8")
app=(site/"app.js").read_text(encoding="utf8")
sw=(site/"sw.js").read_text(encoding="utf8")
profile=json.loads((site/"personal_profile.json").read_text(encoding="utf8"))
manifest=json.loads((site/"manifest.webmanifest").read_text(encoding="utf8"))
assert "const DB_VERSION=1" in app
assert "const BACKUP_VERSION=3" in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert "serviceWorker.register" in app
assert "default-src 'self'" in html and "unsafe-inline" not in html
assert "noindex,nofollow,noarchive" in html
assert "personal_adapter.js" in html and "personal_profile.json" in sw
assert "cache-cpreal01-" in sw
assert profile["schema"]=="PAE04_PERSONAL_QA_PROFILE_V1"
assert profile["constraints"]["seed_intakes"] is False and profile["constraints"]["seed_pressures"] is False
assert len(profile["medicines"])==10 and len(profile["reference_catalog"])==10
assert manifest["id"]=="./" and manifest["scope"]=="./" and manifest["display"]=="standalone"
assert not any(x.is_symlink() for x in site.rglob("*"))
assert (site/".nojekyll").exists()
assert all((site/path).is_file() for path in ["styles.css","home.css","med_guard.css","med_matcher.mjs","icons/icon-192.png","icons/icon-512.png","icons/apple-touch-icon.png"])
assert not any(x.suffix.lower() in (".sqlite",".db",".bak",".zip",".pem",".key") for x in site.rglob("*"))
size=sum(x.stat().st_size for x in site.rglob("*") if x.is_file())
assert size<2_000_000
print("RESULT=PASS PERSONAL_RC1_SITE_PINS=8/8 SAFE_FILE_BYTES="+str(size),flush=True)

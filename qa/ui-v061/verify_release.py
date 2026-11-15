#!/usr/bin/env python3
"""PAE-04 v0.6.1 personal Pages: immutable release pin for ALL static assets.
Only reads the checked-out repository, never opens or alters user IndexedDB.
Source: verified merge commit d1861efc5831becab1163c956d940e390488549f.
"""
import json
import subprocess
import sys
from pathlib import Path

site=Path(sys.argv[1]).resolve()
EXPECTED={
  ".nojekyll": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
  "app.js": "efebc05f9f6c1071adc4d44db4202656df5c9625",
  "CP_MED05_BUILD.json": "73cae13ae3002afd9a139805e7152acfc1ad4762",
  "CP_REAL01_BUILD.json": "b7010ad22f5503f1e63148514f628765e6edd248",
  "CP_UI01_BUILD.json": "b92bd7c5e2720a663cf502ee2abfa9650a7e6dfa",
  "home.css": "fc2446e40f6a5cbbf2d82052143b406c28b3eee8",
  "home.js": "cf6be2e7ab7078b74dcff8a38f7ec7a1b0ffe3b9",
  "icons/apple-touch-icon.png": "4cf9879b433979d1508c8ffdbb312e29123ef549",
  "icons/icon-192.png": "c07d28a59f0d773c2e18af62b261b50389f60a94",
  "icons/icon-512.png": "09673205f1b64d689d8899c1096031ba351f34cc",
  "icons/icon.svg": "05b76763ede5f0d88e2b855f3d90ed72ddf64842",
  "index.html": "9eb534accb7fafbd0821f23204bf5bc5f522313b",
  "manifest.webmanifest": "9d0a1027ecc1f87c806a347da2f4abd012288e6c",
  "med_guard.css": "1ebdff67c6ae4088759bc1c9059ee7f2f5fd6b2e",
  "med_guard.mjs": "9435ec752a887f0e6e5b696be6eaefc7d6999704",
  "med_matcher.mjs": "cf08822f5e71c8fb505fbec066e5eec9145215c6",
  "offline_status.js": "2b2441d09efeaabc1d0594f77bdc84e0efb30e9f",
  "personal_adapter.js": "277b8bc2435d4bd9f4b30c89db15570ca2f2656f",
  "personal_profile.json": "5b21b52962b8ff2ebc48e5a394ef3cd308d50b4c",
  "robots.txt": "1f53798bb4fe33c86020be7f10c44f29486fd190",
  "styles.css": "71c12c82adc41aefe039ddb43ec8724d759d82e9",
  "sw.js": "c76b0ce3288abf5b3753243f4ed8ab9833acc005"
}
assert site.is_dir(), "Missing release site"
actual={str(p.relative_to(site)) for p in site.rglob("*") if p.is_file()}
assert actual==set(EXPECTED), f"Unexpected/missing site files: extra={sorted(actual-set(EXPECTED))}, absent={sorted(set(EXPECTED)-actual)}"
assert not any(p.is_symlink() for p in site.rglob("*")), "Symlink in site"
for name,expected_sha in sorted(EXPECTED.items()):
    path=site/name
    actual_sha=subprocess.check_output(["git","hash-object",str(path)],text=True).strip()
    assert actual_sha==expected_sha, f"Release pin mismatch {name}: {actual_sha} != {expected_sha}"
    print("PINNED PASS",name,actual_sha,flush=True)
html=(site/"index.html").read_text(encoding="utf-8")
app=(site/"app.js").read_text(encoding="utf-8")
sw=(site/"sw.js").read_text(encoding="utf-8")
offline=(site/"offline_status.js").read_text(encoding="utf-8")
profile=json.loads((site/"personal_profile.json").read_text(encoding="utf-8"))
manifest=json.loads((site/"manifest.webmanifest").read_text(encoding="utf-8"))
assert "PERSONAL BETA · v0.6.1" in html and 'src="./offline_status.js"' in html
assert "const DB_VERSION=1" in app
assert "const BACKUP_VERSION=3" in app
assert "const BACKUP_FORMAT='pae04.healthtracker.synthetic-backup'" in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert 'serviceWorker.register' in app
assert "personal-v061-offline1-20261115" in sw and "personal-v061-offline1-20261115" in offline
assert "return offlineUnavailable();" in sw
assert "default-src 'self'" in html and "unsafe-inline" not in html
assert "noindex,nofollow,noarchive" in html
assert profile["schema"]=="PAE04_PERSONAL_QA_PROFILE_V1"
assert profile["constraints"]["seed_intakes"] is False and profile["constraints"]["seed_pressures"] is False
assert len(profile["medicines"])==10 and len(profile["reference_catalog"])==10
assert manifest["id"]=="./" and manifest["scope"]=="./" and manifest["display"]=="standalone"
assert manifest["start_url"]=="./index.html"
assert not any(p.suffix.lower() in (".db",".sqlite",".bak",".zip",".pem",".key") for p in site.rglob("*"))
size=sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
assert size<2_000_000
print("RESULT=PASS PERSONAL_V061_EXACT_ASSET_PINS=22/22 APP_BYTES="+str(size),flush=True)

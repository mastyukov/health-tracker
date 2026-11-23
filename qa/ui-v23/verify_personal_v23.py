#!/usr/bin/env python3
"""PAE-04 personal iPhone v2.3 - SHA pin gate. No personal data extraction."""
from pathlib import Path
from hashlib import sha1
import json,sys
site=Path(sys.argv[1] if len(sys.argv)>1 else 'site').resolve()
PINNED={
  ".nojekyll": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
  "CP_MED05_BUILD.json": "73cae13ae3002afd9a139805e7152acfc1ad4762",
  "CP_REAL01_BUILD.json": "b7010ad22f5503f1e63148514f628765e6edd248",
  "CP_UI01_BUILD.json": "b92bd7c5e2720a663cf502ee2abfa9650a7e6dfa",
  "app.js": "32a093dffddf254278c46a2a56f35128f45aeb6f",
  "home.css": "e49331b5da9c1632f1d4b384ac05bc57506f50f9",
  "home.js": "de4c28b60f6e90a54696b6232c9eb6c4147cea31",
  "icons/apple-touch-icon.png": "4cf9879b433979d1508c8ffdbb312e29123ef549",
  "icons/icon-192.png": "c07d28a59f0d773c2e18af62b261b50389f60a94",
  "icons/icon-512.png": "09673205f1b64d689d8899c1096031ba351f34cc",
  "icons/icon.svg": "05b76763ede5f0d88e2b855f3d90ed72ddf64842",
  "index.html": "08b241a615da56297d4982a7ac5a2c36f0c8c0ca",
  "manifest.webmanifest": "e74f10f038d5a4e1c04936c1246435de58282d35",
  "med_guard.css": "1ebdff67c6ae4088759bc1c9059ee7f2f5fd6b2e",
  "med_guard.mjs": "9435ec752a887f0e6e5b696be6eaefc7d6999704",
  "med_matcher.mjs": "cf08822f5e71c8fb505fbec066e5eec9145215c6",
  "offline_status.js": "862ae34631464e86443139675557485b9dc2398e",
  "personal_adapter.js": "277b8bc2435d4bd9f4b30c89db15570ca2f2656f",
  "personal_profile.json": "5b21b52962b8ff2ebc48e5a394ef3cd308d50b4c",
  "robots.txt": "1f53798bb4fe33c86020be7f10c44f29486fd190",
  "styles.css": "33fc30b7c85f7cdbf60f43a206fb1f47a9c72fb4",
  "sw.js": "21f4cf493b0efaba84e8c74244047ffee445a8e7"
}
assert site.is_dir(),'SITE_MISSING'
assert not any(f.is_symlink() for f in site.rglob('*')),'SYMLINK_IN_SITE'
actual={f.relative_to(site).as_posix() for f in site.rglob('*') if f.is_file()}
assert actual==set(PINNED),'ALLOWLIST_22_MISMATCH'
for name,expected in sorted(PINNED.items()):
 b=(site/name).read_bytes() # checks byte identity; does not parse profile
 actual_sha=sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 assert actual_sha==expected,'BLOB_PIN_FAIL: '+name
html=(site/'index.html').read_text(encoding='utf8')
app=(site/'app.js').read_text(encoding='utf8')
sw=(site/'sw.js').read_text(encoding='utf8')
offline=(site/'offline_status.js').read_text(encoding='utf8')
manifest=json.loads((site/'manifest.webmanifest').read_text(encoding='utf8'))
assert 'Health Tracker · Compact v7.1' in html and 'Только вымышленные данные' not in html,'UI_NOT_PERSONAL'
assert 'src="./personal_adapter.js"' in html,'PERSONAL_ADAPTER_MISSING'
assert 'src="./offline_status.js"' in html,'OFFLINE_MODULE_MISSING'
assert 'id="export-button"' in html and 'id="import-button"' in html,'BACKUP_CONTROLS_MISSING'
assert "default-src 'self'" in html and 'unsafe-inline' not in html,'CSP_CHANGED'
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app,'PERSONAL_DB_NAME_CHANGED'
assert 'const DB_VERSION=1' in app and 'const BACKUP_VERSION=3' in app,'STORAGE_VERSION_CHANGED'
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app,'STORE_LIST_CHANGED'
assert "const BACKUP_FORMAT='pae04.healthtracker.synthetic-backup'" in app,'BACKUP_FORMAT_CHANGED'
assert 'navigator.onLine' not in app and 'Локальная база доступна' in app,'LOCAL_DB_BADGE_REGRESSION'
assert 'TEST: импорт резервных копий отключён' not in app,'IMPORT_TEST_DISABLE'
assert 'indexedDB.deleteDatabase' not in app,'UNAPPROVED_DB_DELETE'
assert 'personal-home-v71-home32-cachefix-20261124' in sw and 'personal-home-v71-home32-cachefix-20261124' in offline,'CACHE_VERSION_MISMATCH'
assert "'./personal_adapter.js'" in sw and "'./personal_profile.json'" in sw,'PERSONAL_ASSETS_NOT_PRECACHED'
assert 'indexedDB.open' not in sw and 'indexedDB.open' not in offline,'SW_TOUCHES_USER_DATA'
assert manifest['id']=='./' and manifest['scope']=='./' and manifest['start_url']=='./index.html' and manifest['display']=='standalone','PWA_ID_CHANGED'
assert 'id="v232-pressure-highlights"' in html,'PRESSURE_HIGHLIGHTS_MISSING'
assert 'id="v232-build-version"' in html,'VISIBLE_VERSION_MISSING'
assert 'setupMedicationSections();' in (site/'home.js').read_text(encoding='utf8'),'MEDICATION_TABS_MISSING'
assert 'v232PressureVisible+=30' in app,'PRESSURE_PAGINATION_MISSING'
assert 'prnReason.maxLength=160' in app,'PRN_REASON_MISSING'
print('PASS_STATIC_ONLY: EXACT 22/22 GIT BLOBS, HOME-V7 PILOT; SAFARI RUNTIME NOT VERIFIED')

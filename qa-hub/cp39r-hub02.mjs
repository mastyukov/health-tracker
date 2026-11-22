'use strict';
/* PAE-04 CP39R-HUB-02: Codespaces-only, synthetic, single-run OLD -> NEW -> OFFLINE -> OLD.
   No personal profile or adapter downloads, no GitHub writes, no automatic retries.
   Execute only after owner authorization to use the identified Codespace. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { join, resolve, sep, extname } from 'node:path';
import { chromium } from 'playwright';

const HUB=join(process.cwd(),'qa-hub');
const RUN=join(HUB,'.run','cp39r-hub02-one-shot-20261123');
const OLD='068bfc4f4bd39736a59c12bd37c56b647bd885cb';
const NEW='c3da0816f48a81626ef25fb94dd653deab8533d3';
const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';
const STORE_NAMES=['pressures','medications','intakes','intakeEvents'];
const CACHE_PREFIX='pae04-ht-stable-candidate-synthetic-schema1-cache-';
const OLD_CACHE=CACHE_PREFIX+'personal-home-v71-cachefix-20261122';
const NEW_CACHE=CACHE_PREFIX+'personal-cp39r-r11b-safe-20261122';
const ORIGIN='https://raw.githubusercontent.com/mastyukov/health-tracker/';
const PIN_NEW=Object.freeze({
 '.nojekyll':['e69de29bb2d1d6434b8b29ae775ad8c2e48c5391',0],
 'CP_MED05_BUILD.json':['73cae13ae3002afd9a139805e7152acfc1ad4762',324],
 'CP_REAL01_BUILD.json':['b7010ad22f5503f1e63148514f628765e6edd248',310],
 'CP_UI01_BUILD.json':['b92bd7c5e2720a663cf502ee2abfa9650a7e6dfa',306],
 'app.js':['6f76cd6b464216fc1402857c33b1b5a4614b3838',86637],
 'home.css':['e49331b5da9c1632f1d4b384ac05bc57506f50f9',13713],
 'home.js':['de4c28b60f6e90a54696b6232c9eb6c4147cea31',22412],
 'icons/apple-touch-icon.png':['4cf9879b433979d1508c8ffdbb312e29123ef549',7145],
 'icons/icon-192.png':['c07d28a59f0d773c2e18af62b26150389f60a94',7697],
 'icons/icon-512.png':['09673205f1b64d689d8899c1096031ba351f34cc',21771],
 'icons/icon.svg':['05b76763ede5f0d88e2b855f3d90ed72ddf64842',449],
 'index.html':['08b241a615da56297d4982a7ac5a2c36f0c8c0ca',26045],
 'manifest.webmanifest':['e74f10f038d5a4e1c04936c1246435de58282d35',740],
 'med_guard.css':['1ebdff67c6ae4088759bc1c9059ee7f2f5fd6b2e',766],
 'med_guard.mjs':['9435ec752a887f0e6e5b696be6eaefc7d6999704',9438],
 'med_matcher.mjs':['cf08822f5e71c8fb505fbec066e5eec9145215c6',4044],
 'offline_status.js':['0d0665221303866f404ecd9e0dc0f05af12b482d',2801],
 'robots.txt':['1f53798bb4fe33c86020be7f10c44f29486fd190',26],
 'styles.css':['33fc30b7c85f7cdbf60f43a206fb1f47a9c72fb4',36188],
 'sw.js':['14ed6da6242b59bc0ba71d589b48ded3aa1eb5ab',3888]
});
const PIN_OLD=Object.freeze({
 'app.js':['3725145e5c48a23027723cc62de9572c0be7feec',84972],
 'sw.js':['b1c1ce828ff7c552088b4e395f3fea7e05e9c7b0',3890],
 'offline_status.js':['d287ba87f900dd43c9b83ab463d21fa9aca13d7e',2803]
});
const FIXTURE=Object.freeze({
 privacy:'HUB02_SYNTHETIC_ONLY',purpose:'TEST',medicines:[],
 constraints:{seed_pressures:false,seed_intakes:false}
});
const STUB='/* PAE04 HUB02 synthetic-only adapter; original adapter NEVER downloaded. */\n';
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
 '.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8',
 '.webmanifest':'application/manifest+json','.css':'text/css; charset=utf-8',
 '.svg':'image/svg+xml','.png':'image/png','.txt':'text/plain; charset=utf-8'};
const report={schema:'PAE04_CP39R_HUB02_V1',sourceOld:OLD,sourceNew:NEW,
 syntheticOnly:true,personalFilesRead:false,actualImport:false,actualRestore:false,
 codespacesTest:true,status:'NOT_RUN',phase:'PREFLIGHT',checks:[],startedAt:new Date().toISOString()};
let browser,ctx,server,page,serveMode='old',serverHits=0;
function gate(ok,name){if(!ok)throw Error('STOP_FIRST_'+name);report.checks.push(name);console.log('PASS '+name)}
function shaBlob(bytes){return createHash('sha1').update(Buffer.from('blob '+bytes.length+'\0')).update(bytes).digest('hex')}
function sha256(bytes){return createHash('sha256').update(bytes).digest('hex')}
function pause(ms){return new Promise(ok=>setTimeout(ok,ms))}
async function download(ref,file,pin){
 const url=ORIGIN+ref+'/site/'+file.split('/').map(encodeURIComponent).join('/');
 const response=await fetch(url,{signal:AbortSignal.timeout(25000),redirect:'error'});
 if(!response.ok)throw Error('PINNED_SOURCE_HTTP_'+response.status);
 const bytes=Buffer.from(await response.arrayBuffer());
 gate(bytes.length===pin[1]&&shaBlob(bytes)===pin[0],'PIN_'+ref.slice(0,8)+'_'+file.replaceAll('/','_'));
 return bytes;
}
async function stage(){
 report.phase='PINNED_SOURCE_PREP';
 assert.equal(Object.keys(PIN_NEW).length,20);
 for(const disallowed of ['personal_profile.json','personal_adapter.js']){
   gate(!Object.hasOwn(PIN_NEW,disallowed)&&!Object.hasOwn(PIN_OLD,disallowed),'PERSONAL_NOT_IN_REMOTE_ALLOWLIST_'+disallowed);
 }
 await mkdir(join(HUB,'.run'),{recursive:true});
 try{await stat(RUN);throw Error('STOP_FIRST_EXISTING_RUN_FOLDER')}catch(e){if(e.code!=='ENOENT')throw e}
 await mkdir(RUN,{recursive:false,mode:0o700});
 await mkdir(join(RUN,'site-old'),{mode:0o700});
 await mkdir(join(RUN,'site-new'),{mode:0o700});
 const pinned={};
 for(const [file,pin] of Object.entries(PIN_NEW)){
   const bytes=await download(NEW,file,pin);
   pinned[file]=bytes;
   const dest=join(RUN,'site-new',file);
   await mkdir(join(dest,'..'),{recursive:true});
   await writeFile(dest,bytes,{flag:'wx',mode:0o600});
 }
 for(const [file,newBytes] of Object.entries(pinned)){
   const bytes=Object.hasOwn(PIN_OLD,file)?await download(OLD,file,PIN_OLD[file]):newBytes;
   const dest=join(RUN,'site-old',file);
   await mkdir(join(dest,'..'),{recursive:true});
   await writeFile(dest,bytes,{flag:'wx',mode:0o600});
 }
 for(const kind of ['old','new']){
   await writeFile(join(RUN,'site-'+kind,'personal_profile.json'),JSON.stringify(FIXTURE),{flag:'wx',mode:0o600});
   await writeFile(join(RUN,'site-'+kind,'personal_adapter.js'),STUB,{flag:'wx',mode:0o600});
 }
 gate(sha256(await readFile(join(RUN,'site-old','app.js')))!==sha256(await readFile(join(RUN,'site-new','app.js'))),'OLD_NEW_APP_DIFFER');
 gate((await readFile(join(RUN,'site-old','sw.js'),'utf8')).includes(OLD_CACHE),'OLD_SW_PIN');
 gate((await readFile(join(RUN,'site-new','sw.js'),'utf8')).includes(NEW_CACHE),'NEW_SW_PIN');
 report.assetPinCount=Object.keys(PIN_NEW).length+Object.keys(PIN_OLD).length;
 report.oldAppSha256=sha256(await readFile(join(RUN,'site-old','app.js')));
 report.newAppSha256=sha256(await readFile(join(RUN,'site-new','app.js')));
}
async function serve(){
 server=createServer(async(req,res)=>{
  try{
   if(req.method!=='GET'){res.writeHead(405);res.end();return}
   const url=new URL(req.url,'http://127.0.0.1/');
   const rel=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
   if(!rel||rel.includes('..')||rel.startsWith('/')||rel.includes('\\')){res.writeHead(403);res.end();return}
   if(!Object.hasOwn(PIN_NEW,rel)&&rel!=='personal_profile.json'&&rel!=='personal_adapter.js'){
    res.writeHead(404);res.end();return;
   }
   const root=join(RUN,'site-'+serveMode);
   const full=resolve(root,rel);
   if(!full.startsWith(root+sep)){res.writeHead(403);res.end();return}
   const bytes=await readFile(full);
   if(rel==='app.js')serverHits++;
   res.writeHead(200,{'Content-Type':MIME[extname(rel)]||'application/octet-stream',
     'Content-Length':bytes.length,'Cache-Control':'no-store'});
   res.end(bytes);
  }catch{res.writeHead(404);res.end()}
 });
 await new Promise((ok,bad)=>{server.once('error',bad);server.listen(0,'127.0.0.1',ok)});
 return 'http://127.0.0.1:'+server.address().port+'/index.html';
}
async function pageReady(p){
 await p.waitForFunction(()=>document.querySelector('#connection-status')?.textContent?.includes('Локальная база доступна')&&typeof db!=='undefined'&&db!==null&&typeof readBackupSnapshot==='function',null,{timeout:16000});
}
async function fingerprint(p){
 return p.evaluate(async()=>{
  const text=await (await fetch('./app.js',{cache:'no-store'})).text();
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  const sha=Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');
  const registration=await navigator.serviceWorker.getRegistration();
  return {sha256:sha,guardLoaded:typeof assertKnownBackupFields==='function',
   controlled:!!navigator.serviceWorker.controller,active:registration?.active?.state||null,
   waiting:!!registration?.waiting,cacheNames:(await caches.keys()).filter(x=>x.startsWith('pae04-ht-stable-candidate-synthetic-schema1-cache-'))};
 });
}
async function snapshot(p){return p.evaluate(async()=>JSON.stringify(await readBackupSnapshot()))}
async function seed(p){
 await p.evaluate(async()=>{
  const r=indexedDB.open('PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',1);
  const c=await new Promise((ok,bad)=>{r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)});
  const t=c.transaction(['pressures','medications','intakes','intakeEvents'],'readwrite');
  t.objectStore('pressures').put({id:'h-p',systolic:120,diastolic:80,pulse:70,dateTime:'2026-03-01T10:00',arm:'right',note:'SYNTHETIC'});
  t.objectStore('medications').put({id:'h-m',name:'QA-HUB synthetic medicine',kind:'regular',dose:'TEST',dailyIntakes:2});
  t.objectStore('intakes').put({id:'h-i',medId:'h-m',date:'2026-03-01',markedAt:'2026-03-01T10:00',takenAtLocal:'2026-03-01T10:00',dailySlot:1,status:'active'});
  t.objectStore('intakeEvents').put({id:'h-e',intakeId:'h-i',medId:'h-m',action:'taken',at:'2026-03-01T10:00'});
  await new Promise((ok,bad)=>{t.oncomplete=ok;t.onerror=()=>bad(t.error);t.onabort=()=>bad(t.error)});
  c.close();
 });
}
async function workerTransition(ctx,token,timeout=16000){
 const deadline=Date.now()+timeout;
 while(Date.now()<deadline){
  const states=await Promise.all(ctx.serviceWorkers().map(async w=>{
   try{return await w.evaluate(()=>({
    cache:typeof CACHE==='string'?CACHE:'',
    active:self.registration.active?.state||'',
    waiting:!!self.registration.waiting
   }))}catch{return null}
  }));
  if(states.some(x=>x?.cache?.endsWith(token)&&x.active==='activated'&&!x.waiting))return;
  await pause(250);
 }
 throw Error('STOP_FIRST_SW_ACTIVATION_TIMEOUT');
}
async function updateAndReopen(url,next,token){
 report.phase='SW_TRANSITION_'+next.toUpperCase();
 serveMode=next;
 await page.evaluate(async()=>{
  const reg=await navigator.serviceWorker.getRegistration();
  if(!reg)throw Error('SW_REGISTRATION_MISSING');
  await reg.update();
 });
 await page.close();
 page=null;
 await workerTransition(ctx,token);
 page=await ctx.newPage();
 await page.goto(url,{waitUntil:'load',timeout:20000});
 await pageReady(page);
}
async function run(){
 report.phase='ISOLATED_BROWSER';
 const url=await serve();
 browser=await chromium.launch({headless:true,args:['--disable-sync','--disable-background-networking','--no-default-browser-check','--no-first-run']});
 ctx=await browser.newContext({serviceWorkers:'allow',viewport:{width:390,height:844}});
 await ctx.route('**/*',route=>{
  const u=new URL(route.request().url());
  if(u.protocol==='http:'&&u.hostname==='127.0.0.1')return route.continue();
  return route.abort('blockedbyclient');
 });
 page=await ctx.newPage();page.setDefaultTimeout(16000);
 await page.goto(url,{waitUntil:'load',timeout:20000});await pageReady(page);
 const initial=await fingerprint(page);
 gate(initial.sha256===report.oldAppSha256&&!initial.guardLoaded,'OLD_APP_SHA');
 await page.evaluate(async()=>{await navigator.serviceWorker.ready});
 await page.waitForFunction(()=>!!navigator.serviceWorker.controller,null,{timeout:16000});
 await page.reload({waitUntil:'load',timeout:20000});await pageReady(page);
 await seed(page);
 await page.reload({waitUntil:'load',timeout:20000});await pageReady(page);
 const before=await snapshot(page),data=JSON.parse(before);
 gate(Object.keys(data).length===4&&STORE_NAMES.every(k=>data[k]?.length===1)&&data.pressures[0].arm==='right','FOUR_SYNTHETIC_STORES_SEEDED');
 await updateAndReopen(url,'new','personal-cp39r-r11b-safe-20261122');
 const upgraded=await fingerprint(page);
 report.afterUpgrade={appSha256:upgraded.sha256,controlled:upgraded.controlled,active:upgraded.active,waiting:upgraded.waiting};
 gate(upgraded.controlled&&upgraded.sha256===report.newAppSha256&&upgraded.guardLoaded,'NEW_APP_CONTROLLER_ACTIVATED');
 gate((await snapshot(page))===before,'FOUR_STORES_PRESERVED_AFTER_UPGRADE');
 report.phase='OFFLINE';
 await ctx.setOffline(true);
 await page.reload({waitUntil:'domcontentloaded',timeout:18000});
 await pageReady(page);
 gate((await snapshot(page))===before,'OFFLINE_FOUR_STORES_PRESERVED');
 await ctx.setOffline(false);
 await updateAndReopen(url,'old','personal-home-v71-cachefix-20261122');
 const restored=await fingerprint(page);
 report.afterRollback={appSha256:restored.sha256,controlled:restored.controlled,active:restored.active,waiting:restored.waiting};
 gate(restored.controlled&&restored.sha256===report.oldAppSha256&&!restored.guardLoaded,'OLD_APP_CONTROLLER_RESTORED');
 gate((await snapshot(page))===before,'ROLLBACK_FOUR_STORES_PRESERVED');
 report.phase='DONE';
}
async function main(){
 let created=false;
 try{
  await stage();created=true;
  await run();
  report.status='PASS_SCOPED';
 }catch(e){
  report.status='FAIL_STOP_FIRST';
  report.errorCode=String(e?.message||e).slice(0,180);
 }finally{
  try{if(page)await page.close()}catch{}
  try{if(ctx)await ctx.close()}catch{}
  try{if(browser)await browser.close()}catch{}
  try{if(server)await new Promise(ok=>server.close(ok))}catch{}
  report.finishedAt=new Date().toISOString();
  report.serverAppRequests=serverHits;
  if(created){
   try{
    const out=join(RUN,'report.json');
    await writeFile(out,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
    const saved=JSON.parse(await readFile(out,'utf8'));
    assert.equal(saved.status,report.status);
    assert.deepEqual(saved.checks,report.checks);
    console.log(JSON.stringify({checkpoint:'CP39R-HUB02',status:report.status,checks:report.checks,
      phase:report.phase,code:report.errorCode||null,report:'qa-hub/.run/cp39r-hub02-one-shot-20261123/report.json',
      readback:'PASS',syntheticOnly:true,githubWrites:0},null,2));
   }catch{console.error('BLOCKED_REPORT_CREATE_OR_READBACK');process.exitCode=1;return}
  }else console.error('BLOCKED_PREP '+(report.errorCode||'UNKNOWN'));
  if(report.status!=='PASS_SCOPED')process.exitCode=1;
 }
}
main().catch(()=>{console.error('BLOCKED_UNHANDLED');process.exitCode=1});

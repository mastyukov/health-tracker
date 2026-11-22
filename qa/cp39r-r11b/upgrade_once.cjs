'use strict';
const fs=require('fs'),path=require('path'),os=require('os'),cp=require('child_process'),http=require('http');
const {chromium}=require('playwright-core');
const ROOT=process.cwd(),SITE=path.join(ROOT,'site'),BASE='068bfc4f4bd39736a59c12bd37c56b647bd885cb';
const DB='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',NEW='personal-cp39r-r11b-safe-20261122';
const PROFILE=path.join(process.env.RUNNER_TEMP||os.tmpdir(),'pae04-r11b-'+process.env.GITHUB_RUN_ID);
let server,ctx,page,mode='before',phase='PRECHECK',passes=0,hits=0;const start=Date.now();
function git(args){const r=cp.spawnSync('git',args,{encoding:'utf8',timeout:8000});if(r.status!==0)throw Error('GIT_ERROR '+r.stderr.slice(0,100));return r.stdout.trim()}
function gate(ok,name,d={}){if(!ok)throw Error('STOP_FIRST_'+name);passes++;console.log('PASS '+name+' '+JSON.stringify(d).slice(0,150))}
async function ready(){await page.waitForFunction(()=>document.querySelector('#connection-status')?.textContent?.includes('Локальная база доступна')&&typeof db!=='undefined'&&db!==null&&typeof readBackupSnapshot==='function',null,{timeout:15000})}
async function snap(){return page.evaluate(async()=>JSON.stringify(await readBackupSnapshot()))}
async function load(url){await page.goto(url,{waitUntil:'load',timeout:20000});await ready()}
async function run(){
 phase='EXACT_SOURCE';
 gate(process.env.GITHUB_REPOSITORY==='mastyukov/health-tracker'&&process.env.GITHUB_HEAD_REF==='sandbox/pae04-cp39r-r11d-split-gates-once-20261123'&&process.env.GITHUB_EVENT_NAME==='pull_request'&&process.env.GITHUB_RUN_ATTEMPT==='1','ONE_SHOT_PIN');
 gate(git(['rev-parse','HEAD^'])==='bcaf8ecd7207d05677798a54aa29698058b099e7'&&git(['rev-parse','HEAD~2'])==='e7ccf7409bf9bc41c97c8bf78a447f5e1a4bf389'&&git(['rev-parse','HEAD~3'])===BASE,'PARENT_SHA');
 for(const f of ['site/personal_profile.json','site/personal_adapter.js'])gate(git(['ls-tree','HEAD^','--',f])===git(['ls-tree','HEAD','--',f]),'PERSONAL_BLOB_UNCHANGED_'+path.basename(f));
 const app=fs.readFileSync(path.join(SITE,'app.js'),'utf8'),sw=fs.readFileSync(path.join(SITE,'sw.js'),'utf8'),off=fs.readFileSync(path.join(SITE,'offline_status.js'),'utf8');
 gate(app.includes("const DB_NAME='"+DB+"'")&&app.includes("const BACKUP_VERSION=3;")&&app.includes("const STORE_NAMES=['pressures','medications','intakes','intakeEvents'];")&&!/\bindexedDB\.deleteDatabase\s*\(/.test(app),'DATABASE_STORES_UNCHANGED');
 gate(app.includes('function assertKnownBackupFields(envelope)')&&app.split('assertKnownBackupFields(parsed);').length===3,'STRICT_GUARD');
 gate(sw.includes(NEW)&&off.includes(NEW),'CACHE_PAIR');
 const old={};for(const f of ['app.js','sw.js','offline_status.js'])old[f]=git(['show','HEAD~3:site/'+f]);
 gate(old['app.js'].includes("const DB_NAME='"+DB+"'")&&!old['app.js'].includes('function assertKnownBackupFields(envelope)'),'OLD_BUILD_PIN');
 const fakeProfile=JSON.stringify({privacy:'R11B_SYNTHETIC_ONLY',purpose:'TEST',medicines:[],constraints:{seed_pressures:false,seed_intakes:false}});
 phase='LOCAL_ONLY_SERVER';
 server=http.createServer((req,res)=>{
   let url;try{url=new URL(req.url,'http://127.0.0.1')}catch{res.writeHead(400);res.end();return}
   const rel=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
   if(req.method!=='GET'||rel.includes('..')||rel.startsWith('/')||rel.includes('\\')){res.writeHead(404);res.end();return}
   if(rel==='personal_profile.json'){res.writeHead(200,{'Content-Type':'application/json'});res.end(fakeProfile);return}
   if(rel==='personal_adapter.js'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end('/* R11B fictional synthetic adapter; real personal adapter remains unread. */');return}
   const f=path.resolve(SITE,rel);if(!f.startsWith(SITE+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile()){res.writeHead(404);res.end();return}
   const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webmanifest':'application/manifest+json','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.ico':'image/x-icon'};
   const b=mode==='before'&&Object.hasOwn(old,rel)?old[rel]:fs.readFileSync(f);hits++;
   res.writeHead(200,{'Content-Type':mime[path.extname(rel)]||'application/octet-stream','Cache-Control':'no-store'});res.end(b);
 });
 await new Promise((ok,bad)=>{server.once('error',bad);server.listen(0,'127.0.0.1',ok)});
 const url='http://127.0.0.1:'+server.address().port+'/index.html';
 phase='CHROMIUM';
 const chrome=cp.spawnSync('which',['google-chrome'],{encoding:'utf8'}).stdout.trim();gate(chrome.startsWith('/')&&fs.existsSync(chrome),'CHROME_INSTALLED');
 if(fs.existsSync(PROFILE))throw Error('PROFILE_ALREADY_EXISTS');
 ctx=await chromium.launchPersistentContext(PROFILE,{executablePath:chrome,headless:true,serviceWorkers:'allow',viewport:{width:390,height:844},args:['--disable-sync','--disable-background-networking','--disable-component-update','--no-default-browser-check','--no-first-run','--no-proxy-server']});
 await ctx.route('**/*',route=>{const u=new URL(route.request().url());if(u.protocol==='http:'&&u.hostname==='127.0.0.1')return route.continue();return route.abort('blockedbyclient')});
 page=await ctx.newPage();page.setDefaultTimeout(13000);
 phase='BASELINE';await load(url);
 gate(await page.evaluate(()=>typeof assertKnownBackupFields==='undefined'&&DB_NAME==='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'),'BASELINE_READY');
 phase='SYNTHETIC_INDEXEDDB_SEED';
 await page.evaluate(async()=>{
  const r=indexedDB.open('PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',1);
  const c=await new Promise((ok,bad)=>{r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)});
  const t=c.transaction(['pressures','medications','intakes','intakeEvents'],'readwrite');
  t.objectStore('pressures').put({id:'s-p',systolic:120,diastolic:80,pulse:70,dateTime:'2026-03-01T10:00',arm:'right',note:'SYNTHETIC',createdAt:'2026-03-01T10:00'});
  t.objectStore('medications').put({id:'s-m',name:'R11B Тестовый препарат',kind:'regular',dose:'TEST',dailyIntakes:2,createdAt:'2026-03-01T10:00'});
  t.objectStore('intakes').put({id:'s-i',medId:'s-m',date:'2026-03-01',markedAt:'2026-03-01T10:00',takenAtLocal:'2026-03-01T10:00',dailySlot:1,status:'active'});
  t.objectStore('intakeEvents').put({id:'s-e',intakeId:'s-i',medId:'s-m',action:'taken',at:'2026-03-01T10:00'});
  await new Promise((ok,bad)=>{t.oncomplete=ok;t.onerror=()=>bad(t.error);t.onabort=()=>bad(t.error)});c.close();
 });
 await page.reload({waitUntil:'load'});await ready();
 const before=await snap(),four=JSON.parse(before);
 gate(Object.keys(four).length===4&&Object.values(four).every(x=>x.length===1)&&four.pressures[0].arm==='right','SYNTHETIC_FOUR_STORES',{counts:Object.fromEntries(Object.entries(four).map(([k,v])=>[k,v.length]))});
 phase='UPGRADE';
 await page.waitForFunction(async()=>!!navigator.serviceWorker.controller,null,{timeout:15000});
 mode='after';
 await page.evaluate(async()=>{const r=await navigator.serviceWorker.getRegistration();if(!r)throw Error('SW_MISSING');await r.update()});
 await page.waitForFunction(async term=>(await caches.keys()).some(k=>k.includes(term)),NEW,{timeout:15000});
 await page.reload({waitUntil:'load',timeout:18000});await ready();
 const after=await snap(),guard=await page.evaluate(()=>typeof assertKnownBackupFields==='function');
 const countsBefore=Object.fromEntries(Object.entries(JSON.parse(before)).map(([key,rows])=>[key,rows.length]));
 const countsAfter=Object.fromEntries(Object.entries(JSON.parse(after)).map(([key,rows])=>[key,rows.length]));
 const swState=await page.evaluate(async()=>{const registration=await navigator.serviceWorker.getRegistration();return {controlled:!!navigator.serviceWorker.controller,active:registration?.active?.state==='activated',newCache:(await caches.keys()).some(key=>key.includes('personal-cp39r-r11b-safe-20261122'))}});
 console.log('R11D_UPGRADE_DIAGNOSTIC '+JSON.stringify({indexedDbExact:before===after,guardLoaded:guard,countsBefore,countsAfter,swState}));
 gate(before===after,'UPGRADE_INDEXEDDB_FOUR_STORES_PRESERVED',{countsBefore,countsAfter});
 gate(guard&&swState.controlled&&swState.active&&swState.newCache,'UPGRADE_NEW_CODE_LOADED',{guardLoaded:guard,swState});
 phase='BACKUP_V3_GUARD';
 const rejected=await page.evaluate(()=>{
  const good={format:'pae04.healthtracker.synthetic-backup',version:3,exportedAt:'2026-01-01',sha256:'fake',data:{pressures:[{id:'p',systolic:120,diastolic:80,pulse:70,dateTime:'2026-01-01',arm:'right'}],medications:[],intakes:[{id:'i',medId:'m',date:'2026-01-01'}],intakeEvents:[{id:'e',intakeId:'i',medId:'m',action:'taken',at:'2026-01-01'}]}};assertKnownBackupFields(good);let n=0;
  for(const key of ['envelope','pressures','intakes','intakeEvents']){const d=JSON.parse(JSON.stringify(good));if(key==='envelope')d.extra='bad';else d.data[key][0].extra='bad';try{assertKnownBackupFields(d)}catch(e){if(String(e).includes('Неизвестное поле'))n++}}return n;
 });gate(rejected===4,'EXTERNAL_V3_NEGATIVE_FIELDS',{rejected});
 phase='OFFLINE';
 await ctx.setOffline(true);await page.reload({waitUntil:'domcontentloaded',timeout:18000});await ready();
 gate(await snap()===before,'OFFLINE_FOUR_STORES_PRESERVED');
 phase='ROLLBACK';
 await ctx.setOffline(false);mode='before';
 await page.evaluate(async()=>{const r=await navigator.serviceWorker.getRegistration();if(!r)throw Error('SW_MISSING');await r.update()});
 await page.reload({waitUntil:'load',timeout:18000});await ready();
 const restored=await page.evaluate(()=>typeof assertKnownBackupFields==='undefined');
 gate(restored&&await snap()===before,'ROLLBACK_PRESERVED_FOUR_STORES',{originalCodeRestored:restored});
 phase='DONE';
}
(async()=>{let status='BLOCKED_EXECUTION',errors=[];try{await run();status='PASS_SYNTHETIC_UPGRADE_ROLLBACK_SCOPED'}catch(e){errors.push({phase,message:String(e.stack||e).slice(0,900)})}finally{
if(ctx)try{await ctx.close()}catch(e){errors.push({phase:'CLEANUP',message:String(e).slice(0,100)})}
if(server)try{server.closeAllConnections();await new Promise(ok=>server.close(ok))}catch(e){errors.push({phase:'SERVER_CLOSE',message:String(e).slice(0,100)})}
const report={checkpoint:'CP39R-R11D',status,phase,passed:passes,httpHits:hits,durationSeconds:+((Date.now()-start)/1000).toFixed(2),errors,syntheticOnly:true,personalFilesRead:false,actualImport:false,actualRestore:false,macUsed:false,releaseGo:false};console.log('PAE04_R11D_RESULT '+JSON.stringify(report));if(status!=='PASS_SYNTHETIC_UPGRADE_ROLLBACK_SCOPED')process.exitCode=1;}})();

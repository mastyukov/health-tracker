#!/usr/bin/env node
/**
 * PAE-04 CP-QA-HUB-03 / Chromium UI + IndexedDB synthetic scope.
 * Runs ONLY against already staged qa-hub/.run/site using one new loopback
 * ephemeral port and an empty Chromium context. No WebKit/SW/offline recheck.
 * No cloud writes, token, personal records, existing browser profiles or retry.
 * Local report: qa-hub/.run/crud-v233-report.json, create-only.
 */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT=dirname(fileURLToPath(import.meta.url));
const SITE=join(ROOT,'.run','site');
const REPORT=join(ROOT,'.run','crud-v233-report.json');
const SOURCE='3020e5c1278e5073c229a0ed36a35a9815658c15';
const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';
const STORES=['pressures','medications','intakes','intakeEvents'];
const FILES=new Set([
  'index.html','app.js','styles.css','home.js','home.css',
  'med_guard.mjs','med_matcher.mjs','med_guard.css',
  'personal_adapter.js','offline_status.js','manifest.webmanifest','sw.js',
  'personal_profile.json','icons/icon.svg','icons/apple-touch-icon.png',
  'icons/icon-192.png','icons/icon-512.png'
]);
const TYPES={
  '.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
  '.json':'application/json; charset=utf-8',
  '.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png'
};
const meds=[
  {name:'QA-ORION-011',kind:'regular',time:'12:00',slot:true},
  {name:'QA-QUARTZ-022',kind:'course',time:'12:01',slot:true},
  {name:'QA-RIVER-033',kind:'asNeeded',time:'12:02',slot:false}
];

function gate(ok,code){if(!ok)throw Error(code);}
function day(offset=0){return new Date(Date.now()+offset*86400000).toISOString().slice(0,10);}
async function preflight(){
  try {await stat(REPORT);throw Error('REPORT_EXISTS_STOP_FIRST');}
  catch(e){if(e.code!=='ENOENT')throw e;}
  const index=await stat(join(SITE,'index.html'));
  gate(index.isFile(),'STAGED_SITE_MISSING');
  const profile=JSON.parse(await readFile(join(SITE,'personal_profile.json'),'utf8'));
  gate(profile.schema==='PAE04_PERSONAL_QA_PROFILE_V1' &&
    profile.purpose==='PERSONAL_TEST_ONLY' &&
    profile.constraints?.seed_intakes===false &&
    profile.constraints?.seed_pressures===false &&
    Array.isArray(profile.medicines) && profile.medicines.length===10 &&
    profile.medicines.every(x=>typeof x.name==='string' && x.name.startsWith('QA-')),
    'NON_SYNTHETIC_PREVIEW_STOP_FIRST');
}
async function startServer(){
  const server=createServer(async(req,res)=>{
    try{
      if(req.method!=='GET'&&req.method!=='HEAD'){
        res.writeHead(405);res.end();return;
      }
      const u=new URL(req.url,'http://127.0.0.1');
      const rel=decodeURIComponent(u.pathname.slice(1))||'index.html';
      if(!FILES.has(rel)||rel.includes('..')||rel.startsWith('/')){
        res.writeHead(404);res.end();return;
      }
      const data=await readFile(join(SITE,rel));
      const ext=rel.slice(rel.lastIndexOf('.'));
      res.setHeader('X-Content-Type-Options','nosniff');
      res.setHeader('Cache-Control','no-store');
      res.setHeader('Content-Type',TYPES[ext]||'application/octet-stream');
      res.writeHead(200,{'Content-Length':data.length});
      res.end(req.method==='HEAD'?undefined:data);
    }catch{res.writeHead(404);res.end();}
  });
  await new Promise((ok,bad)=>{server.once('error',bad);server.listen(0,'127.0.0.1',ok)});
  return {server,base:'http://127.0.0.1:'+server.address().port+'/'};
}
async function ready(page){
  await page.waitForFunction(name=>(
    typeof db!=='undefined' && !!db && db.name===name &&
    document.querySelector('#med-form')?.dataset.pae04MedGuard==='mounted'
  ),DB_NAME,{timeout:15000});
}
async function readStores(page){
  return page.evaluate(()=>{
    const keys=['pressures','medications','intakes','intakeEvents'];
    if(typeof db==='undefined'||!db)throw Error('DATABASE_NOT_READY');
    return new Promise((resolve,reject)=>{
      const tx=db.transaction(keys,'readonly'),rows={};
      for(const key of keys){
        const req=tx.objectStore(key).getAll();
        req.onsuccess=()=>{rows[key]=req.result};
      }
      tx.oncomplete=()=>resolve(rows);
      tx.onabort=()=>reject(Error('READ_TRANSACTION_ABORT'));
      tx.onerror=()=>{};
    });
  });
}
async function waitCounts(page,p,m,i,e){
  await page.waitForFunction(a=>(
    typeof snapshot!=='undefined' && snapshot.pressures?.length===a[0] &&
    snapshot.medications?.length===a[1] && snapshot.intakes?.length===a[2] &&
    snapshot.intakeEvents?.length===a[3]
  ),[p,m,i,e],{timeout:15000});
}
async function wheel(page,selector,value){
  await page.locator(selector).evaluate((el,val)=>{
    el.value=val;
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
  },value);
}
async function addMed(page,med,number){
  const form=page.locator('#med-form');
  await form.locator('#med-name').fill(med.name);
  await form.locator('#med-dose').fill('QA условная доза');
  await form.locator('#med-kind').selectOption(med.kind);
  if(med.slot)await form.locator('#med-daily-target').selectOption('1');
  if(med.kind==='course'){
    await wheel(page,'#course-from',day(-3));
    await wheel(page,'#course-to',day(1));
  }
  const confirm=page.locator('#med-guard-panel button.med-guard-confirm');
  gate(await confirm.count()===1,'MED_GUARD_CONFIRM_MISSING');
  await confirm.click();
  await waitCounts(page,1,number,0,0);
  const rows=await readStores(page);
  gate(rows.medications.length===number &&
    rows.medications.filter(x=>x.name===med.name&&x.kind===med.kind).length===1,
    'MEDICATION_SAVE_MISMATCH');
}
async function mark(page,med,count){
  const card=page.locator('#med-list article.med-block').filter({hasText:med.name});
  gate(await card.count()===1,'CARD_NOT_FOUND');
  await card.locator('input.intake-time-input').first().fill(med.time);
  if(med.slot){
    const checkbox=card.locator('.med-schedule-slot input[type="checkbox"]').first();
    gate(await checkbox.count()===1,'CHECKBOX_NOT_FOUND');
    await checkbox.check();
  }else{
    const button=card.locator('button.intake-confirm-button');
    gate(await button.count()===1,'PRN_BUTTON_NOT_FOUND');
    await button.click();
  }
  await waitCounts(page,1,3,count,count);
}
function verify(data,when,intakeDay){
  gate(STORES.every(x=>Array.isArray(data[x])),'MISSING_OBJECT_STORES');
  gate(data.pressures.length===1 && data.medications.length===3 &&
    data.intakes.length===3 && data.intakeEvents.length===3,'UNEXPECTED_COUNTS');
  const pressure=data.pressures[0];
  assert.equal(pressure.systolic,120);
  assert.equal(pressure.diastolic,80);
  assert.equal(pressure.pulse,70);
  assert.equal(pressure.arm,'right');
  assert.equal(pressure.dateTime,when);
  for(const entry of meds){
    const med=data.medications.find(x=>x.name===entry.name);
    gate(!!med&&med.kind===entry.kind,'WRONG_MEDICATION_KIND');
    if(entry.slot)gate(med.dailyIntakes===1,'WRONG_DAILY_TARGET');
    const intakes=data.intakes.filter(x=>x.medId===med.id);
    gate(intakes.length===1 && intakes[0].status==='active' &&
      intakes[0].date===intakeDay &&
      intakes[0].takenAtLocal===intakeDay+'T'+entry.time,
      'INTAKE_SAVE_MISMATCH');
    gate(entry.slot?intakes[0].dailySlot===1:intakes[0].dailySlot===undefined,
      'INTAKE_SLOT_MISMATCH');
    const events=data.intakeEvents.filter(x=>x.intakeId===intakes[0].id);
    gate(events.length===1 && events[0].medId===med.id &&
      events[0].action==='marked' &&
      events[0].newTakenAtLocal===intakeDay+'T'+entry.time,
      'AUDIT_EVENT_MISMATCH');
  }
  gate(new Set(data.medications.map(x=>x.id)).size===3,'DUPLICATE_MEDICATION_ID');
  gate(new Set(data.intakes.map(x=>x.id)).size===3,'DUPLICATE_INTAKE_ID');
}
function stable(data){
  const result={};
  for(const key of STORES)result[key]=[...data[key]].sort((a,b)=>a.id.localeCompare(b.id));
  return result;
}
const report={
  schema:'PAE04_QA_HUB_CRUD_V1',sourceCommit:SOURCE,synthetic:true,
  engine:'Chromium',status:'NOT_RUN',checks:[],startedAt:new Date().toISOString()
};
let server=null,browser=null,phase='PREFLIGHT';
try{
  await preflight();
  phase='ISOLATED_SERVER';
  const site=await startServer();
  server=site.server;
  phase='BROWSER_LAUNCH';
  browser=await chromium.launch({headless:true});
  const ctx=await browser.newContext({
    timezoneId:'UTC',serviceWorkers:'block',viewport:{width:1280,height:900}
  });
  const page=await ctx.newPage();
  page.setDefaultTimeout(15000);
  await page.route('**/*',route=>{
    return route.request().url().startsWith(site.base)?route.continue():route.abort();
  });
  phase='ISOLATED_EMPTY_DB';
  await page.goto(site.base,{waitUntil:'domcontentloaded',timeout:15000});
  await ready(page);
  const initial=await readStores(page);
  gate(STORES.every(key=>initial[key]?.length===0),'NONEMPTY_FRESH_CONTEXT');
  report.checks.push('isolated-empty-indexeddb');
  phase='PRESSURE_AND_PULSE_UI';
  const pressureTime=new Date(Date.now()-3600000).toISOString().slice(0,16);
  await page.locator('button[data-page="pressure"]').first().click();
  await page.locator('#systolic').fill('120');
  await page.locator('#diastolic').fill('80');
  await page.locator('#pulse').fill('70');
  await wheel(page,'#pressure-datetime',pressureTime);
  await page.locator('#pressure-form button[type="submit"]').click();
  await waitCounts(page,1,0,0,0);
  const p=await readStores(page);
  gate(p.pressures[0]?.systolic===120 && p.pressures[0]?.diastolic===80 &&
    p.pressures[0]?.pulse===70 && p.pressures[0]?.arm==='right','PRESSURE_SAVE');
  report.checks.push('pressure-and-pulse-ui-save');
  phase='THREE_MEDICATIONS_UI';
  await page.locator('button[data-page="meds"]').first().click();
  await page.locator('details.v232-add-med > summary').click();
  for(let i=0;i<meds.length;i++)await addMed(page,meds[i],i+1);
  report.checks.push('three-medication-kinds-ui-save');
  phase='THREE_INTAKE_MARKS_UI';
  const intakeDay=day(-1);
  await wheel(page,'#intake-date',intakeDay);
  for(let i=0;i<meds.length;i++)await mark(page,meds[i],i+1);
  report.checks.push('three-intake-ui-marks');
  phase='AUDIT_AND_RELOAD';
  const before=await readStores(page);
  verify(before,pressureTime,intakeDay);
  report.checks.push('intake-audit-atomic-records');
  await page.reload({waitUntil:'domcontentloaded',timeout:15000});
  await ready(page);
  await waitCounts(page,1,3,3,3);
  const after=await readStores(page);
  verify(after,pressureTime,intakeDay);
  assert.deepStrictEqual(stable(after),stable(before));
  report.checks.push('indexeddb-reload-persistence');
  gate((await page.locator('#stat-pressure').innerText()).trim()==='1' &&
    (await page.locator('#stat-meds').innerText()).trim()==='3' &&
    (await page.locator('#stat-intakes').innerText()).trim()==='3',
    'UI_COUNTER_MISMATCH');
  report.checks.push('ui-counters-after-reload');
  report.status='PASS_SCOPED_CRUD';
}catch(error){
  report.status='FAIL_STOP_FIRST';
  report.failedPhase=phase;
  report.errorClass=error?.name==='AssertionError'?'AssertionError':
    error?.name==='TimeoutError'?'TimeoutError':'OtherError';
  process.exitCode=1;
}finally{
  if(browser)try{await browser.close()}catch{process.exitCode=1;}
  if(server)try{await new Promise(ok=>server.close(ok))}catch{process.exitCode=1;}
  report.finishedAt=new Date().toISOString();
  try{
    await writeFile(REPORT,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
    const saved=JSON.parse(await readFile(REPORT,'utf8'));
    assert.equal(saved.status,report.status);
    assert.deepStrictEqual(saved.checks,report.checks);
    console.log(JSON.stringify({status:report.status,checks:report.checks,
      failedPhase:report.failedPhase||null,report:'qa-hub/.run/crud-v233-report.json',
      sourceCommit:SOURCE,synthetic:true,readback:'PASS',githubWrites:0},null,2));
  }catch{
    console.error('BLOCKED_REPORT_WRITE_OR_READBACK_STOP_FIRST');
    process.exitCode=1;
  }
}

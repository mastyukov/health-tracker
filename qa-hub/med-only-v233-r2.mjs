#!/usr/bin/env node
/**
 * PAE-04 CP-QA-HUB-03 / medication-only diagnostic after prior scoped failure.
 * No pressure QA repetition. A fresh Chromium context on a new loopback-only
 * port uses the EXISTING synthetic site. No SW/offline QA, no external traffic.
 * Strict STOP_FIRST. Prior FAIL report preserved, new report create-only.
 */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { stat, readFile, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT=dirname(fileURLToPath(import.meta.url));
const SITE=join(ROOT,'.run','site');
const PRIOR=join(ROOT,'.run','crud-v233-report.json');
const REPORT=join(ROOT,'.run','med-v233-r2-report.json');
const SOURCE='3020e5c1278e5073c229a0ed36a35a9815658c15';
const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';
const STORES=['pressures','medications','intakes','intakeEvents'];
const FILES=new Set(['index.html','app.js','styles.css','home.js','home.css',
  'med_guard.mjs','med_matcher.mjs','med_guard.css','personal_adapter.js',
  'offline_status.js','manifest.webmanifest','sw.js','personal_profile.json',
  'icons/icon.svg','icons/apple-touch-icon.png','icons/icon-192.png','icons/icon-512.png']);
const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
  '.json':'application/json; charset=utf-8','.webmanifest':'application/manifest+json',
  '.svg':'image/svg+xml','.png':'image/png'};
const MEDS=[
  {name:'QA-ORION-011',kind:'regular',time:'12:00',scheduled:true},
  {name:'QA-QUARTZ-022',kind:'course',time:'12:01',scheduled:true},
  {name:'QA-RIVER-033',kind:'asNeeded',time:'12:02',scheduled:false}
];
function gate(cond,code){if(!cond)throw Error(code);}
function day(offset=0){return new Date(Date.now()+offset*86400000).toISOString().slice(0,10);}
async function preflight(){
  try{await stat(REPORT);throw Error('NEW_REPORT_ALREADY_EXISTS_STOP_FIRST');}
  catch(e){if(e.code!=='ENOENT')throw e;}
  const existing=JSON.parse(await readFile(PRIOR,'utf8'));
  gate(existing.sourceCommit===SOURCE && existing.synthetic===true &&
    existing.status==='FAIL_STOP_FIRST' &&
    existing.failedPhase==='THREE_MEDICATIONS_UI' &&
    existing.errorClass==='TimeoutError' &&
    JSON.stringify(existing.checks)===JSON.stringify([
      'isolated-empty-indexeddb','pressure-and-pulse-ui-save'
    ]),'PRIOR_FAILURE_NOT_MATCHED');
  await stat(join(SITE,'index.html'));
  const profile=JSON.parse(await readFile(join(SITE,'personal_profile.json'),'utf8'));
  gate(profile.schema==='PAE04_PERSONAL_QA_PROFILE_V1' &&
    profile.purpose==='PERSONAL_TEST_ONLY' &&
    profile.constraints?.seed_intakes===false &&
    profile.constraints?.seed_pressures===false &&
    profile.medicines?.length===10 &&
    profile.medicines.every(x=>typeof x.name==='string' && x.name.startsWith('QA-')),
    'PREVIEW_NOT_SYNTHETIC');
}
async function serve(){
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
  return page.evaluate(()=>new Promise((resolve,reject)=>{
    if(typeof db==='undefined'||!db)return reject(Error('DB_NOT_READY'));
    const keys=['pressures','medications','intakes','intakeEvents'];
    const tx=db.transaction(keys,'readonly'),rows={};
    for(const key of keys){
      const req=tx.objectStore(key).getAll();
      req.onsuccess=()=>{rows[key]=req.result};
    }
    tx.oncomplete=()=>resolve(rows);
    tx.onabort=()=>reject(Error('READ_ABORT'));
  }));
}
async function waitCounts(page,m,i,e){
  await page.waitForFunction(v=>(typeof snapshot!=='undefined' &&
    snapshot.pressures?.length===0 &&
    snapshot.medications?.length===v[0] &&
    snapshot.intakes?.length===v[1] &&
    snapshot.intakeEvents?.length===v[2]),[m,i,e],{timeout:10000});
}
async function setDate(page,selector,value){
  await page.locator(selector).evaluate((el,val)=>{
    el.value=val;
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
  },value);
}
const report={schema:'PAE04_MED_ONLY_R2_V1',sourceCommit:SOURCE,synthetic:true,
  engine:'Chromium',status:'NOT_RUN',checks:[],startedAt:new Date().toISOString()};
let browser=null,server=null,phase='PREFLIGHT';
try{
  await preflight();
  phase='ISOLATED_LOOPBACK_SERVER';
  const site=await serve();server=site.server;
  phase='NEW_CHROMIUM_CONTEXT';
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({
    timezoneId:'UTC',serviceWorkers:'block',viewport:{width:1280,height:900}
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);
  await page.route('**/*',route=>route.request().url().startsWith(site.base)
    ?route.continue():route.abort());
  phase='EMPTY_MEDICATION_DATABASE';
  await page.goto(site.base,{waitUntil:'domcontentloaded',timeout:15000});
  await ready(page);
  const initial=await readStores(page);
  gate(STORES.every(x=>initial[x]?.length===0),'NONEMPTY_FRESH_CONTEXT');
  report.checks.push('empty-isolated-medication-db');
  phase='NAVIGATE_MEDICATION_PAGE';
  await page.locator('button[data-page="meds"]').first().click();
  await page.locator('details.v232-add-med > summary').click();
  for(let index=0;index<MEDS.length;index++){
    const med=MEDS[index],num=index+1,form=page.locator('#med-form');
    phase='MED_'+num+'_FILL_NAME';
    await form.locator('#med-name').fill(med.name);
    // Deliberately leave optional dose blank: a pending "change" on #med-dose
    // can redraw/detach the dynamically mounted approval button on blur.
    phase='MED_'+num+'_SELECT_KIND';
    await form.locator('#med-kind').selectOption(med.kind);
    phase='MED_'+num+'_SELECT_SCHEDULE';
    if(med.scheduled)await form.locator('#med-daily-target').selectOption('1');
    if(med.kind==='course'){
      phase='MED_'+num+'_SET_COURSE_DATES';
      await setDate(page,'#course-from',day(-3));
      await setDate(page,'#course-to',day(1));
    }
    phase='MED_'+num+'_APPROVAL_BUTTON';
    const approval=page.locator('#med-guard-panel button.med-guard-confirm');
    gate(await approval.count()===1,'MED_APPROVAL_BUTTON_NOT_FOUND');
    phase='MED_'+num+'_APPROVAL_CLICK';
    await approval.click({timeout:10000});
    phase='MED_'+num+'_WAIT_DB';
    await waitCounts(page,num,0,0);
    const rows=await readStores(page);
    gate(rows.medications.length===num &&
      rows.medications.some(x=>x.name===med.name&&x.kind===med.kind),
      'MED_NOT_SAVED');
    report.checks.push('medication-'+num+'-saved');
  }
  phase='SET_INTAKE_DAY';
  const intakeDay=day(-1);
  await setDate(page,'#intake-date',intakeDay);
  for(let index=0;index<MEDS.length;index++){
    const med=MEDS[index],num=index+1;
    phase='INTAKE_'+num+'_FIND_CARD';
    const card=page.locator('#med-list article.med-block').filter({hasText:med.name});
    gate(await card.count()===1,'INTAKE_CARD_NOT_FOUND');
    phase='INTAKE_'+num+'_SET_TIME';
    await card.locator('input.intake-time-input').first().fill(med.time);
    phase='INTAKE_'+num+'_CONFIRM';
    if(med.scheduled){
      const check=card.locator('.med-schedule-slot input[type="checkbox"]').first();
      gate(await check.count()===1,'SCHEDULE_CHECKBOX_NOT_FOUND');
      await check.check({timeout:10000});
    }else{
      const button=card.locator('button.intake-confirm-button');
      gate(await button.count()===1,'PRN_BUTTON_NOT_FOUND');
      await button.click({timeout:10000});
    }
    phase='INTAKE_'+num+'_WAIT_AUDIT';
    await waitCounts(page,3,num,num);
    report.checks.push('intake-'+num+'-with-audit');
  }
  const verify=rows=>{
    gate(rows.pressures.length===0 && rows.medications.length===3 &&
      rows.intakes.length===3 && rows.intakeEvents.length===3,
      'STORED_COUNTS_MISMATCH');
    for(const med of MEDS){
      const m=rows.medications.find(x=>x.name===med.name);
      gate(!!m && m.kind===med.kind,'KIND_MISMATCH');
      if(med.scheduled)gate(m.dailyIntakes===1,'SCHEDULE_MISMATCH');
      const intakes=rows.intakes.filter(x=>x.medId===m.id);
      gate(intakes.length===1 && intakes[0].status==='active' &&
        intakes[0].date===intakeDay &&
        intakes[0].takenAtLocal===intakeDay+'T'+med.time,
        'INTAKE_MISMATCH');
      gate(med.scheduled?intakes[0].dailySlot===1:intakes[0].dailySlot===undefined,
        'SLOT_MISMATCH');
      const events=rows.intakeEvents.filter(x=>x.intakeId===intakes[0].id);
      gate(events.length===1 && events[0].medId===m.id &&
        events[0].action==='marked' &&
        events[0].newTakenAtLocal===intakeDay+'T'+med.time,
        'AUDIT_MISMATCH');
    }
  };
  phase='BEFORE_RELOAD_AUDIT';
  const before=await readStores(page);verify(before);
  report.checks.push('medication-audit-before-reload');
  phase='RELOAD_PERSISTENCE';
  await page.reload({waitUntil:'domcontentloaded',timeout:15000});
  await ready(page);
  await waitCounts(page,3,3,3);
  const after=await readStores(page);verify(after);
  for(const key of STORES)assert.deepStrictEqual(
    [...after[key]].sort((a,b)=>a.id.localeCompare(b.id)),
    [...before[key]].sort((a,b)=>a.id.localeCompare(b.id))
  );
  report.checks.push('medication-indexeddb-reload');
  report.status='PASS_SCOPED_MED';
}catch(e){
  report.status='FAIL_STOP_FIRST';
  report.failedPhase=phase;
  report.errorClass=e?.name==='TimeoutError'?'TimeoutError':
    e?.name==='AssertionError'?'AssertionError':'OtherError';
  process.exitCode=1;
}finally{
  if(browser)try{await browser.close()}catch{process.exitCode=1;}
  if(server)try{await new Promise(ok=>server.close(ok))}catch{process.exitCode=1;}
  report.finishedAt=new Date().toISOString();
  try{
    await writeFile(REPORT,JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
    const result=JSON.parse(await readFile(REPORT,'utf8'));
    assert.equal(result.status,report.status);
    assert.deepStrictEqual(result.checks,report.checks);
    console.log(JSON.stringify({status:report.status,checks:report.checks,
      failedPhase:report.failedPhase||null,errorClass:report.errorClass||null,
      readback:'PASS',report:'qa-hub/.run/med-v233-r2-report.json',
      synthetic:true,githubWrites:0},null,2));
  }catch{
    console.error('BLOCKED_REPORT_WRITE_READBACK_STOP_FIRST');
    process.exitCode=1;
  }
}

import { createHash, randomUUID } from 'node:crypto';
import { mkdir, writeFile, readFile, readdir, stat, rename, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, join, resolve, sep, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOME=dirname(fileURLToPath(import.meta.url));
const SITE=join(HOME,'.run','site');
const SRC='https://raw.githubusercontent.com/mastyukov/health-tracker/3020e5c1278e5073c229a0ed36a35a9815658c15/site/';
const PINS={
  "index.html": "beb4be69b81e31deb5d03543749ef549ce4953e2",
  "app.js": "3725145e5c48a23027723cc62de9572c0be7feec",
  "styles.css": "33fc30b7c85f7cdbf60f43a206fb1f47a9c72fb4",
  "home.js": "e579cc0db5c8e360b3a57870d0e3bc36a087f1c7",
  "home.css": "f38d59e4ef42fa44e64dd471d677881fccb5d040",
  "med_guard.mjs": "9435ec752a887f0e6e5b696be6eaefc7d6999704",
  "med_matcher.mjs": "cf08822f5e71c8fb505fbec066e5eec9145215c6",
  "med_guard.css": "1ebdff67c6ae4088759bc1c9059ee7f2f5fd6b2e",
  "personal_adapter.js": "277b8bc2435d4bd9f4b30c89db15570ca2f2656f",
  "offline_status.js": "15bebef4326103c10189bacbf118037a9f64e5b8",
  "manifest.webmanifest": "e74f10f038d5a4e1c04936c1246435de58282d35",
  "icons/icon.svg": "05b76763ede5f0d88e2b855f3d90ed72ddf64842",
  "icons/apple-touch-icon.png": "4cf9879b433979d1508c8ffdbb312e29123ef549",
  "icons/icon-192.png": "c07d28a59f0d773c2e18af62b261b50389f60a94",
  "icons/icon-512.png": "09673205f1b64d689d8899c1096031ba351f34cc",
  "sw.js": "eca3ff2677e9ea8397214a015e92b90b0011a2a1"
};
const PORT=8765;
const kinds=['regular','course','asNeeded'];
function syntheticProfile(){
  return {
    schema:'PAE04_PERSONAL_QA_PROFILE_V1',
    purpose:'PERSONAL_TEST_ONLY',
    description:'SYNTHETIC QA ONLY — no personal medicine or clinical data',
    constraints:{seed_intakes:false,seed_pressures:false},
    medicines:Array.from({length:10},(_,i)=>({
      key:'qa-med-'+String(i+1).padStart(2,'0'),
      name:'QA-Тестовый препарат '+String(i+1).padStart(2,'0'),
      dose:(i+1)+' усл. ед.',
      kind:kinds[i%3],
      category:i%4===0?'supplement':'medicine',
      product_strength_mg:null,
      form:'таблетки',
      from:null,to:null
    }))
  };
}
function shaBlob(data){
  return createHash('sha1').update(Buffer.from('blob '+data.length+'\0')).update(data).digest('hex');
}
function fail(message){throw new Error(message)}
async function prepare(){
  const target=join(HOME,'.run','staging-'+randomUUID());
  await mkdir(target,{recursive:true});
  try{
    for(const [rel,expected] of Object.entries(PINS)){
      if(rel.includes('..')||rel==='personal_profile.json'||rel.startsWith('/'))fail('DISALLOWED_PATH '+rel);
      const response=await fetch(SRC+rel,{signal:AbortSignal.timeout(25000),redirect:'error'});
      if(!response.ok)fail('FETCH_FAILED '+rel+' HTTP '+response.status);
      const data=Buffer.from(await response.arrayBuffer());
      if(data.length>200000)fail('OVERSIZE '+rel);
      if(shaBlob(data)!==expected)fail('SOURCE_SHA_MISMATCH '+rel);
      const output=join(target,rel);
      await mkdir(dirname(output),{recursive:true});
      await writeFile(output,data,{flag:'wx'});
    }
    const fixture=syntheticProfile();
    if(fixture.medicines.length!==10||fixture.medicines.some(x=>!x.name.startsWith('QA-')))fail('NON_SYNTHETIC_FIXTURE');
    await writeFile(join(target,'personal_profile.json'),JSON.stringify(fixture,null,2)+'\n',{flag:'wx'});
    const sw=await readFile(join(target,'sw.js'),'utf8');
    if(!sw.includes("'./personal_profile.json'"))fail('SW_MISSING_PROFILE_REFERENCE');
    // No original profile has been fetched, cloned or read.
    await mkdir(dirname(SITE),{recursive:true});
    try{await stat(SITE);fail('PREVIEW_ALREADY_EXISTS_STOP_FIRST')}catch(e){if(e.code!=='ENOENT')throw e}
    await rename(target,SITE);
    console.log(JSON.stringify({status:'PASS_STATIC_PREP',sourceCommit:'3020e5c1278e5073c229a0ed36a35a9815658c15',sourceAssets:Object.keys(PINS).length,synthetic:true,preview:SITE}));
  }catch(e){console.error('BLOCKED_PREP '+e.message);process.exitCode=1;/* Preserve staging for forensic review; no retry */ }
}
const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png'};
async function listen(host='127.0.0.1',port=0){
  await stat(join(SITE,'index.html'));
  const server=createServer(async(req,res)=>{
    try{
      if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end();return}
      const url=new URL(req.url,'http://localhost');
      const rel=decodeURIComponent(url.pathname)==='/'?'index.html':decodeURIComponent(url.pathname).split('/').filter(Boolean).join('/');
      const path=resolve(SITE,rel);
      if(!path.startsWith(SITE+sep) || rel.includes('..')){res.writeHead(403);res.end();return}
      const st=await stat(path);
      if(!st.isFile()){res.writeHead(404);res.end();return}
      res.setHeader('Content-Type',TYPES[extname(path)]||'application/octet-stream');
      res.setHeader('X-Content-Type-Options','nosniff');
      if(rel==='personal_profile.json')res.setHeader('X-PAE-Data','synthetic-only');
      const body=await readFile(path);
      res.writeHead(200,{'Content-Length':body.length});res.end(req.method==='HEAD'?undefined:body);
    }catch{res.writeHead(404);res.end()}
  });
  await new Promise((ok,bad)=>{server.once('error',bad);server.listen(port,host,ok)});
  return {server,address:server.address()};
}
async function serve(){
  const {address}=await listen('0.0.0.0',PORT);
  console.log('PAE QA HUB / SYNTHETIC ONLY / Private port required / HTTP localhost '+address.port);
}
async function test(){
  const report={status:'NOT_RUN',sourceCommit:'3020e5c1278e5073c229a0ed36a35a9815658c15',synthetic:true,results:[],startedAt:new Date().toISOString()};
  let server=null;
  try{
    const preview=await listen('127.0.0.1',0);server=preview.server;
    const base='http://127.0.0.1:'+preview.address.port+'/';
    const {chromium,webkit}=await import('playwright');
    for(const [name,engine] of [['Chromium',chromium],['WebKit',webkit]]){
      const browser=await engine.launch({headless:true});
      try{
        const ctx=await browser.newContext({serviceWorkers:'allow'});
        const page=await ctx.newPage();
        await page.goto(base,{waitUntil:'domcontentloaded',timeout:15000});
        const data=await page.evaluate(async()=>await (await fetch('./personal_profile.json')).json());
        if(data.purpose!=='PERSONAL_TEST_ONLY'||data.medicines.length!==10||data.medicines.some(x=>!x.name.startsWith('QA-')))fail('PROFILE_NOT_SYNTHETIC');
        await page.evaluate(async()=>Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(new Error('SW_READY_TIMEOUT')),15000))]));
        await page.reload({waitUntil:'domcontentloaded'});
        await page.waitForFunction(()=>!!navigator.serviceWorker.controller,{timeout:15000});
        await ctx.setOffline(true);
        await page.reload({waitUntil:'domcontentloaded',timeout:15000});
        const ok=await page.evaluate(()=>document.body?.textContent?.length>500);
        if(!ok)fail('OFFLINE_SHELL_EMPTY');
        report.results.push({browser:name,status:'PASS',checks:['synthetic-profile','online-load','service-worker','offline-reload']});
        await ctx.close();
      }finally{await browser.close()}
    }
    report.status='PASS_SCOPED';
  }catch(e){
    report.status='FAIL_STOP_FIRST';
    report.error=String(e?.message||e).slice(0,250);
    process.exitCode=1;
  }finally{
    report.finishedAt=new Date().toISOString();
    await mkdir(join(HOME,'.run'),{recursive:true});
    await writeFile(join(HOME,'.run','report.json'),JSON.stringify(report,null,2)+'\n');
    if(server)await new Promise(ok=>server.close(ok));
    console.log(JSON.stringify(report,null,2));
  }
}
const command=process.argv[2];
if(command==='prepare')await prepare();
else if(command==='serve')await serve();
else if(command==='test')await test();
else fail('USAGE node qa-hub.mjs prepare | serve | test');

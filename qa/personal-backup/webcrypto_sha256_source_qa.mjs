import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto,createHash} from 'node:crypto';
const src=fs.readFileSync(new URL('../../site/app.js',import.meta.url),'utf8');
const from=src.indexOf('function canonical(value){');
const to=src.indexOf('function normalizedBackupData(version,data){',from);
assert.ok(from>=0&&to>from,'source SHA function markers');
const funcs=src.slice(from,to);
assert.ok(funcs.includes('async function sha256(value){'),'real app SHA');
const {canonical,sha256}=new Function('crypto','TextEncoder',funcs+';return {canonical,sha256}')(webcrypto,TextEncoder);
const checks=[];
async function verify(label,v){
 const actual=await sha256(v);
 const independent=createHash('sha256').update(Buffer.from(canonical(v),'utf8')).digest('hex');
 assert.equal(actual,independent,label);
 assert.match(actual,/^[a-f0-9]{64}$/);
 checks.push(label);
}
await verify('EMPTY_OBJECT',{});
await verify('EMPTY_ARRAY',[]);
await verify('NESTED',{z:[1,3],a:{name:'SYNTHETIC',done:true}});
await verify('UNICODE',{note:'Только синтетика — 薬'});
await verify('NUMERIC',{zero:0,negative:-4,decimal:121.5});
for(const version of [1,2,3]){
 const data={pressures:[],medications:[],intakes:[]};
 if(version===3)data.intakeEvents=[];
 await verify('BACKUP_V'+version,{format:'pae04.healthtracker.synthetic-backup',version,exportedAt:'2026-11-17T12:00:00.000Z',data});
}
const original={data:{pressures:[{id:'SYN',systolic:122}],medications:[],intakes:[],intakeEvents:[]}};
assert.notEqual(await sha256(original),await sha256({data:{...original.data,pressures:[{id:'SYN',systolic:123}]}}));
checks.push('TAMPER_ALTERS_DIGEST');
assert.equal(await sha256({z:2,a:1}),await sha256({a:1,z:2}));
checks.push('CANONICAL_ORDER');
console.log('QA_REAL_WEBCRYPTO '+JSON.stringify({status:'PASS_REAL_NODE_WEBCRYPTO',count:checks.length,cases:checks,comparison:'independent createHash sha256',limitations:['No Safari/WebKit','No real IndexedDB','Only synthetic data']}));

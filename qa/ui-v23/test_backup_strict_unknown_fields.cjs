'use strict';
// CP39: standalone synthetic-only test for the EXACT helper from published site/app.js.
// Run once: node --test qa/ui-v23/test_backup_strict_unknown_fields.cjs
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const app=fs.readFileSync(path.resolve(__dirname,'../../site/app.js'),'utf8');
new vm.Script(app,{filename:'site/app.js'}); // compile full app without executing DOM/IndexedDB
const begin=app.indexOf('function assertKnownBackupFields(envelope){');
const end=app.indexOf('function normalizedBackupData(',begin);
assert.ok(begin>=0&&end>begin,'Exact helper must exist before normalization');
assert.equal(app.indexOf('function assertKnownBackupFields(envelope){',begin+1),-1,'No duplicate helper');
const guard=vm.runInNewContext(app.slice(begin,end)+'\nassertKnownBackupFields;',Object.create(null),{timeout:1000});
function fixture(version=3){
 const data={
  pressures:[{id:'pressure001',systolic:120,diastolic:80,pulse:60,dateTime:'2026-01-01T10:00',note:'synthetic',arm:'right',createdAt:'2026-01-01T10:00:00Z'}],
  medications:[{id:'medicine001',name:'SYNTHETIC',dose:'test',kind:'regular',from:null,to:null,createdAt:'2026-01-01T10:00:00Z'}],
  intakes:[{id:'intake001',medId:'medicine001',date:'2026-01-01',markedAt:'2026-01-01T10:00:00Z',takenAtLocal:'2026-01-01T10:00',status:'active',dailySlot:1,reason:'synthetic'}],
  intakeEvents:[{id:'event001',intakeId:'intake001',medId:'medicine001',action:'marked',at:'2026-01-01T10:00:00Z',newTakenAtLocal:'2026-01-01T10:00'}]
 };
 if(version<3)delete data.intakeEvents; // legacy backup normalization uses []
 return {format:'pae04.healthtracker.synthetic-backup',version,exportedAt:'2026-01-01T10:00:00Z',data,sha256:'a'.repeat(64)};
}
function clone(v){return JSON.parse(JSON.stringify(v));}
for(const version of [1,2,3])test('valid synthetic backup v'+version+' retains compatibility',()=>{
 const doc=fixture(version),before=clone(doc);
 assert.equal(guard(doc),undefined);
 assert.deepEqual(doc,before);
});
const negatives=[
 ['envelope',doc=>{doc.syntheticUnknown=true;}],
 ['pressure',doc=>{doc.data.pressures[0].syntheticUnknown=true;}],
 ['intake',doc=>{doc.data.intakes[0].syntheticUnknown=true;}],
 ['intakeEvent',doc=>{doc.data.intakeEvents[0].syntheticUnknown=true;}]
];
for(const [label,mutate] of negatives)test('reject unknown '+label+' field without data mutation',()=>{
 const doc=fixture(3);mutate(doc);const before=clone(doc);
 assert.throws(()=>guard(doc),/Неизвестное поле резервной копии/);
 assert.deepEqual(doc,before);
});
test('guard only validates external JSON; both ingress paths use it before normalization',()=>{
 assert.equal((app.match(/assertKnownBackupFields\(parsed\);/g)||[]).length,2);
 const verify=app.indexOf('async function verifyDownloadedBackup(');
 const preview=app.indexOf('async function previewImport(');
 assert.ok(verify>=0&&preview>verify);
 const a=app.indexOf('assertKnownBackupFields(parsed);',verify);
 const b=app.indexOf('assertKnownBackupFields(parsed);',preview);
 assert.ok(a>verify&&a<preview&&b>preview);
});

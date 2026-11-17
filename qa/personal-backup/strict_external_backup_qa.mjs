import assert from 'node:assert/strict';
import fs from 'node:fs';
const text=fs.readFileSync('site/app.js','utf8');
const marker='// PAE-04 owner-approved policy: selected EXTERNAL backups only, after SHA-256.';
const start=text.indexOf(marker),stop=text.indexOf('function validateBackupData(data,includeLocal=true){',start);
assert.ok(start>=0&&stop>start,'external schema guard exists');
const guard=text.slice(start,stop);
assert.equal(text.split('validateExternalBackupShape(parsed);').length-1,2,'two external input sites only');
assert.ok(!/\bdb\b|indexedDB|objectStore|transaction|snapshot|addRecord/.test(guard),'guard has zero DB writes');
const verification=text.slice(text.indexOf('async function verifyDownloadedBackup('),text.indexOf('function resetImportCheckpoint('));
const preview=text.slice(text.indexOf('async function previewImport('),text.indexOf('async function downloadImportCheckpoint('));
for(const [label,scope] of [['VERIFY',verification],['PREVIEW',preview]]){
 const sha=scope.indexOf('if(await sha256(body)!==expected)');
 const gate=scope.indexOf('validateExternalBackupShape(parsed);');
 const normalize=scope.indexOf('normalizedBackupData(parsed.version,parsed.data)');
 assert.ok(sha>=0&&gate>sha&&normalize>gate,label+' must check SHA then schema then normalization');
}
assert.ok(!guard.includes('window.location'),'guard cannot navigate');
const check=new Function('STORE_NAMES',guard+';return validateExternalBackupShape;')(['pressures','medications','intakes','intakeEvents']);
const copy=o=>JSON.parse(JSON.stringify(o)),now='2026-11-17T12:00:00.000Z',day='2026-11-17',dt=day+'T11:00',id='TEST_SYNTH_123';
const data={
pressures:[{id:id+'_P',systolic:121,diastolic:77,pulse:65,dateTime:dt,note:'SYNTHETIC_ONLY',arm:'right',createdAt:now}],
medications:[{id:id+'_M',name:'SYNTHETIC ONLY',dose:'',kind:'regular',from:null,to:null,createdAt:now}],
intakes:[{id:id+'_I',medId:id+'_M',date:day,takenAtLocal:dt,markedAt:now,status:'active'}],
intakeEvents:[{id:id+'_E',intakeId:id+'_I',medId:id+'_M',action:'marked',at:now,newTakenAtLocal:dt}]
};
const base={format:'pae04.healthtracker.synthetic-backup',version:3,exportedAt:now,sha256:'a'.repeat(64),data};
const cases=[
['valid_v3',true,x=>{}],
['valid_v2',true,x=>{x.version=2;delete x.data.intakeEvents}],
['valid_v1',true,x=>{x.version=1;delete x.data.intakeEvents}],
['valid_empty_v3',true,x=>{for(const n of Object.keys(x.data))x.data[n]=[]}],
['valid_optional_pressure_updatedAt',true,x=>{x.data.pressures[0].updatedAt=now}],
['valid_optional_intake_slot',true,x=>{x.data.intakes[0].dailySlot=1;x.data.intakes[0].takenQuantity={numerator:1,denominator:2};x.data.intakes[0].takenUnit='unit'}],
['valid_optional_event_correction',true,x=>{x.data.intakeEvents[0].oldTakenAtLocal=dt}],
['unknown_envelope',false,x=>{x.syntheticUnknown=1}],
['unknown_data_store_v3',false,x=>{x.data.ghost=[]}],
['unknown_data_store_v2',false,x=>{x.version=2;delete x.data.intakeEvents;x.data.ghost=[]}],
['legacy_v2_fourth_store_present',false,x=>{x.version=2}],
['unknown_pressure',false,x=>{x.data.pressures[0].syntheticUnknown=1}],
['unknown_intake',false,x=>{x.data.intakes[0].syntheticUnknown=1}],
['unknown_event',false,x=>{x.data.intakeEvents[0].syntheticUnknown=1}],
['missing_pressures',false,x=>{delete x.data.pressures}],
['missing_medications',false,x=>{delete x.data.medications}],
['missing_intakes',false,x=>{delete x.data.intakes}],
['missing_events_v3',false,x=>{delete x.data.intakeEvents}],
['wrong_data_shape',false,x=>{x.data=[]}],
['wrong_pressure_row',false,x=>{x.data.pressures=[null]}],
['wrong_intake_row',false,x=>{x.data.intakes=[[]]}],
['wrong_event_row',false,x=>{x.data.intakeEvents=[42]}],
['null_data',false,x=>{x.data=null}]
];
let n=0;
for(const [name,expected,alter] of cases){
 const value=copy(base);alter(value);let accepted=true;
 try{check(value)}catch{accepted=false}
 assert.equal(accepted,expected,'fixture '+name);n++;
}
console.log('PASS_EXTERNAL_SCHEMA '+n+'/'+cases.length);
console.log('PASS_SCOPED_CALL_SITE_ORDER 2/2');
console.log('PASS_GUARD_NO_DATABASE_WRITES');
console.log('LIMITATION actual IndexedDB, file picker, Safari and restore NOT RUN');

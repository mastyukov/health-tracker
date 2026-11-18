import assert from 'node:assert/strict';
import fs from 'node:fs';
import './strict_external_backup_qa.mjs';

// PAE-04 CP-UX02: synthetic, source-bound, fail-closed negative QA.
// Run from repository root: node qa/personal-backup/nested_quantity_qa.mjs
// Does not open the app, browser, IndexedDB, personal adapter or network.
const source=fs.readFileSync('site/app.js','utf8');
const marker='// PAE-04 owner-approved policy: selected EXTERNAL backups only, after SHA-256.';
const start=source.indexOf(marker);
const stop=source.indexOf('function validateBackupData(data,includeLocal=true){',start);
assert.ok(start>=0 && stop>start,'guard source markers');
const guard=source.slice(start,stop);
const nestedMarker='// Reject unrecognised nested quantity keys in selected external backups only.';
assert.equal(guard.split(nestedMarker).length-1,1,'exactly one guarded quantity block');
assert.ok(!/\bdb\b|indexedDB|objectStore|transaction|snapshot|addRecord/.test(guard),'guard has no DB writes');
const check=new Function('STORE_NAMES',guard+';return validateExternalBackupShape;')(['pressures','medications','intakes','intakeEvents']);
const now='2026-11-17T12:00:00.000Z';
function fixture(){
  return {format:'pae04.healthtracker.synthetic-backup',version:3,exportedAt:now,sha256:'a'.repeat(64),data:{
    pressures:[],medications:[],
    intakes:[{id:'SYN-I-001',medId:'SYN-M-001',date:'2026-11-17',takenAtLocal:'2026-11-17T11:00',markedAt:now,status:'active'}],
    intakeEvents:[]
  }};
}
const tests=[
  ['no_quantity',true,()=>{}],
  ['fraction_half',true,x=>{x.data.intakes[0].takenQuantity={numerator:1,denominator:2}}],
  ['fraction_one_and_half',true,x=>{x.data.intakes[0].takenQuantity={numerator:3,denominator:2}}],
  ['scalar_number_preserved',true,x=>{x.data.intakes[0].takenQuantity=.5}],
  ['scalar_string_preserved',true,x=>{x.data.intakes[0].takenQuantity='½'}],
  ['null_quantity',true,x=>{x.data.intakes[0].takenQuantity=null}],
  ['empty_nested_object_policy_deferred',true,x=>{x.data.intakes[0].takenQuantity={}}]
];
for(const key of ['unexpected','__proto__','constructor','prototype','toString','неизвестно','_private','newVersion','schemaVersion','numeratorX','denominatorX','$ref']){
  tests.push(['unknown_nested_'+key,false,x=>{
    const quantity=x.data.intakes[0].takenQuantity={numerator:1,denominator:2};
    Object.defineProperty(quantity,key,{value:'SYNTHETIC',enumerable:true,configurable:true});
  }]);
}
tests.push(['array_quantity',false,x=>{x.data.intakes[0].takenQuantity=[]}]);
tests.push(['nested_array_quantity',false,x=>{x.data.intakes[0].takenQuantity=[{numerator:1,denominator:2}]}]);
assert.equal(tests.length,21,'case count');
let passed=0;
for(const [label,expected,mutate] of tests){
  const v=fixture();mutate(v);
  // The only supported input is JSON, not arbitrary JS objects.
  const input=JSON.parse(JSON.stringify(v));
  let accepted=true;try{check(input)}catch{accepted=false}
  assert.equal(accepted,expected,label);passed++;
}
const verify=source.slice(source.indexOf('async function verifyDownloadedBackup('),source.indexOf('function resetImportCheckpoint('));
const preview=source.slice(source.indexOf('async function previewImport('),source.indexOf('async function downloadImportCheckpoint('));
function checkOrder(path){
  const sha=path.indexOf('if(await sha256(body)!==expected)');
  const guard=path.indexOf('validateExternalBackupShape(parsed);');
  const normalize=path.indexOf('normalizedBackupData(parsed.version,parsed.data)');
  return sha>=0&&guard>sha&&normalize>guard;
}
assert.ok(checkOrder(verify)&&checkOrder(preview),'SHA before guard before normalization in both handlers');
console.log('PASS_SOURCE_BOUND_NESTED_QUANTITY '+passed+'/21');
console.log('LIMITATIONS: no Safari/WebKit, IndexedDB, file picker, Node26 claim, or real medical data');

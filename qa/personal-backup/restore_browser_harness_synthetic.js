(function(){
 const checks=[],sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const el=id=>document.getElementById(id);
 const clone=v=>JSON.parse(JSON.stringify(v));
 const check=(name,ok,info)=>{checks.push({name,status:ok?'PASS':'FAIL',detail:info||null});if(!ok)throw Error('CHECK_FAILED_'+name)};
 async function until(pred,where,ms=12000){const started=Date.now();while(Date.now()-started<ms){if(pred())return;await sleep(100)}throw Error('TIMEOUT_'+where)}
 async function signed(data,version=3){const body={format:BACKUP_FORMAT,version,exportedAt:new Date().toISOString(),data:clone(data)};return {...body,sha256:await sha256(body)}}
 function sendFile(id,object,label){const input=el(id);const dt=new DataTransfer();const file=new File([JSON.stringify(object)],label+'.json',{type:'application/json'});dt.items.add(file);input.value='';input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));return file;}
 async function preview(obj,label,expected){
   sendFile('import-file',obj,label);
   await until(()=>{const s=el('import-preview').textContent||'';return s.includes('Ошибка:')||s.includes('Проверка SHA-256 PASS')},'preview_'+label);
   const msg=el('import-preview').textContent||'';
   if(expected==='reject')check('REJECT_'+label,msg.includes('Ошибка:')&&el('checkpoint-button').disabled,msg.slice(0,100));
   else check('PREVIEW_'+label,msg.includes('Проверка SHA-256 PASS')&&!el('checkpoint-button').disabled,msg.slice(0,100));
   return msg;
 }
 async function checkpoint(){
   const start=window.__qaDownloads.length;
   el('checkpoint-button').click();
   await until(()=>window.__qaDownloads.length>start&&!el('checkpoint-ack').disabled,'checkpoint');
   check('CHECKPOINT_EXTERNAL_BLOB',window.__qaDownloads[window.__qaDownloads.length-1].blob.size>100);
   el('checkpoint-ack').checked=true;
   el('checkpoint-ack').dispatchEvent(new Event('change',{bubbles:true}));
   check('CHECKPOINT_ACK_ENABLES_IMPORT',!el('import-button').disabled);
 }
 async function importSelected(expectedAdded){
   el('import-button').click();
   await until(()=>{const x=el('import-preview').textContent||'';return x.includes('Добавлено ')||x.includes('Ошибка:')},'apply');
   const x=el('import-preview').textContent||'';
   check('IMPORT_ADDED_'+expectedAdded,x.includes('Добавлено '+expectedAdded+' записей'),x.slice(0,150));
 }
 function finish(error){
   if(error)checks.push({name:'EXECUTION',status:'FAIL',detail:String(error).slice(0,250)});
   const report={status:checks.every(x=>x.status==='PASS')?'PASS_SCOPED_CHROME_INDEXEDDB':'FAIL_SCOPED_CHROME_INDEXEDDB',synthetic:true,checks,realIndexedDB:true,userRecordsAccessed:false,limitations:['Safari NOT RUN','iPhone restore NOT RUN','external downloaded file durability NOT verified']};
   const out=document.createElement('pre');out.id='qa-restore-result';out.textContent=JSON.stringify(report);document.body.append(out);
 }
 async function run(){
   await until(()=>typeof db!=='undefined'&&!!db,'dbopen');
   const initial=await readBackupSnapshot();
   check('EMPTY_4_STORES',STORE_NAMES.every(n=>Array.isArray(initial[n])&&initial[n].length===0));
   window.__qaDownloads=[];
   downloadFile=(name,blob)=>{window.__qaDownloads.push({name,blob})};
   window.confirm=()=>true;
   const now=new Date().toISOString(),day='2026-11-17',datetime='2026-11-17T11:00';
   const p={id:'synpress_000001',systolic:121,diastolic:77,pulse:65,dateTime:datetime,arm:'right',note:'SYNTHETIC',createdAt:now};
   const m={id:'synmedic_000001',name:'SYNTHETIC ONLY',dose:'',kind:'regular',from:null,to:null,createdAt:now};
   const i={id:'synintak_000001',medId:m.id,date:day,takenAtLocal:datetime,markedAt:now,status:'active'};
   const e={id:'synevent_000001',intakeId:i.id,medId:m.id,action:'marked',at:now,newTakenAtLocal:datetime};
   const data={pressures:[p],medications:[m],intakes:[i],intakeEvents:[e]};
   check('VALIDATED_SYNTHETIC_4_STORES',validateBackupData(data,false)===4);
   const backup=await signed(data);
   sendFile('verify-file',backup,'synthetic_verify');
   await until(()=>(el('verify-result').textContent||'').includes('PASS'),'verify_hash');
   check('VERIFY_SHA256_WITH_FILE_INPUT',el('verify-result').textContent.includes('SHA-256 совпадает'));
   await preview(backup,'synthetic_restore','accept');
   await checkpoint();
   await importSelected(4);
   const restored=await readBackupSnapshot();
   check('REAL_INDEXEDDB_4_STORES',STORE_NAMES.every(n=>restored[n].length===1));
   check('RESTORED_RECORDS_MATCH',canonical(restored)===canonical(data));
   await preview(backup,'repeat_same_backup','accept');
   await checkpoint();
   await importSelected(0);
   const noDup=await readBackupSnapshot();
   check('IDEMPOTENT_REPEAT',canonical(noDup)===canonical(restored));
   for(const [type,alter] of [
    ['envelope',x=>x.unknownSynthetic=true],
    ['pressure',x=>x.data.pressures[0].unknownSynthetic=true],
    ['intake',x=>x.data.intakes[0].unknownSynthetic=true],
    ['event',x=>x.data.intakeEvents[0].unknownSynthetic=true]
   ]){
      const obj=clone(backup);
      alter(obj);
      const {sha256:oldHash,...body}=obj;obj.sha256=await sha256(body);
      await preview(obj,'unknown_'+type,'reject');
      check('NO_IDB_MUTATION_'+type,canonical(await readBackupSnapshot())===canonical(restored));
   }
   const bad=clone(backup);bad.sha256='0'.repeat(64);
   await preview(bad,'tampered_SHA','reject');
   check('BAD_SHA_NO_MUTATION',canonical(await readBackupSnapshot())===canonical(restored));
   const conflicting=clone(data);conflicting.pressures[0].systolic=133;
   const conflictBackup=await signed(conflicting);
   sendFile('import-file',conflictBackup,'conflicting_id');
   await until(()=>(el('import-preview').textContent||'').includes('Конфликтов: 1'),'conflict_preview');
   check('CONFLICT_BLOCKS_IMPORT',el('checkpoint-button').disabled&&el('import-button').disabled);
   const addData=clone(data);addData.pressures=[{...p,id:'synpress_000002',systolic:123}];addData.medications=[];addData.intakes=[];addData.intakeEvents=[];
   const extra=await signed(addData);
   await preview(extra,'stale_checkpoint','accept');
   await checkpoint();
   await addRecord('pressures',{...p,id:'synpress_000003',systolic:127});
   await reload();
   el('import-button').click();
   await until(()=>(el('messages').textContent||'').includes('База изменилась'),'stale_abort');
   const final=await readBackupSnapshot();
   check('STALE_CHECKPOINT_REJECTED',final.pressures.length===2&&!final.pressures.some(r=>r.id==='synpress_000002'));
   check('PERSISTENT_OLD_RECORDS_UNCHANGED',final.medications.length===1&&final.intakes.length===1&&final.intakeEvents.length===1);
 }
 document.addEventListener('DOMContentLoaded',()=>{run().then(()=>finish(null),finish)});
})();

import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const app=fs.readFileSync('site/app.js','utf8');
const functionLine=app.split('\n').find(x=>x.startsWith('function connectStatus('));
assert.ok(functionLine,'connectStatus declaration missing');
const el={children:[],replaceChildren(...args){this.children=args}};
const context={$:id=>{assert.equal(id,'connection-status');return el},node:(tag,cls)=>({tag,cls}),document:{createTextNode:txt=>({text:String(txt)})}};
vm.createContext(context);
vm.runInContext(functionLine+'; globalThis.updateBadge=connectStatus;',context);
for(const [state,label,cls] of [['checking','Проверяем локальную базу','status-dot '],['ready','Локальная база доступна','status-dot online'],['error','Локальная база недоступна','status-dot offline']]){
 context.updateBadge(state);
 assert.equal(el.children[0].cls,cls);
 assert.equal(el.children[1].text,label);
 console.log('PASS LOCAL_DB_BADGE_'+state.toUpperCase());
}
assert.ok(!app.includes('navigator.onLine'));
assert.ok(!app.includes("addEventListener('online',connectStatus)"));
assert.ok(!app.includes("addEventListener('offline',connectStatus)"));
assert.ok(app.includes("await openDB();await reload();connectStatus('ready');"));
assert.ok(app.includes("}catch(e){connectStatus('error');showMessage("));
const sw=fs.readFileSync('site/sw.js','utf8'),off=fs.readFileSync('site/offline_status.js','utf8');
const cache='personal-v0612-localdbstatus-20261117';
assert.ok(sw.includes(cache)&&off.includes(cache));
assert.ok(sw.includes('cache:"reload"'));
console.log('PASS NO_NETWORK_CLAIM_AND_CACHE_MATCH');

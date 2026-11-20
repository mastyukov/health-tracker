'use strict';
/* PAE-04 CP-UI01. Synthetic-only home, existing DB and audit flow unchanged. */
(function () {
  if (typeof PAE04_V021_TEST_ONLY === 'undefined' || PAE04_V021_TEST_ONLY !== true) {
    throw Error('CP-UI01 is allowed only in a synthetic TEST candidate');
  }
  const FONT_KEY = 'pae04-cp-ui01-font-size-v1';
  const THEME_KEY = 'pae04-iphone-theme-v1';
  const COMPACT_KEY = 'pae04-iphone-compact-v1';
  const SCALES = [0.90, 0.96, 1, 1.14, 1.28];
  const TYPE_NAMES = {regular:'Постоянные',course:'Курсовые',asNeeded:'Ситуативные'};
  let scaleIndex=2;
  let dayLast='';
  let savingIds=new Set();
  const el=id=>document.getElementById(id);
  const element=(tag,cls,value)=>{
    const e=document.createElement(tag);
    if(cls)e.className=cls;
    if(value!==undefined)e.textContent=String(value);
    return e;
  };
  const localDate=d=>dateLocal(d);
  const priorDate=day=>{
    const parts=day.split('-').map(Number);
    return localDate(new Date(parts[0],parts[1]-1,parts[2]-1,12));
  };
  const humanDate=day=>new Intl.DateTimeFormat('ru-RU',{weekday:'long',day:'numeric',month:'long'}).format(new Date(day+'T12:00:00'));
  const activeIntake=i=>intakeStatus(i)==='active';
  function timesFor(medId,day) {
    return snapshot.intakes.filter(i=>i.medId===medId && i.date===day && activeIntake(i))
      .map(i=>i.takenAtLocal && i.takenAtLocal.startsWith(day+'T')?i.takenAtLocal.slice(11,16):null)
      .filter(Boolean).sort();
  }
  function readFont() {
    try {
      const raw=localStorage.getItem(FONT_KEY);
      if(raw!==null){
        const n=Number(raw);
        if(Number.isInteger(n)&&n>=0&&n<SCALES.length)scaleIndex=n;
      }
    } catch (_) { /* private browsing: retain working controls without persistence */ }
    applyFont();
  }
  function applyFont(){
    document.documentElement.style.setProperty('--ht-home-scale',String(SCALES[scaleIndex]));
    const indicator=el('ui01-font-label');
    if(indicator)indicator.textContent=String(scaleIndex+1)+' / '+SCALES.length;
    const less=el('ui01-font-less'),more=el('ui01-font-more');
    if(less)less.disabled=scaleIndex===0;
    if(more)more.disabled=scaleIndex===SCALES.length-1;
  }
  function applyDisplaySettings(){
    let theme='system',compact=true;
    try{theme=localStorage.getItem(THEME_KEY)||'system';compact=(localStorage.getItem(COMPACT_KEY)??'true')==='true';}catch(_){}
    if(!['system','light','dark'].includes(theme))theme='system';
    if(theme==='system')document.documentElement.removeAttribute('data-appearance');
    else document.documentElement.setAttribute('data-appearance',theme);
    document.documentElement.classList.toggle('compact-view',compact);
    const themeSelect=el('display-theme'),compactCheck=el('compact-view');
    if(themeSelect)themeSelect.value=theme;if(compactCheck)compactCheck.checked=compact;
  }
  function adjustFont(delta){
    scaleIndex=Math.max(0,Math.min(SCALES.length-1,scaleIndex+delta));
    try{localStorage.setItem(FONT_KEY,String(scaleIndex));}catch(_){}
    applyFont();
  }
  function drawPressure(day){
    const holder=el('ui01-pressure');if(!holder)return;
    holder.replaceChildren();
    const heading=element('h2','ui01-card-title','Последний замер');
    const icon=element('span','ui01-tonometer-icon');icon.innerHTML='<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="11" y="5" width="34" height="46" rx="7"/><rect x="17" y="12" width="22" height="17" rx="2"/><path d="M20 22h4l3-5 4 9 3-4h3"/><circle cx="28" cy="40" r="3"/><path d="M45 37c13-2 17 2 13 10l-3 5"/><rect x="43" y="51" width="17" height="8" rx="3"/></svg>';heading.prepend(icon);
    holder.append(heading);
    const all=[...snapshot.pressures].sort((a,b)=>b.dateTime.localeCompare(a.dateTime));
    const latest=all[0];
    const todayRows=all.filter(p=>p.dateTime.slice(0,10)===day);
    if(!latest){
      holder.append(element('p','ui01-empty','Измерений пока нет'));
    }else{
      const row=element('div','ui01-reading');
      row.append(element('strong','ui01-bp',String(latest.systolic)+' / '+String(latest.diastolic)),
        element('span','ui01-reading-meta',humanDate(latest.dateTime.slice(0,10))+' · '+latest.dateTime.slice(11,16)+' · '+(latest.pulse==null?'Пульс не указан':'Пульс '+latest.pulse)));
      holder.append(row);
    }
    const average=el('ui01-pressure-average');if(average){average.replaceChildren();average.hidden=todayRows.length<2;}
    if(todayRows.length>=2&&average){
      const mean=key=>Math.round(todayRows.reduce((a,p)=>a+p[key],0)/todayRows.length);
      const pulses=todayRows.filter(p=>Number.isFinite(p.pulse));
      average.append(element('h2','ui01-card-title','Среднее сегодня'));
      average.append(element('span','ui01-muted',`${todayRows.length} ${todayRows.length===1?'измерение':'измерения'}`));
      average.append(element('strong','ui01-yesterday-bp',`${mean('systolic')} / ${mean('diastolic')} мм рт. ст.`));
      if(pulses.length>=2)average.append(element('span','ui01-muted','Пульс в среднем: '+Math.round(pulses.reduce((a,p)=>a+p.pulse,0)/pulses.length)));
    }
    const add=element('button','primary ui01-wide-button','＋ Добавить измерение');
    add.type='button';
    add.addEventListener('click',()=>navigate('pressure'));
    holder.append(add);
  }
  function courseActive(m,day) {
    if(m.kind!=='course')return false;
    if(!m.from&&!m.to)return false; // Undated courses remain in full journal, not asserted as active.
    return (!m.from||day>=m.from)&&(!m.to||day<=m.to);
  }
  function onHomeIntake(m,button) {
    if(savingIds.has(m.id))return;
    const day=today();
    if(timesFor(m.id,day).length){navigate('meds');return;}
    if(m.kind==='course'&&!courseActive(m,day)){navigate('meds');return;}
    const time=clockLocal(new Date());
    if(!window.confirm('Подтвердить приём «'+m.name+'» сегодня в '+time+'?'))return;
    savingIds.add(m.id);button.disabled=true;
    const record={id:crypto.randomUUID(),medId:m.id,date:day,takenAtLocal:day+'T'+time,
      markedAt:new Date().toISOString(),status:'active'};
    Promise.resolve().then(()=>{
      validateIntake(record);
      return changeIntake('marked',record);
    }).then(async()=>{
      safetyNeedsNewCheck();
      await reload();
      showMessage('Приём отмечен в '+time+'. При необходимости исправьте время в журнале лекарств.');
    }).catch(err=>showMessage('Не удалось сохранить отметку: '+toError(err),'error'))
      .finally(()=>{savingIds.delete(m.id);button.disabled=false;drawHome();});
  }
  function medRow(m,day){
    const row=element('div','ui01-med-row');
    const current=snapshot.intakes.filter(i=>i.medId===m.id&&i.date===day&&activeIntake(i));
    const goal=m.kind==='asNeeded'?null:medDailyTarget(m);
    const desc=element('div','ui01-med-description');
    desc.append(element('strong','ui01-med-name',m.name));
    if(m.dose)desc.append(element('span','ui01-personal-dose',m.dose));
    if(m.kind==='asNeeded')desc.append(element('span','ui01-muted','По необходимости'));
    if(goal===null){
      const times=current.map(i=>i.takenAtLocal?.slice(11,16)).filter(Boolean).sort();
      if(times.length)desc.append(element('span','ui01-today-time','Сегодня: '+times.join(', ')));
      const btn=element('button','ui01-check'+(current.length?' is-taken':''),current.length?'✓':'');
      btn.type='button';btn.setAttribute('aria-label',current.length?'Открыть журнал приёмов '+m.name:'Записать фактический приём '+m.name);
      btn.addEventListener('click',()=>current.length?navigate('meds'):onHomeIntake(m,btn));row.append(btn,desc);return row;
    }
    const slots=medDailySlots(m,current),checks=element('div','ui01-home-slots');
    for(let n=1;n<=goal;n++){
      const taken=slots[n-1],label=element('label','ui01-home-slot'),box=element('input');
      box.type='checkbox';box.checked=!!taken;box.setAttribute('aria-label',`${m.name}: ${medSlotLabel(goal,n)}`);
      label.append(box,element('span','',medSlotLabel(goal,n)));checks.append(label);
      box.addEventListener('change',async()=>{
        box.disabled=true;
        try{
          if(taken){if(!window.confirm(`Отменить отметку «${medSlotLabel(goal,n)}» для ${m.name}? История сохранится.`)){box.checked=true;return;}
            const stamp=new Date().toISOString();await changeIntake('cancelled',{...taken,status:'cancelled',cancelledAt:stamp,updatedAt:stamp},taken);
          }else{
            const time=clockLocal(new Date()),takenAtLocal=day+'T'+time;
            if(snapshot.intakes.some(i=>i.medId===m.id&&i.takenAtLocal===takenAtLocal&&activeIntake(i)))throw Error('В это время уже есть отметка. Уточните время в журнале лекарств.');
            const record={id:crypto.randomUUID(),medId:m.id,date:day,takenAtLocal,markedAt:new Date().toISOString(),status:'active',dailySlot:n};
            validateIntake(record);await changeIntake('marked',record);
          }
          safetyNeedsNewCheck();await reload();
        }catch(err){box.checked=!!taken;showMessage('Отметка не изменена: '+toError(err),'error');}
        finally{box.disabled=false;}
      });
    }
    const legacy=current.filter(i=>!Number.isInteger(i.dailySlot)).length;
    if(legacy)desc.append(element('span','ui01-muted',`${legacy} старых ${legacy===1?'отметка':'отметок'} без назначенного слота`));
    row.append(desc,checks);
    return row;
  }
  function drawMeds(day,yday){
    const host=el('ui01-meds');if(!host)return;host.replaceChildren();
    host.append(element('h2','ui01-section-title','Лекарства сегодня'));
    let visible=0,scheduled=0,completed=0;
    for(const kind of ['regular','course','asNeeded']){
      const list=snapshot.medications.filter(m=>m.kind===kind&&(kind!=='course'||courseActive(m,day)))
        .sort((a,b)=>a.name.localeCompare(b.name,'ru'));
      if(!list.length)continue;
      visible++;
      const card=element('section','ui01-card ui01-med-group');
      const h=element('h3','ui01-group-title',TYPE_NAMES[kind]);
      const kindGlyph={regular:'∞',course:'▦',asNeeded:'ϟ'}[kind];
      h.prepend(element('span',`ui01-kind-icon kind-${kind}`,kindGlyph));
      card.append(h);
      for(const med of list){
        const actual=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day&&activeIntake(i));
        const goal=med.kind==='asNeeded'?null:medDailyTarget(med);if(goal!==null){scheduled+=goal;completed+=medDailySlots(med,actual).filter(Boolean).length;}
        card.append(medRow(med,day));
      }
      host.append(card);
    }
    if(!visible)host.append(element('p','ui01-empty','На сегодня лекарств нет. Добавьте препарат в разделе «Лекарства».'));
    if(scheduled){host.append(element('p','ui01-note',`Отмечено по расписанию: ${completed} из ${scheduled}. Ситуативные приёмы отдельно.`));}
    else if(visible){host.append(element('p','ui01-note','Расписание не задано. Пустая отметка не означает пропуск.'));}
  }
  function drawHome(){
    if(!el('ui01-pressure'))return;
    const day=today();
    dayLast=day;
    el('ui01-date').textContent=humanDate(day);
    drawPressure(day);
    drawMeds(day);
  }
  const originalOverview=renderOverview;
  renderOverview=function(){
    originalOverview();
    drawHome();
  };
  function setupPressurePeriods(){
    document.querySelectorAll('[data-period-target]').forEach(group=>{
      const target=el(group.dataset.periodTarget);
      if(!target)return;
      if(target.id==='pressure-list-period')target.value='all';
      const buttons=[...group.querySelectorAll('button[data-period]')];
      const sync=()=>buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.period===target.value)));
      buttons.forEach(b=>b.addEventListener('click',()=>{
        if(target.value!==b.dataset.period){
          target.value=b.dataset.period;
          target.dispatchEvent(new Event('change',{bubbles:true}));
        }
        sync();
      }));
      target.addEventListener('change',sync);
      sync();
    });
  }
  document.addEventListener('DOMContentLoaded',()=>{
    readFont();
    applyDisplaySettings();
    setupPressurePeriods();
    el('display-theme').addEventListener('change',e=>{try{localStorage.setItem(THEME_KEY,e.target.value)}catch(_){}applyDisplaySettings();});
    el('compact-view').addEventListener('change',e=>{try{localStorage.setItem(COMPACT_KEY,String(e.target.checked))}catch(_){}applyDisplaySettings();});
    el('ui01-font-less').addEventListener('click',()=>adjustFont(-1));
    el('ui01-font-more').addEventListener('click',()=>adjustFont(1));
    drawHome();
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)drawHome();});
    window.addEventListener('focus',drawHome);
    window.setInterval(()=>{if(today()!==dayLast)drawHome();},60000);
  });
  window.PAE04CPUI01={render:drawHome,priorDate,courseActive};
})();

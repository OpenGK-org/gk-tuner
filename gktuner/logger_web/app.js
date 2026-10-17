// CCP Studio dashboard frontend, adapted for GK Tuner native transport and appearance.
const $ = id => document.getElementById(id);
const MAX_VIEW_SECONDS = 60;
const palette = ['#1478a5','#c35d3c','#7562a9','#39856c','#bd4d6b','#6d8140','#976430','#4c8191','#8c6293','#667682'];
const darkPalette = ['#55c7ee','#fb9972','#baa1fb','#66d9ad','#fa93bc','#c1da76','#f5c175','#86d1e3','#d6a2e3','#adc2d7'];
const defaults = [
  ['RPM'], ['MAF_MEASURED','MAF_SELECTED'], ['MAP'], ['LOAD_FINAL'], ['TCO'], ['IGA_FINAL_AVG']
];
const friendly = {
  RPM:'Engine speed',TPS_V:'Throttle position voltage',TPS_POSITION_DEG:'Throttle position',TPS_ADC_COUNTS:'Throttle sensor ADC counts',TPS_ADC_WORD_RAW:'Throttle sensor ADC word',TPS_F4B5_RAW:'Legacy TPS byte - fixed/invalid',TCO:'Coolant temperature - ECU processed',TCO_SENSOR:'Coolant sensor - ECU processed',TCO_ST:'Coolant temperature - control',TIA:'Intake air temperature - ECU processed',TIA_SENSOR:'Intake air sensor - ECU processed',VBAT_RAW:'Battery voltage signal',
  IDLE_TCO_CORRECTION_LEARNING_STATE:'Idle coolant correction learning',TEMP_CORR_SOURCE_FAD2:'Idle coolant correction input',AIRMODEL_ADAPT_SAMPLE_C73A:'Upstream O2 raw ADC',O2_UPSTREAM:'Upstream O2 voltage',UNKNOWN_C766:'Downstream O2 raw ADC',O2_DOWNSTREAM:'Downstream O2 voltage',OPENTG_AFR:'OpenTG AFR',
  MAF_MEASURED:'Measured airflow',MAF_SELECTED:'Selected airflow',MAF_MODELED:'Modeled airflow',MAP:'Manifold pressure',
  CHARGE_DIRECT:'Direct cylinder charge',LOAD_VE_MODEL:'Modeled cylinder charge',LOAD_ALT:'Alternate cylinder charge',LOAD_FINAL:'Final cylinder charge',AMP_AD:'Ambient pressure',
  FD25:'Airflow status flags',FD45:'Airflow selection flags',FD46:'Load fallback flags',FD3A:'Load branch flags',
  MODEL_GRADIENT_LOAD_INPUT:'Model gradient load input',ENGINE_PERIOD_TCO_CORRECTION_BLEND:'Engine period coolant blend',ENGINE_PERIOD_OPERATING_CONDITION_FACTOR:'Engine period condition factor',MODEL_GRADIENT_COMBINED:'Combined model gradient',ER_PERIOD_NORM_CORR_EFFECTIVE:'Engine period normalization correction',
  TI_BASIC_COR:'Injection time - basic correction',TI_TOTAL_F966:'Injection time - total',TI_ADD_F96C:'Injection time - additive',INJECTOR_DUTY:'Injector duty cycle',VEHICLE_SPEED:'Vehicle speed',CAM_POSITION_DEG:'Intake cam position',CAM_TARGET_DEG:'Intake cam target',CAM_POSITION_RAW:'Legacy unverified IVVT word',CAM_TARGET_RAW:'Legacy IVVT controller reference',
  BOOST_STATUS_FLAGS:'Boost controller status flags',BOOST_MAP_MBAR:'Boost controller MAP',BOOST_EGT:'Boost controller EGT',BOOST_IAT:'Boost controller IAT',BOOST_MAX_BOOST_MBAR:'Boost controller maximum boost',
  TPS_SENSOR_V:'Legacy TPS voltage alias - coolant address',TPS:'Legacy TPS angle alias - coolant address',TOIL:'Invalid old oil reading - coolant address',VBAT:'Original battery voltage channel',VBAT_ADC:'Original battery ADC channel',
  WF_FAST_STATE_C936:'Fast wall-film state',WF_SLOW_STATE_C968:'Slow wall-film state',WF_STATE_C93C:'Wall-film runtime state',
  LAMBDA_CTRL_CC82:'Lambda control CC82',LAMBDA_CTRL_CC84:'Lambda control CC84',LAMBDA_CTRL_CCA2:'Lambda control CCA2',LAMBDA_ADAPT_ADD:'Lambda adaptation additive',LAMBDA_ADAPT_MUL:'Lambda adaptation multiplicative',
  AIRMODEL_ADAPT_COMBINED:'Combined air model adaptation',AIRMODEL_ADAPT_SLOW:'Slow air model adaptation',AIRMODEL_ADAPT_FAST:'Fast air model adaptation',AIRMODEL_ADAPT_LOW:'Low air model adaptation',AIRMODEL_ADAPT_HIGH:'High air model adaptation',
  IGA_REF_COR:'Reference ignition correction',IGA_BAS_COR:'Base ignition correction',KNK_AVG:'Average knock correction',
  KNOCK_SENSOR_ADC:'Knock sensor ADC counts',KNOCK_SENSOR_V:'Knock sensor voltage',
  EFF_IGA_BAS:'Base ignition efficiency',EFF_IGA_SP:'Setpoint ignition efficiency',EFF_IGA_FINAL:'Final ignition efficiency',
  IGA_DIF_TQ_REQ:'Torque request angle delta',IGA_TQ_REQ:'Torque request ignition angle',IGA_DIF_MIN:'Minimum angle delta',IGA_MIN:'Minimum ignition angle',IGA_FINAL_AVG:'Average final ignition angle',
  IGA_BAS_TEMP_CORR:'Base ignition temperature correction',IGA_REF_TEMP_CORR:'Reference ignition temperature correction',IGA_BAS_TEMP_CORR_FACTOR:'Base temperature correction factor',
  IGA_REF_BASE:'Reference base ignition angle',IGA_BAS_BASE:'Base map ignition angle',IGA_DIF_MIN_TCO_CORR:'Minimum angle coolant correction',IGA_TRA_KNK:'Transient knock correction',MODEL_GRADIENT_PRIMARY:'Primary model gradient',
  DIRECT_CHARGE_FROM_MAF_mg_stk:'Airflow-derived cylinder charge',LOAD_FINAL_MINUS_DIRECT_mg_stk:'Final charge difference',LOAD_FINAL_OVER_DIRECT_pct:'Final charge ratio',
  MAF_PULSATION_FD24_9:'Airflow pulsation active',USE_MEASURED_MAF_FD44_8:'Measured airflow selected',MAF_FALLBACK_FD46_5:'Airflow fallback active'
};
const label = name => {
  const base=name.replace(/_raw$/,'');
  if(friendly[base])return friendly[base];
  if(/^KNK_CYL[1-4]$/.test(base))return `Cylinder ${base.slice(-1)} knock correction`;
  if(/^KNOCK_V_CYL[1-4]$/.test(base))return `Cylinder ${base.slice(-1)} knock voltage`;
  if(/^KNOCK_THRESHOLD_CYL[1-4]$/.test(base))return `Cylinder ${base.slice(-1)} knock threshold`;
  if(/^IGA_FINAL_CYL[1-4]$/.test(base))return `Cylinder ${base.slice(-1)} final ignition angle`;
  return base.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
};
const state = {meta:null,selected:new Set(),fields:[],rows:[],graphs:[],graphsLoaded:false,name:'',source:'sample',status:'idle',sessionMode:'record',dataMode:'record',monitorSupported:false,next:0,baseIndex:0,dataVersion:0,followLive:false,view:null,cursor:null,drag:null,modalIndex:null,modalSelected:new Set(),modalAxes:{},modalColors:{},raf:0};
const fmt = (v,d=1) => v==null || !Number.isFinite(+v) ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const num = v => {if(v==null||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null};
const duration = s => `${String(Math.floor(s/60)).padStart(2,'0')}:${(s%60).toFixed(1).padStart(4,'0')}`;
const tField = () => state.fields.includes('t_s')?'t_s':state.fields.find(x=>/^(time|timestamp|t)$/i.test(x));
const tAt = i => tField() ? num(state.rows[i]?.[tField()]) ?? i : i;
const range = () => state.rows.length?[tAt(0),tAt(state.rows.length-1)]:[0,1];
const signalInfo = column => state.meta?.signals.find(s=>s.column===column);
const unitFor = column => signalInfo(column)?.unit || (/_mg_stk$/i.test(column)?'mg/stk':/_pct$/i.test(column)?'%':'raw');
const lineColor = (graph,signal,index) => /^#[0-9a-f]{6}$/i.test(graph.colors?.[signal]||'')?graph.colors[signal]:(document.documentElement.dataset.theme==='dark'?darkPalette:palette)[index%palette.length];
const legacyColumns = {
  TPS_ACTUAL:['TPS_F4B5_RAW',v=>Math.round(v/.4686274509803922)]
};
const retiredOilColumns={TOIL:'TCO_SENSOR',TOIL_raw:'TCO_SENSOR_raw'};
const temperatureColumns=new Set(['TCO','TCO_SENSOR','TCO_ST','TIA','TIA_SENSOR']);
const restoredTiColumns={MODEL_GRADIENT_LOAD_INPUT_raw:'TI_BASIC_COR',ENGINE_PERIOD_TCO_CORRECTION_BLEND_raw:'TI_TOTAL_F966',ENGINE_PERIOD_OPERATING_CONDITION_FACTOR_raw:'TI_ADD_F96C'};
const legacySignalNames={...retiredOilColumns,...Object.fromEntries(Object.entries(legacyColumns).map(([old,[corrected]])=>[old.replace(/_raw$/,''),corrected.replace(/_raw$/,'')]))};
function normalizeLegacy(fields,rows){
  const versioned=fields.includes('TEMP_SCALE_VERSION')&&Number(rows[0]?.TEMP_SCALE_VERSION)===2;
  const oldTemperatures=!versioned&&fields.some(f=>temperatureColumns.has(f));
  const rename=fields.some(f=>legacyColumns[f]);
  const oldOil=fields.some(f=>retiredOilColumns[f]);
  if(!fields.includes('TEMP_SCALE_VERSION')&&!oldTemperatures&&!rename&&!oldOil)return {fields,rows};
  const convertedFields=[...new Set(fields.filter(f=>f!=='TEMP_SCALE_VERSION').map(f=>retiredOilColumns[f]||legacyColumns[f]?.[0]||f))];
  for(const row of rows){
    delete row.TEMP_SCALE_VERSION;
    for(const field of fields){
      if(oldTemperatures&&temperatureColumns.has(field)&&row[field]!=null)row[field]=row[field]*.75-18;
      const rule=legacyColumns[field];
      if(rule){row[rule[0]]=row[field]==null?row[field]:rule[1](row[field]);delete row[field]}
    }
    for(const [old,replacement] of Object.entries(retiredOilColumns)){
      if(!fields.includes(old))continue;
      if(!fields.includes(replacement))row[replacement]=old==='TOIL'&&row[old]!=null?row[old]*.75-18:row[old];
      delete row[old];
    }
  }
  return {fields:convertedFields,rows};
}
function addTuningFields(fields,rows){
  if(fields.includes('TPS_V')&&!fields.includes('TPS_POSITION_DEG')){
    fields.push('TPS_POSITION_DEG');
    for(const row of rows){const v=num(row.TPS_V);row.TPS_POSITION_DEG=v==null?null:Math.max(0,Math.min(90,(v-.34)*90/(4.35-.34)))}
  }
  if(fields.includes('RPM')&&fields.includes('TI_TOTAL_F966')&&!fields.includes('INJECTOR_DUTY')){
    fields.push('INJECTOR_DUTY');
    for(const row of rows){const rpm=num(row.RPM),pulse=num(row.TI_TOTAL_F966);row.INJECTOR_DUTY=rpm==null||pulse==null?null:pulse*rpm/1200}
  }
  return {fields,rows};
}

function savePrefs(){nativeBridge.savePreferences(JSON.stringify({version:4,selected:[...state.selected],graphs:state.graphs,connection:{channel:$('channel').value,bitrate:$('bitrate').value,rate:$('rate').value},sessionMode:state.sessionMode}));}
function loadPrefs(){try{
  const pref=JSON.parse(nativeBridge.preferences||'{}');
  for(const key of ['channel','bitrate','rate'])if(pref.connection && pref.connection[key]!=null)$(key).value=pref.connection[key];
  if(pref.sessionMode==='monitor')state.sessionMode='monitor';
  if(Array.isArray(pref.selected))pref.selected=pref.selected.map(s=>{const name=legacySignalNames[s]||s;return (pref.version||0)<2&&name==='TPS_F4B5_RAW'?'TPS_V':name});
  if(Array.isArray(pref.selected)&&(pref.version||0)<3){
    for(const [current,original] of [['MODEL_GRADIENT_LOAD_INPUT','TI_BASIC_COR'],['ENGINE_PERIOD_TCO_CORRECTION_BLEND','TI_TOTAL_F966'],['ENGINE_PERIOD_OPERATING_CONDITION_FACTOR','TI_ADD_F96C']]){
      if(pref.selected.includes(current)&&!pref.selected.includes(original))pref.selected.push(original);
    }
  }
  if(Array.isArray(pref.graphs))pref.graphs=pref.graphs.map(g=>{
    const signals=Array.isArray(g)?g:g.signals;
    const restore=s=>(pref.version||0)<3&&restoredTiColumns[s]||retiredOilColumns[s]||legacyColumns[s]?.[0]||s;
    if(!Array.isArray(signals)||!signals.some(s=>restore(s)!==s))return g;
    const migrated=signals.map(restore);
    if(Array.isArray(g))return migrated;
    return {...g,signals:[...new Set(migrated)],colors:Object.fromEntries(Object.entries(g.colors||{}).map(([s,c])=>[restore(s),c]))};
  });
  return pref;
}catch{return {}}}
function odtCount(names){
  const unique=new Map();
  for(const name of names){const signal=state.meta.signals.find(s=>s.name===name);if(!signal)continue;
    for(const needed of [signal,...(signal.depends_on||[]).map(n=>state.meta.signals.find(s=>s.name===n)).filter(Boolean)]){
      if(needed.source==='can')continue;
      unique.set(needed.address==null?needed.name:`${needed.address}:${needed.size}:${needed.signed}`,needed.size);
    }
  }
  const sizes=[...unique.values()].sort((a,b)=>b-a),bins=[];
  for(const size of sizes){let i=bins.findIndex(x=>x+size<=7);if(i<0)bins.push(size);else bins[i]+=size}
  return bins.length;
}
function renderSignalList(){
  const q=$('signal-search').value.toLowerCase().trim(),list=$('signal-list');list.textContent='';
  for(const s of state.meta.signals){
    if(q&&!`${label(s.name)} ${s.name} ${s.note} ${s.unit}`.toLowerCase().includes(q))continue;
    const row=document.createElement('label');row.className='signal-item';row.title=s.note||s.name;
    const cb=document.createElement('input');cb.type='checkbox';cb.checked=state.selected.has(s.name);
    cb.onchange=()=>{cb.checked?state.selected.add(s.name):state.selected.delete(s.name);updateCapacity();savePrefs()};
    const name=document.createElement('span');name.className='signal-name';
    const primary=document.createElement('strong');primary.textContent=label(s.name);
    const code=document.createElement('small');code.textContent=s.name;
    name.append(primary,code);
    const unit=document.createElement('span');unit.className='unit';unit.textContent=s.unit||'raw';
    row.append(cb,name,unit);list.append(row);
  }
  updateCapacity();
}
function updateCapacity(){
  const used=odtCount([...state.selected]),over=used>12,boostOnly=state.selected.size>0&&used===0;
  $('selected-count').textContent=`${state.selected.size} selected`;
  $('capacity-label').textContent=`${used} / 12 ODTs`;
  $('capacity-bar').style.width=`${Math.min(100,used/12*100)}%`;
  $('capacity-bar').classList.toggle('over',over);
  $('capacity-hint').textContent=over?'Reduce the selection to fit the ECU’s 12 ODT limit.':boostOnly?'CAN broadcast - no ECU connection needed':`${state.selected.size} signals - ${state.selected.size?12-used+' ODTs available':'select signals to record'}`;
  $('rate').disabled=boostOnly;
  $('capture-button').disabled=over||!state.selected.size;
}
function setupGraphs(){
  const pref=loadPrefs();
  state.graphs=(Array.isArray(pref.graphs)?pref.graphs:defaults).slice(0,8).map(g=>{
    if(Array.isArray(g))return {signals:g.slice(0,10),height:180,axes:{},colors:{}};
    return {signals:Array.isArray(g.signals)?g.signals.slice(0,10):[],height:Math.max(120,Math.min(560,Number(g.height)||180)),axes:g.axes&&typeof g.axes==='object'?g.axes:{},colors:g.colors&&typeof g.colors==='object'?g.colors:{}};
  });
  state.graphsLoaded=true;
  renderGraphs();
}
function setData(fields,rows,name,source){
  state.fields=fields;state.rows=rows;state.name=name;state.source=source;state.dataMode=state.sessionMode;state.view=null;state.cursor=null;state.next=rows.length;state.baseIndex=0;state.dataVersion++;state.followLive=source==='live';
  if(!state.graphsLoaded)setupGraphs();else renderGraphs();
  $('dataset-name').textContent=name;
  $('sample-button').classList.toggle('active',source==='sample');
  $('sample-check').textContent=source==='sample'?'✓':'';
  updateMetrics();renderLiveValues();updateLiveUI();scheduleDraw();
}
function updateMetrics(){
  const [a,b]=range(),n=state.rows.length,span=n>1?Math.max(0,b-a):0;
  $('metric-span-label').textContent=state.source==='live'&&state.dataMode==='monitor'?'Window':'Duration';
  $('metric-duration').textContent=duration(span);
  $('metric-samples').textContent=n.toLocaleString();
  $('metric-rate').textContent=n>1&&span>0?`${fmt((n-1)/span,1)} Hz`:'—';
  $('metric-signals').textContent=state.fields.filter(f=>f!==tField()&&!['cycle','dto_frames'].includes(f)).length;
  $('metric-session-detail').textContent=state.source==='live'?(state.dataMode==='monitor'?'Rolling 30 seconds':state.status==='recording'?'Capture in progress':'Live capture'):'Loaded capture';
  $('timeline-range').textContent=`${fmt(a,2)}s – ${fmt(b,2)}s`;
  $('metric-samples-detail').textContent=state.source==='live'?(state.fields.slice(1).every(f=>f.startsWith('BOOST_'))?'Boost controller frames':'Complete DAQ cycles'):'Recorded data points';
  $('metric-signals-detail').textContent='Available in this dataset';
}
function renderLiveValues(){
  const panel=$('live-values');panel.textContent='';
  if(state.source!=='live'||state.dataMode!=='monitor')return;
  for(const signal of state.fields.filter(f=>f!==tField()&&!['cycle','dto_frames'].includes(f))){
    const item=document.createElement('div');item.className='live-value';
    const name=document.createElement('span');name.textContent=label(signal);
    const reading=document.createElement('strong');reading.dataset.signal=signal;reading.textContent='—';
    const unit=document.createElement('small');unit.textContent=unitFor(signal)==='raw'?'':unitFor(signal);
    item.append(name,reading,unit);panel.append(item);
  }
  updateLiveValues();
}
function updateLiveValues(){
  const row=state.rows[state.rows.length-1];
  $('live-values').querySelectorAll('[data-signal]').forEach(el=>{
    const value=num(row?.[el.dataset.signal]);
    el.textContent=fmt(value,Math.abs(value||0)<10?2:1);
  });
}
function renderGraphs(){
  const root=$('charts');root.textContent='';$('graph-count').textContent=`${state.graphs.length} / 8`;
  $('add-graph').disabled=state.graphs.length>=8;$('add-graph-bottom').disabled=state.graphs.length>=8;
  state.graphs.forEach((graph,i)=>{
    const signals=graph.signals;
    const card=document.createElement('div');card.className='chart-card';
    const top=document.createElement('div');top.className='chart-top';
    const left=document.createElement('div');
    const title=document.createElement('div');title.className='chart-title';
    const idx=document.createElement('span');idx.className='chart-index';idx.textContent=String(i+1).padStart(2,'0');
    title.append(idx,document.createTextNode(signals.length?`${label(signals[0])} - ${unitFor(signals[0])}`:'Empty graph'));
    const sub=document.createElement('div');sub.className='chart-sub';
    sub.textContent=signals.length>1?`${signals.length} channels`:'';
    left.append(title,sub);
    const actions=document.createElement('div');actions.className='chart-actions';
    const edit=document.createElement('button');edit.textContent='⚙';edit.title='Choose plotted signals';edit.onclick=()=>openModal(i);
    const remove=document.createElement('button');remove.textContent='×';remove.title='Remove graph';remove.onclick=()=>{state.graphs.splice(i,1);renderGraphs();savePrefs()};
    actions.append(edit,remove);top.append(left,actions);
    const wrap=document.createElement('div');wrap.className='chart-wrap';wrap.style.height=`${graph.height}px`;
    const canvas=document.createElement('canvas');
    const tooltip=document.createElement('div');tooltip.className='value-tooltip';tooltip.hidden=true;
    wrap.append(canvas,tooltip);
    wrap.addEventListener('mousemove',e=>chartMove(e,canvas));wrap.addEventListener('mouseleave',()=>{if(!state.drag){state.cursor=null;scheduleDraw()}});
    wrap.addEventListener('mousedown',e=>{if(e.button!==0)return;state.drag={x:e.clientX,view:[...view()],width:canvas.getBoundingClientRect().width};wrap.style.cursor='grabbing'});
    wrap.addEventListener('mouseup',()=>{state.drag=null;wrap.style.cursor='crosshair'});
    wrap.addEventListener('wheel',e=>{e.preventDefault();const box=canvas.getBoundingClientRect();zoom(e.deltaY<0?.78:1.28,timeFromX(e.clientX-box.left,box.width))},{passive:false});
    wrap.addEventListener('dblclick',()=>{state.view=null;scheduleDraw()});
    const legend=document.createElement('div');legend.className='legend';
    signals.forEach((s,j)=>{
      const item=document.createElement('div');item.className='legend-item';
      const dot=document.createElement('span');dot.className='legend-dot';dot.style.background=lineColor(graph,s,j);
      const name=document.createElement('span');name.textContent=label(s);
      const value=document.createElement('strong');value.dataset.signal=s;value.textContent='—';
      item.append(dot,name,value);legend.append(item);
    });
    const resize=document.createElement('div');resize.className='resize-handle';resize.title='Drag to resize graph height';resize.tabIndex=0;resize.setAttribute('role','separator');resize.setAttribute('aria-label',`Resize graph ${i+1}`);resize.setAttribute('aria-orientation','horizontal');resize.setAttribute('aria-valuemin','120');resize.setAttribute('aria-valuemax','560');resize.setAttribute('aria-valuenow',String(graph.height));
    resize.innerHTML='<span></span>';
    resize.addEventListener('keydown',e=>{if(!['ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();graph.height=Math.max(120,Math.min(560,graph.height+(e.key==='ArrowDown'?20:-20)));wrap.style.height=`${graph.height}px`;resize.setAttribute('aria-valuenow',String(graph.height));scheduleDraw();savePrefs()});
    resize.addEventListener('pointerdown',e=>{e.preventDefault();resize.setPointerCapture(e.pointerId);const startY=e.clientY,startHeight=graph.height;
      const move=event=>{graph.height=Math.max(120,Math.min(560,startHeight+event.clientY-startY));wrap.style.height=`${graph.height}px`;resize.setAttribute('aria-valuenow',String(graph.height));scheduleDraw()};
      const done=()=>{resize.removeEventListener('pointermove',move);resize.removeEventListener('pointerup',done);resize.removeEventListener('pointercancel',done);savePrefs()};
      resize.addEventListener('pointermove',move);resize.addEventListener('pointerup',done);resize.addEventListener('pointercancel',done)
    });
    card.append(top,wrap,legend,resize);root.append(card);
  });scheduleDraw();
}
function liveView(){const [first,last]=range(),start=Math.max(first,last-30);return [start,Math.max(start+30,last)]}
function timeBounds(){const [first,last]=range();return [state.source==='live'?first:Math.min(0,first),last]}
function fitView(){const [first,last]=timeBounds();return state.source==='live'?[Math.max(first,last-MAX_VIEW_SECONDS),Math.max(first+.01,last)]:[first,Math.min(last,first+MAX_VIEW_SECONDS)]}
function view(){return state.source==='live'&&state.followLive?liveView():state.view||fitView()}
function timeFromX(x,width){const [a,b]=view();return a+Math.max(0,Math.min(1,(x-52)/Math.max(1,width-67)))*(b-a)}
function chartMove(e,canvas){
  const box=canvas.getBoundingClientRect();
  if(state.drag){const span=state.drag.view[1]-state.drag.view[0];const dx=(e.clientX-state.drag.x)/Math.max(1,state.drag.width-67)*span;setView(state.drag.view[0]-dx,state.drag.view[1]-dx)}
  state.cursor=state.rows.length?tAt(nearestIndex(timeFromX(e.clientX-box.left,box.width))):null;scheduleDraw();
}
window.addEventListener('mouseup',()=>{state.drag=null;document.querySelectorAll('.chart-wrap').forEach(x=>x.style.cursor='crosshair')});
function setView(a,b){
  state.followLive=false;updateLiveUI();
  const [lo,hi]=timeBounds(),total=Math.max(.01,hi-lo),limit=Math.min(MAX_VIEW_SECONDS,total),span=Math.max(Math.min(limit,.04),Math.min(limit,b-a));
  a=Math.max(lo,Math.min(hi-span,a));state.view=[a,a+span];scheduleDraw();
}
function zoom(factor,center){const [a,b]=view(),[lo,hi]=timeBounds(),maxSpan=Math.min(MAX_VIEW_SECONDS,Math.max(.01,hi-lo));if(factor>1&&b-a>=maxSpan-1e-9)return;center=center??(a+b)/2;setView(center-(center-a)*factor,center+(b-center)*factor)}
function nearestIndex(t){let lo=0,hi=state.rows.length-1;while(lo<hi){const m=(lo+hi)>>1;if(tAt(m)<t)lo=m+1;else hi=m}return lo>0&&Math.abs(tAt(lo-1)-t)<Math.abs(tAt(lo)-t)?lo-1:lo}
function scheduleDraw(){if(!state.raf)state.raf=requestAnimationFrame(()=>{state.raf=0;drawAll()})}
function drawAll(){
  const charts=$('charts').children;
  for(let i=0;i<charts.length;i++)drawChart(charts[i],state.graphs[i]);
  const [a,b]=view();$('timeline-range').textContent=`${fmt(a,2)}s – ${fmt(b,2)}s${state.followLive?' - live':state.view?' - zoomed':''}`;
  $('cursor-time').textContent=state.cursor==null?'—':`${fmt(state.cursor,3)} s`;
  updateTimeScrollbar(a,b);
}
function updateTimeScrollbar(a,b){
  const [first,last]=timeBounds(),travel=Math.max(0,last-first-(b-a)),bar=$('time-scrollbar');
  bar.hidden=travel<.01;
  if(bar.hidden)return;
  $('time-scroll-start').textContent=`${fmt(first,1)}s`;
  $('time-scroll-end').textContent=`${fmt(last,1)}s`;
  $('time-scroll').value=String(Math.round((a-first)/travel*10000));
}
function niceStep(span,target){const raw=span/target,p=Math.pow(10,Math.floor(Math.log10(raw||1)));return [1,2,5,10].map(v=>v*p).find(v=>v>=raw)||10*p}
function drawChart(card,graph){
  const signals=graph.signals;
  const canvas=card.querySelector('canvas'),box=canvas.getBoundingClientRect(),w=Math.max(100,box.width),h=Math.max(100,box.height),dpr=window.devicePixelRatio||1;
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
  const c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
  const L=52,R=w-15,T=10,B=h-25,[a,b]=view(),span=Math.max(.001,b-a);
  const x=t=>L+(t-a)/span*(R-L);
  const baseKey=JSON.stringify([state.dataVersion,a,b,w,h,dpr,signals,graph.axes,graph.colors]);
  let y=card._baseY;
  if(card._baseKey!==baseKey){
  let start=nearestIndex(a),end=nearestIndex(b);start=Math.max(0,start-1);end=Math.min(state.rows.length-1,end+1);
  const groups=new Map(),groupFor=unitFor;
  for(const s of signals)groups.set(groupFor(s),{min:Infinity,max:-Infinity});
  for(let i=start;i<=end;i++)for(const s of signals){const v=num(state.rows[i]?.[s]);if(v==null)continue;const g=groups.get(groupFor(s));g.min=Math.min(g.min,v);g.max=Math.max(g.max,v)}
  for(const [unit,g] of groups){
    if(!Number.isFinite(g.min)){g.min=0;g.max=1}
    const pad=Math.max((g.max-g.min)*.11,Math.abs(g.max)*.025,.05);
    g.min-=pad;g.max+=pad;
    const saved=graph.axes?.[unit];
    if(Number.isFinite(saved?.min))g.min=saved.min;
    if(Number.isFinite(saved?.max))g.max=saved.max;
    if(g.max<=g.min)g.max=g.min+1;
  }
  const primary=groups.values().next().value||{min:0,max:1},min=primary.min,max=primary.max;
  y=(s,v)=>{const g=groups.get(groupFor(s))||primary;return B-(v-g.min)/(g.max-g.min)*(B-T)};
  c.font='10px Segoe UI, sans-serif';c.lineWidth=1;c.textBaseline='middle';
  const ys=niceStep(max-min,3);
  for(let val=Math.ceil(min/ys)*ys;val<=max;val+=ys){const yy=B-(val-min)/(max-min)*(B-T);c.strokeStyle=customPalette.border||(document.documentElement.dataset.theme==='dark'?'#3a4859':'#e6ebee');c.beginPath();c.moveTo(L,yy);c.lineTo(R,yy);c.stroke();c.fillStyle=customPalette.text||(document.documentElement.dataset.theme==='dark'?'#acbbc9':'#73818a');c.textAlign='right';c.fillText(fmt(val,Math.abs(ys)<1?2:1),L-9,yy)}
  const ts=niceStep(span,7);
  for(let t=Math.ceil(a/ts)*ts;t<=b;t+=ts){const xx=x(t);c.strokeStyle=customPalette.border||(document.documentElement.dataset.theme==='dark'?'#303d4e':'#eef1f3');c.beginPath();c.moveTo(xx,T);c.lineTo(xx,B);c.stroke();c.fillStyle=customPalette.text||(document.documentElement.dataset.theme==='dark'?'#acbbc9':'#73818a');c.textAlign='center';c.textBaseline='top';c.fillText(`${fmt(t,ts<1?2:1)}s`,xx,B+7)}
  c.save();c.beginPath();c.rect(L,T,R-L,B-T);c.clip();
  for(let j=0;j<signals.length;j++){
    c.strokeStyle=lineColor(graph,signals[j],j);c.lineWidth=1.8;c.lineJoin='round';c.lineCap='round';c.beginPath();let active=false;
    const bucket=Math.max(1,Math.ceil((end-start+1)/Math.max(1,R-L)));
    for(let i=start;i<=end;i+=bucket){
      let first=-1,last=-1,minI=-1,maxI=-1,minV=Infinity,maxV=-Infinity,gap=false;
      for(let k=i;k<=Math.min(end,i+bucket-1);k++){
        const v=num(state.rows[k]?.[signals[j]]);
        if(v==null){gap=true;continue}
        if(first<0)first=k;
        last=k;
        if(v<minV){minV=v;minI=k}
        if(v>maxV){maxV=v;maxI=k}
      }
      if(first<0){active=false;continue}
      const indices=[first,minI,maxI,last].sort((u,v)=>u-v);
      for(const k of indices){if(k===indices[0]&&!active){c.moveTo(x(tAt(k)),y(signals[j],num(state.rows[k][signals[j]])));active=true}else c.lineTo(x(tAt(k)),y(signals[j],num(state.rows[k][signals[j]])))}
      if(gap)active=false;
    }
    c.stroke();
  }
  c.restore();
  const base=card._baseCanvas||document.createElement('canvas');
  if(base.width!==canvas.width||base.height!==canvas.height){base.width=canvas.width;base.height=canvas.height}
  const baseContext=base.getContext('2d');baseContext.clearRect(0,0,base.width,base.height);baseContext.drawImage(canvas,0,0);
  card._baseCanvas=base;card._baseKey=baseKey;card._baseY=y;
  }else c.drawImage(card._baseCanvas,0,0,w,h);
  c.save();c.beginPath();c.rect(L,T,R-L,B-T);c.clip();
  if(state.cursor!=null&&state.cursor>=a&&state.cursor<=b){const xx=x(state.cursor);c.strokeStyle='#667986';c.setLineDash([4,4]);c.lineWidth=1;c.beginPath();c.moveTo(xx,T);c.lineTo(xx,B);c.stroke();c.setLineDash([]);const row=state.rows[nearestIndex(state.cursor)];
    for(let j=0;j<signals.length;j++){const v=num(row?.[signals[j]]);if(v==null)continue;c.fillStyle=lineColor(graph,signals[j],j);c.beginPath();c.arc(xx,y(signals[j],v),4,0,Math.PI*2);c.fill();c.strokeStyle='#fff';c.lineWidth=1.5;c.stroke()}
  }
  c.restore();
  const row=state.rows[nearestIndex(state.cursor==null?b:state.cursor)];
  card.querySelectorAll('[data-signal]').forEach(el=>{const s=el.dataset.signal,v=num(row?.[s]),unit=unitFor(s);el.textContent=`${fmt(v,Math.abs(v||0)<10?2:1)}${unit==='raw'?'':' '+unit}`});
  const tooltip=card.querySelector('.value-tooltip');
  tooltip.hidden=state.cursor==null||!row||!signals.length;
  if(!tooltip.hidden){
    tooltip.textContent='';
    const head=document.createElement('div');head.className='value-tooltip-head';head.textContent=`RECORDED AT ${fmt(tAt(nearestIndex(state.cursor)),6)} s`;
    tooltip.append(head);
    const list=document.createElement('div');list.className='value-tooltip-list';
    if(signals.length>5)list.classList.add('two-column');
    signals.forEach((s,j)=>{
      const item=document.createElement('div');item.className='value-tooltip-item';
      const dot=document.createElement('i');dot.style.background=lineColor(graph,s,j);
      const name=document.createElement('span');name.textContent=label(s);
      const value=document.createElement('strong');const v=num(row[s]),unit=unitFor(s);
      value.textContent=`${fmt(v,4)}${unit==='raw'?'':' '+unit}`;
      item.append(dot,name,value);list.append(item);
    });
    tooltip.append(list);
    const xx=x(state.cursor),width=tooltip.offsetWidth;
    tooltip.style.left=`${Math.max(55,Math.min(w-width-6,xx+12))}px`;
  }
}
function openModal(index){state.modalIndex=index;state.modalSelected=new Set(state.graphs[index].signals);state.modalAxes=JSON.parse(JSON.stringify(state.graphs[index].axes||{}));state.modalColors={...(state.graphs[index].colors||{})};$('plot-search').value='';$('plot-modal').hidden=false;renderModal();$('plot-search').focus()}
function renderModal(){const q=$('plot-search').value.toLowerCase(),list=$('modal-list');list.textContent='';
  for(const name of new Set([...state.fields,...state.modalSelected])){if(name===tField()||['cycle','dto_frames'].includes(name)||!`${label(name)} ${name} ${signalInfo(name)?.note||''}`.toLowerCase().includes(q))continue;
    const row=document.createElement('div');row.className='modal-item';const option=document.createElement('label');option.className='modal-option';const box=document.createElement('input');box.type='checkbox';box.checked=state.modalSelected.has(name);box.disabled=!box.checked&&state.modalSelected.size>=10;
    box.onchange=()=>{box.checked?state.modalSelected.add(name):state.modalSelected.delete(name);renderModal()};
    const text=document.createElement('span');text.className='modal-signal-name';
    const strong=document.createElement('strong');strong.textContent=label(name);const code=document.createElement('small');code.textContent=state.fields.includes(name)?name:`${name} - not in this CSV`;
    text.append(strong,code);const unit=document.createElement('small');unit.className='modal-unit';unit.textContent=unitFor(name);option.append(box,text,unit);
    const colour=document.createElement('input');colour.type='color';colour.className='line-colour';colour.value=state.modalColors[name]||lineColor(state.graphs[state.modalIndex],name,Math.max(0,[...state.modalSelected].indexOf(name)));colour.title=`Line colour for ${label(name)}`;colour.setAttribute('aria-label',`Line colour for ${label(name)}`);colour.disabled=!box.checked;colour.oninput=()=>{state.modalColors[name]=colour.value};
    row.append(option,colour);list.append(row)
  }$('modal-selection').textContent=`${state.modalSelected.size} / 10 selected`;renderAxes();
}
function validateAxes(){
  let error='';
  for(const unit of new Set([...state.modalSelected].map(unitFor))){
    const axis=state.modalAxes[unit]||{};
    if(['min','max'].some(key=>axis[key]!=null&&!Number.isFinite(axis[key]))){error=`${unit}: enter a valid number.`;break}
    if(axis.min!=null&&axis.max!=null&&axis.min>=axis.max){error=`${unit}: minimum must be below maximum.`;break}
  }
  $('axis-error').textContent=error;$('axis-error').hidden=!error;
  $('modal-save').disabled=!state.modalSelected.size||!!error;
}
function renderAxes(){
  const root=$('axis-settings');root.textContent='';
  const units=[...new Set([...state.modalSelected].map(unitFor))];
  units.forEach((unit,index)=>{
    const row=document.createElement('div');row.className='axis-row';
    const title=document.createElement('span');title.className='axis-unit';title.textContent=unit==='raw'?'Raw value':unit;
    if(index===0)title.title='The left Y axis uses this unit';
    row.append(title);
    for(const key of ['min','max']){
      const input=document.createElement('input');input.type='number';input.step='any';input.placeholder=key==='min'?'Auto min':'Auto max';
      input.setAttribute('aria-label',`${unit} ${key}imum`);
      const current=state.modalAxes[unit]?.[key];input.value=current==null?'':String(current);
      input.oninput=()=>{if(!state.modalAxes[unit])state.modalAxes[unit]={};state.modalAxes[unit][key]=input.value===''?null:Number(input.value);validateAxes()};
      row.append(input);
    }
    root.append(row);
  });
  validateAxes();
}
function showNotice(message){$('notice').textContent=message;$('notice').hidden=!message}
let nativeBridge;
let customPalette={};
function applyPalette(raw){
  try{customPalette=JSON.parse(raw)||{}}catch(e){customPalette={}}
  const rules=[];
  const rule=(role,selectors,property)=>{const value=customPalette[role];if(/^#[0-9a-f]{6}$/i.test(value||''))rules.push(`${selectors}{${property}:${value}!important}`)};
  rule('background','html,body,.main,.sidebar,.sidebar-bottom','background');
  rule('surface','.topbar,.charts,.chart-wrap,.chart-card,.metrics,.modal,.search-wrap,.modal-search,input,select,button','background');
  rule('text','body,button,input,select,.view-name,.chart-title,.signal-name strong','color');
  rule('muted','.section-label,.unit,.signal-name small,.capacity-hint,.settings label','color');
  rule('border','.sidebar,.topbar,.chart-card,.modal,.search-wrap,.modal-search,input,select,button','border-color');
  rule('accent','.source.active,.session-mode button.active,.capture-button,.primary','background');
  rule('selection','.signal-item.selected','background');
  rule('hover','button:hover:not(:disabled)','background');
  rule('accent','input[type="checkbox"]','accent-color');
  rule('accent','.time-scrollbar input[type="range"]::-webkit-slider-runnable-track,.time-scrollbar input[type="range"]::-webkit-slider-thumb','background');
  if(customPalette.accent){const v=customPalette.accent;const rgb=[1,3,5].map(i=>parseInt(v.slice(i,i+2),16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);const lum=rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;rules.push(`.source.active,.session-mode button.active,.capture-button,.primary{color:${lum>.179?'#102235':'#ffffff'}!important}`)}
  let style=document.getElementById('custom-palette');
  if(!style){style=document.createElement('style');style.id='custom-palette';document.head.appendChild(style)}
  style.textContent=rules.join('\n');
  document.querySelectorAll('.chart-card').forEach(card=>card._baseKey=null);
  state.dataVersion++;scheduleDraw();
}
async function api(path,body){
  return new Promise((resolve,reject)=>nativeBridge.request(path,JSON.stringify(body||{}),reply=>{
    const data=JSON.parse(reply);data.error?reject(Error(data.error)):resolve(data);
  }));
}
function applyAppearance(theme,scale){
  document.documentElement.dataset.theme=theme.toLowerCase();

  document.querySelectorAll('.chart-card').forEach(card=>card._baseKey=null);
  state.dataVersion++;scheduleDraw();
}
function updateLiveUI(){
  const running=['connecting','recording','stopping'].includes(state.status);
  for(const mode of ['record','monitor']){
    const button=$(`mode-${mode}`);button.classList.toggle('active',state.sessionMode===mode);
    button.setAttribute('aria-pressed',String(state.sessionMode===mode));button.disabled=running||(mode==='monitor'&&!state.monitorSupported);
    if(mode==='monitor'&&!state.monitorSupported)button.title='Restart the logger to enable live monitoring.';
  }
  $('live-panel').hidden=state.source!=='live'||state.dataMode!=='monitor';
  $('download-button').hidden=state.source==='live'&&state.dataMode==='monitor';
  $('follow-live').hidden=state.source!=='live'||!running;
  $('follow-live').classList.toggle('active',state.followLive);
  $('follow-live').textContent=state.followLive?'Following live':'Follow live';
  $('sample-button').disabled=running;$('import-button').disabled=running;
  $('capture-button').innerHTML=running?`<span class="record-dot"></span> Stop ${state.dataMode==='monitor'?'live monitor':'CSV log'}`:`<span class="record-dot"></span> Start ${state.sessionMode==='monitor'?'live monitor':'CSV log'}`;
}
function updateStatus(status){
  const wasRunning=['connecting','recording','stopping'].includes(state.status);
  state.status=status.state;const running=['connecting','recording','stopping'].includes(status.state),button=$('capture-button'),pill=$('status-pill');
  if(state.source==='live'&&running){state.sessionMode=status.mode||state.sessionMode;state.dataMode=state.sessionMode}
  if(state.source==='live'&&wasRunning&&!running&&state.followLive){state.view=liveView();state.followLive=false;scheduleDraw()}
  button.classList.toggle('running',running);
  const statusText=running&&state.dataMode==='monitor'&&status.state==='recording'?'MONITORING':status.state.toUpperCase();
  pill.classList.toggle('recording',running);pill.innerHTML=running?`<i></i> ${statusText}`:`<i></i> ${state.source==='live'?'SESSION '+status.state.toUpperCase():state.source.toUpperCase()+' DATA'}`;
  if(status.error)showNotice(status.error);else if(running)showNotice('');
  if(state.source==='live'&&status.fields?.length&&state.fields.join()!=status.fields.join())setData(status.fields,[],status.output||'Live capture','live');
  updateLiveUI();
  if(state.source==='live')updateMetrics();
}
let lastStatusPoll=0;
async function poll(){
  let delay=100;
  try{
    if(performance.now()-lastStatusPoll>=500){updateStatus(await api('/api/status'));lastStatusPoll=performance.now()}
    if(state.source==='live'){
      const version=state.dataVersion,next=state.next;
      const chunk=await api(`/api/samples?since=${next}`);
      if(state.source==='live'&&state.dataVersion===version){
        if(chunk.base>next){state.rows=[];state.baseIndex=chunk.base}
        else if(chunk.available_from>state.baseIndex){const drop=Math.min(state.rows.length,chunk.available_from-state.baseIndex);state.rows.splice(0,drop);state.baseIndex+=drop}
        state.next=chunk.next;
        if(chunk.rows.length){
          state.rows.push(...chunk.rows);
          state.dataVersion++;
          if(state.dataMode==='monitor'){
            const cutoff=tAt(state.rows.length-1)-30;let drop=0;
            while(drop<state.rows.length&&tAt(drop)<cutoff)drop++;
            if(drop){state.rows.splice(0,drop);state.baseIndex+=drop}
            if(state.view){const [first,last]=range(),span=state.view[1]-state.view[0];if(state.view[0]<first)state.view=[first,Math.max(first+span,last)]}
          }
          updateMetrics();updateLiveValues();scheduleDraw();
        }
        if(chunk.total>state.next)delay=0;
      }
    }
  }catch(e){showNotice(e.message)}
  finally{setTimeout(poll,delay)}
}
async function startCapture(){
  if(state.sessionMode==='monitor'&&!state.monitorSupported){showNotice('Restart the logger app to enable live monitoring.');return}
  try{const status=await api('/api/start',{signals:[...state.selected],channel:$('channel').value,bitrate:Number($('bitrate').value),rate:Number($('rate').value),mode:state.sessionMode});setData(status.fields,[],state.sessionMode==='monitor'?'Live monitor':'Live capture','live');updateStatus(status);showNotice('')}catch(e){showNotice(e.message)}
}
async function loadSample(){try{const data=await api('/api/sample-capture');setData(data.fields,data.rows,data.name,'sample');updateStatus(await api('/api/status'));showNotice('')}catch(e){showNotice(e.message)}}
function parseCSV(text){
  if(!text.includes('"')){
    const lines=text.split(/\r?\n/);
    const fields=(lines.shift()||'').split(',').map(x=>x.replace(/^\uFEFF/,''));
    const rows=[];
    for(const line of lines){
      if(!line)continue;
      const values=line.split(','),row={};
      for(let i=0;i<fields.length;i++){const value=values[i],number=Number(value);row[fields[i]]=value==null||value===''||!Number.isFinite(number)?null:number}
      rows.push(row);
    }
    if(!fields.length||!rows.length)throw Error('CSV file has no data rows.');
    if(!fields.includes('t_s')){fields.unshift('t_s');rows.forEach((r,i)=>r.t_s=i)}
    const normalized=normalizeLegacy(fields,rows);return addTuningFields(normalized.fields,normalized.rows);
  }
  const lines=[];let row=[],field='',quoted=false;
  for(let i=0;i<text.length;i++){const ch=text[i];if(quoted){if(ch==='"'&&text[i+1]==='"'){field+='"';i++}else if(ch==='"')quoted=false;else field+=ch}else if(ch==='"')quoted=true;else if(ch===','){row.push(field);field=''}else if(ch==='\n'){row.push(field.replace(/\r$/,''));lines.push(row);row=[];field=''}else field+=ch}
  if(field||row.length){row.push(field);lines.push(row)}
  const fields=lines.shift()?.map(x=>x.replace(/^\uFEFF/,''))||[];
  const rows=lines.filter(x=>x.length>1).map((x,i)=>Object.fromEntries(fields.map((f,j)=>[f,x[j]===''?null:num(x[j])])));
  if(!fields.length||!rows.length)throw Error('CSV file has no data rows.');
  if(!fields.includes('t_s')){fields.unshift('t_s');rows.forEach((r,i)=>r.t_s=i)}
  const normalized=normalizeLegacy(fields,rows);return addTuningFields(normalized.fields,normalized.rows);
}
async function initialize(){
  try{state.meta=await api('/api/meta');state.monitorSupported=state.meta.features?.includes('monitor')||false;const pref=loadPrefs();const valid=(pref.selected||state.meta.defaults).filter(n=>state.meta.signals.some(s=>s.name===n));state.selected=new Set(valid.length?valid:state.meta.defaults);renderSignalList();const status=await api('/api/status');if(['connecting','recording','stopping'].includes(status.state)&&status.fields?.length){state.sessionMode=status.mode||'record';setData(status.fields,[],status.mode==='monitor'?'Live monitor':status.output||'Live capture','live');updateStatus(status)}else await loadSample()}catch(e){showNotice(e.message)}
  $('signal-search').oninput=renderSignalList;
  $('select-defaults').onclick=()=>{state.selected=new Set(state.meta.defaults);renderSignalList();savePrefs()};
  $('clear-signals').onclick=()=>{state.selected.clear();renderSignalList();savePrefs()};
  for(const key of ['channel','bitrate','rate'])$(key).onchange=savePrefs;
  $('settings-toggle').onclick=()=>{$('settings').classList.toggle('open');$('settings-chevron').textContent=$('settings').classList.contains('open')?'⌃':'⌄'};
  for(const mode of ['record','monitor'])$(`mode-${mode}`).onclick=()=>{state.sessionMode=mode;updateLiveUI();savePrefs()};
  $('capture-button').onclick=async()=>{if(['connecting','recording','stopping'].includes(state.status)){try{updateStatus(await api('/api/stop',{}))}catch(e){showNotice(e.message)}}else await startCapture()};
  $('sample-button').onclick=loadSample;
  $('import-button').onclick=()=>$('file-input').click();
  $('file-input').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const data=parseCSV(await file.text());setData(data.fields,data.rows,file.name,'imported');updateStatus(await api('/api/status'));showNotice('')}catch(err){showNotice(err.message)}e.target.value=''};
  $('download-button').onclick=()=>{if(state.source==='live')api('/api/download',{}).catch(e=>showNotice(e.message));else{const csv=[['TEMP_SCALE_VERSION',...state.fields].join(','),...state.rows.map(r=>[2,...state.fields.map(f=>r[f]??'')].join(','))].join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download=state.name||'ccp_data.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}};
  const add=()=>{if(state.graphs.length>=8)return;const used=new Set(state.graphs.flatMap(g=>g.signals)),next=state.fields.find(f=>f!==tField()&&!['cycle','dto_frames'].includes(f)&&!used.has(f))||state.fields.find(f=>f!==tField()&&!['cycle','dto_frames'].includes(f));state.graphs.push({signals:next?[next]:[],height:180,axes:{},colors:{}});renderGraphs();savePrefs();openModal(state.graphs.length-1)};
  $('add-graph').onclick=add;$('add-graph-bottom').onclick=add;
  $('zoom-in').onclick=()=>zoom(.72);$('zoom-out').onclick=()=>zoom(1.4);$('fit-view').onclick=()=>{state.followLive=false;state.view=null;updateLiveUI();scheduleDraw()};
  $('time-scroll').oninput=e=>{const [first,last]=timeBounds(),[a,b]=view(),span=b-a;const start=first+(last-first-span)*Number(e.target.value)/10000;setView(start,start+span)};
  $('follow-live').onclick=()=>{state.followLive=true;state.view=null;updateLiveUI();scheduleDraw()};
  $('plot-search').oninput=renderModal;$('modal-close').onclick=()=>$('plot-modal').hidden=true;
  $('plot-modal').onclick=e=>{if(e.target===$('plot-modal'))$('plot-modal').hidden=true};
  $('modal-save').onclick=()=>{const graph=state.graphs[state.modalIndex];graph.signals=[...state.modalSelected];graph.axes=state.modalAxes;graph.colors=state.modalColors;$('plot-modal').hidden=true;renderGraphs();savePrefs()};
  window.addEventListener('resize',scheduleDraw);
  setTimeout(poll,100);
}
new QWebChannel(qt.webChannelTransport,channel=>{nativeBridge=channel.objects.logger;applyAppearance(nativeBridge.theme,nativeBridge.scale);applyPalette(nativeBridge.palette);nativeBridge.appearanceChanged.connect(applyAppearance);nativeBridge.paletteChanged.connect(applyPalette);initialize();});

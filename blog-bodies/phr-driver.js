(() => {
const BASE='https://raw.githubusercontent.com/roger506/phr-graphics/main/blog-bodies/';
const TITLE='Sierra Ranches, Davie Real Estate Market Update';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const L=[];
const log=(...a)=>{L.push(a.map(x=>typeof x==='object'?JSON.stringify(x):String(x)).join(' '));};

function fire(el){
  const r=el.getBoundingClientRect();
  const o={bubbles:true,cancelable:true,view:window,clientX:r.x+r.width/2,clientY:r.y+r.height/2};
  ['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click']
    .forEach(t=>el.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,o)));
}
function rows(){return [...document.querySelectorAll('li.list-item')];}
function findRow(){return rows().find(x=>x.innerText.includes(TITLE));}
function modalOpen(){
  return [...document.querySelectorAll('div.el-tabs__item')].some(x=>x.textContent.trim()==='Schema');
}
function postEditor(){
  return tinymce.editors.find(e=>{try{return e.getElement().closest('.el-dialog');}catch(_){return false;}});
}
function tab(name){
  const t=[...document.querySelectorAll('div.el-tabs__item')].find(x=>x.textContent.trim()===name);
  if(t) fire(t);
  return !!t;
}
async function gotoPage(n){
  const p=[...document.querySelectorAll('.page-list *')].find(x=>x.textContent.trim()===String(n)&&x.children.length===0);
  if(!p) return false;
  fire(p); await sleep(2500); return true;
}
async function openPost(){
  let r=findRow();
  for(let pg=2; !r && pg<=4; pg++){ if(!await gotoPage(pg)) break; r=findRow(); }
  if(!r){log('ROW NOT FOUND'); return false;}
  log('row found:', r.innerText.replace(/\s+/g,' ').slice(0,160));
  const pen=r.querySelector('i.icon-edit1');
  if(!pen){log('NO PENCIL'); return false;}
  fire(pen);
  for(let i=0;i<30;i++){ await sleep(1000); if(modalOpen()) break; }
  log('modal open:', modalOpen());
  return modalOpen();
}
async function setBody(){
  const html=await (await fetch(BASE+'sierra-body.html')).text();
  log('body fetched', html.length);
  for(let i=0;i<20;i++){ if(postEditor()) break; await sleep(500); }
  const ed=postEditor();
  if(!ed){log('NO POST EDITOR'); return false;}
  ed.setContent(html);
  ['change','input','keyup','blur'].forEach(e=>ed.fire(e));
  if(ed.save) ed.save();
  const back=ed.getContent().length;
  log('body set, readback', back);
  return back>1500;
}
async function setSchema(){
  const js=await (await fetch(BASE+'sierra-schema.json')).text();
  if(!tab('Schema')){log('NO SCHEMA TAB'); return false;}
  await sleep(1500);
  const cm=document.querySelector('.CodeMirror');
  if(!cm||!cm.CodeMirror){log('NO CODEMIRROR'); return false;}
  cm.CodeMirror.setValue(js);
  await sleep(500);
  log('schema set', cm.CodeMirror.getValue().length);
  return true;
}
function descField(){
  const divs=[...document.querySelectorAll('div.ie-content')];
  return divs.map((el,i)=>({i,el,txt:(el.innerText||'').trim().slice(0,70)}));
}
function counters(){
  return [...document.querySelectorAll('*')].filter(e=>e.children.length===0&&/^\d+\s*\/\s*\d+$/.test(e.textContent.trim())).map(e=>e.textContent.trim());
}
async function toSEO(){
  if(!tab('SEO')){log('NO SEO TAB'); return false;}
  await sleep(2000);
  log('seo fields', JSON.stringify(descField().map(d=>({i:d.i,txt:d.txt}))));
  log('counters', JSON.stringify(counters()));
  return true;
}
function selectField(i){
  const el=[...document.querySelectorAll('div.ie-content')][i];
  if(!el){log('no field',i); return false;}
  el.focus();
  const r=document.createRange(); r.selectNodeContents(el);
  const s=getSelection(); s.removeAllRanges(); s.addRange(r);
  log('selected field',i,'active',document.activeElement===el);
  return true;
}
async function publish(expectLen){
  const c=counters(); const ed=postEditor();
  const bodyLen=ed?ed.getContent().length:0;
  log('GATE counters',JSON.stringify(c),'bodyLen',bodyLen);
  if(bodyLen<1500){log('ABORT: body too short'); return false;}
  if(!c.some(x=>x.split('/')[0].trim()===String(expectLen))){log('ABORT: counter does not show',expectLen); return false;}
  const btn=[...document.querySelectorAll('button,div')].filter(b=>b.children.length<=2)
    .find(b=>/^(Publish|Post Now)$/.test(b.textContent.trim()));
  if(!btn){log('NO PUBLISH BUTTON'); return false;}
  log('clicking', btn.textContent.trim());
  fire(btn);
  for(let i=0;i<40;i++){ await sleep(1000); if(!modalOpen()){log('modal closed at',i); return true;} }
  log('modal STILL OPEN after 40s');
  return false;
}
window.PHR={log:L, sleep, fire, rows, findRow, modalOpen, postEditor, tab, openPost,
  setBody, setSchema, toSEO, selectField, counters, descField, publish,
  async prepare(){
    L.length=0;
    try{
      if(!await openPost()) return 'OPEN FAILED';
      if(!await setBody()) return 'BODY FAILED';
      if(!await setSchema()) return 'SCHEMA FAILED';
      if(!await toSEO()) return 'SEO FAILED';
      log('PREPARE OK');
      return 'OK';
    }catch(e){ log('ERR', e.message); return 'ERR '+e.message; }
  }};
return 'PHR ready';
})()

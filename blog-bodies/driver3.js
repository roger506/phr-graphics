(()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));const L=[];const Q={log:L};
const OLD='Riverstone, Davie FL market update: 14';
const NEW='Riverstone, Davie FL market update: 11 closed sales, median $1,810,000, median 65 cumulative days to go under contract.';
Q.NEW=NEW;
const D=e=>{const r=e.getBoundingClientRect();const o={bubbles:true,cancelable:true,view:window,clientX:r.x+r.width/2,clientY:r.y+r.height/2};
['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>e.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,o)));};
Q.D=D;
const mt=()=>[...document.querySelectorAll('div.el-tabs__item')];
const isModal=()=>mt().some(x=>x.textContent.trim()==='Schema');
const tab=async n=>{const t=mt().find(x=>x.textContent.trim()===n);if(!t)return 0;D(t);await s(2500);return 1;};
const cnts=()=>[...document.querySelectorAll('.ie-count')].map(x=>x.textContent.trim());
Q.cnts=cnts;
const hunt=()=>{
 const out=[];
 let n=document.querySelectorAll('div.ie-content')[2];
 let vm=null;
 while(n&&!vm){ if(n.__vue__) vm=n.__vue__; n=n.parentElement; }
 let v=vm, lvl=0;
 while(v&&lvl<12){
  const d=v._data||v.$data||{};
  const walk=(o,path,dep)=>{
   if(!o||dep>3) return;
   for(const k of Object.keys(o)){
    let val; try{ val=o[k]; }catch(e){ continue; }
    if(typeof val==='string'&&val.indexOf(OLD)===0) out.push({lvl,path:path+k,len:val.length,obj:o,key:k});
    else if(val&&typeof val==='object'&&!Array.isArray(val)&&dep<3) walk(val,path+k+'.',dep+1);
   }
  };
  walk(d,'',0);
  v=v.$parent; lvl++;
 }
 return out;
};
Q.hunt=hunt;
Q.run=async()=>{
 if(!isModal()){
  const li=[...document.querySelectorAll('li.list-item')].find(x=>x.innerText.includes('Riverstone, Davie'));
  if(!li) return {err:'norow',log:L};
  D(li.querySelector('i.icon-edit1'));
  for(let i=0;i<20;i++){await s(1000); if(isModal()) break;}
 }
 if(!isModal()) return {err:'nomodal',log:L};
 L.push('modal open');
 await tab('SEO');
 L.push('seo tab, counters '+JSON.stringify(cnts()));
 const hits=hunt();
 L.push('hits '+hits.length+' '+JSON.stringify(hits.map(h=>({lvl:h.lvl,path:h.path,len:h.len}))));
 if(!hits.length) return {err:'nomodelfield',log:L,counters:cnts()};
 for(const h of hits){ try{ h.obj[h.key]=NEW; }catch(e){ L.push('setfail '+h.path); } }
 await s(1500);
 const c=cnts();
 L.push('after set '+JSON.stringify(c));
 const dom=(document.querySelectorAll('div.ie-content')[2].innerText||'').replace(/\n$/,'');
 const ok=c.some(x=>x.indexOf('119 /')===0);
 if(!ok) return {err:'counter-not-119',counters:c,dom:dom.slice(0,130),log:L};
 const b=[...document.querySelectorAll('button')].filter(x=>x.innerText.trim()==='Publish');
 if(!b.length) return {err:'nopublish',log:L};
 D(b[b.length-1]);
 await s(7000);
 return {counters:c,dom:dom.slice(0,130),published:!isModal(),log:L};
};
window.Q=Q;return'ready3';})()

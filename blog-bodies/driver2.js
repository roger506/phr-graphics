(()=>{const B='https://raw.githubusercontent.com/roger506/phr-graphics/main/blog-bodies/';
const T='Riverstone, Davie';const s=ms=>new Promise(r=>setTimeout(r,ms));const L=[];const P={log:L};
const D=e=>{const r=e.getBoundingClientRect();const o={bubbles:true,cancelable:true,view:window,clientX:r.x+r.width/2,clientY:r.y+r.height/2};
['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>e.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,o)));};
P.D=D;
const rows=()=>[...document.querySelectorAll('li.list-item')];
const row=()=>rows().find(x=>x.innerText.trim().startsWith(T));
const mtabs=()=>[...document.querySelectorAll('div.el-tabs__item')].map(x=>x.textContent.trim());
const isModal=()=>mtabs().includes('Schema');
const ed=()=>{const c=tinymce.editors.filter(e=>{try{const el=e.getElement();return el&&document.contains(el)&&el.closest('.el-dialog');}catch(x){return false}});
return c.length?c[c.length-1]:null;};
P.ed=ed;
const tab=async n=>{const t=[...document.querySelectorAll('div.el-tabs__item')].find(x=>x.textContent.trim()===n);if(!t)return 0;D(t);await s(2500);return 1;};
P.tab=tab;
const btn=async l=>{const b=[...document.querySelectorAll('button')].filter(x=>x.innerText.trim()===l);if(!b.length)return'none';D(b[b.length-1]);await s(6000);return'clicked'+b.length;};
P.btn=btn;
P.run=async()=>{
 P.H=await(await fetch(B+'2026-11-04-riverstone-davie.html')).text();
 P.F=await(await fetch(B+'2026-11-04-riverstone-davie-faq.json')).text();
 L.push('fetched '+P.H.length+'/'+P.F.length);
 if(!isModal()){
   let r=row();
   if(!r){for(const p of[3,2]){const pl=document.querySelector('.page-list');if(!pl)break;
     const e=[...pl.children].find(c=>c.innerText.trim()===String(p));if(!e)continue;D(e);await s(6000);r=row();if(r)break;}}
   if(!r)return{err:'norow',log:L};
   L.push('row found');D(r.querySelector('i.icon-edit1'));
   for(let i=0;i<20;i++){await s(1000);if(isModal())break;}
 }
 if(!isModal())return{err:'nomodal',log:L};
 const ti=document.querySelector('input[placeholder="Add a title here..."]');
 L.push('modal open, title='+(ti?ti.value:'?'));
 await tab('Content');
 const E=ed();if(!E)return{err:'noeditor',n:tinymce.editors.length,log:L};
 E.setContent(P.H);['change','input','keyup','blur'].forEach(x=>E.fire(x));if(E.save)E.save();
 await s(1000);
 const g=E.getContent(),ta=E.getElement();
 const body={len:g.length,ta:(ta&&ta.value||'').length,n1810:/1,810,000/.test(g),n1835:/1,835,000/.test(g),tb:(g.match(/<table/g)||[]).length,link:/riverstone-market-activity/.test(g)};
 L.push('body '+JSON.stringify(body));
 if(!(body.n1810&&!body.n1835&&body.tb===3&&body.link))return{err:'bodybad',body,log:L};
 await tab('Schema');
 const c=document.querySelector('.CodeMirror');
 if(!c||!c.CodeMirror)return{err:'nocm',body,log:L};
 c.CodeMirror.setValue(P.F);await s(1500);
 const v=c.CodeMirror.getValue();
 const sc={ok:v===P.F,len:v.length,msg:(document.body.innerText.match(/Valid JSON|Invalid/i)||[0])[0]};
 L.push('schema '+JSON.stringify(sc));
 if(!sc.ok)return{err:'schemabad',body,sc,log:L};
 const pub=await btn('Publish');
 await s(5000);
 return{body,sc,pub,stillModal:isModal(),counts:(document.body.innerText.match(/Published\s*\n?\s*\d+/g)||[]),log:L};
};
window.PHR=P;return'ready2';})()

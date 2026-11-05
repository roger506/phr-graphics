(()=>{const B='https://raw.githubusercontent.com/roger506/phr-graphics/main/blog-bodies/';
const T='Riverstone, Davie';const s=ms=>new Promise(r=>setTimeout(r,ms));const P={};
P.D=(e)=>{const r=e.getBoundingClientRect();const o={bubbles:true,cancelable:true,view:window,clientX:r.x+r.width/2,clientY:r.y+r.height/2};
['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>e.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,o)));};
P.rows=()=>[...document.querySelectorAll('li.list-item')];
P.row=()=>P.rows().find(x=>x.innerText.trim().startsWith(T));
P.page=async n=>{const pl=document.querySelector('.page-list');if(!pl)return 0;
const e=[...pl.children].find(c=>c.innerText.trim()===String(n));if(!e)return 0;P.D(e);await s(6000);return P.rows().length;};
P.tab=async n=>{const t=[...document.querySelectorAll('div.el-tabs__item')].find(x=>x.textContent.trim()===n);if(!t)return 0;P.D(t);await s(2500);return 1;};
P.cnt=()=>[...document.querySelectorAll('.ie-count')].map(e=>e.textContent.trim());
P.fields=()=>[...document.querySelectorAll('div.ie-content')];
P.focus=i=>{const e=P.fields()[i];e.focus();const r=document.createRange();r.selectNodeContents(e);const g=getSelection();g.removeAllRanges();g.addRange(r);return document.activeElement===e;};
P.end=async i=>{const e=P.fields()[i];e.blur();await s(600);e.focus();const r=document.createRange();r.selectNodeContents(e);r.collapse(false);const g=getSelection();g.removeAllRanges();g.addRange(r);return document.activeElement===e;};
P.btn=async l=>{const b=[...document.querySelectorAll('button')].filter(x=>x.innerText.trim()===l);if(!b.length)return 'none';P.D(b[b.length-1]);await s(5000);return 'clicked '+b.length;};
P.open=async()=>{if(window.tinymce&&tinymce.editors.length)return{already:1};
let r=P.row();if(!r){for(const p of[3,2,1]){await P.page(p);r=P.row();if(r)break;}}
if(!r)return{err:'norow'};P.D(r.querySelector('i.icon-edit1'));
for(let i=0;i<18;i++){await s(1000);if(window.tinymce&&tinymce.editors.length)break;}
const t=document.querySelector('input[placeholder="Add a title here..."]');
return{ed:(window.tinymce?tinymce.editors.length:0),title:t?t.value:null};};
P.body=async()=>{const e=tinymce.editors[0];e.setContent(P.H);['change','input','keyup','blur'].forEach(x=>e.fire(x));if(e.save)e.save();await s(800);
const g=e.getContent(),ta=e.getElement();return{len:g.length,ta:(ta&&ta.value||'').length,n1810:/1,810,000/.test(g),n1835:/1,835,000/.test(g),tb:(g.match(/<table/g)||[]).length};};
P.schema=async()=>{await P.tab('Schema');const c=document.querySelector('.CodeMirror');if(!c||!c.CodeMirror)return'nocm';
c.CodeMirror.setValue(P.F);await s(1500);const v=c.CodeMirror.getValue();
return{ok:v===P.F,len:v.length,msg:(document.body.innerText.match(/Valid JSON|Invalid/i)||[0])[0]};};
P.go=async()=>{P.H=await(await fetch(B+'2026-11-04-riverstone-davie.html')).text();
P.F=await(await fetch(B+'2026-11-04-riverstone-davie-faq.json')).text();
const o=await P.open();if(o.err)return o;const b=await P.body();const sc=await P.schema();
const pub=await P.btn('Publish');await s(4000);
return{open:o,body:b,schema:sc,pub,after:document.body.innerText.slice(0,200).replace(/\n/g,'|'),ed:(window.tinymce?tinymce.editors.length:0)};};
window.PHR=P;return'ready';})()

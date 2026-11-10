window.PHR = (function () {
  const B = 'https://raw.githubusercontent.com/roger506/phr-graphics/main/blog-bodies/';
  const BODY_URL   = B + '2026-11-10-imagination-farms-body.html';
  const SCHEMA_URL = B + '2026-11-10-imagination-farms-schema.json';
  const TITLE      = 'Imagination Farms, Davie Real Estate Market Update: 2026';
  const log = [];
  const L = (...a) => { log.push(a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' ')); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function dispatch(el) {
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window,
                clientX: r.x + r.width / 2, clientY: r.y + r.height / 2 };
    ['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click']
      .forEach(t => el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o)));
  }
  function modalOpen() {
    return [...document.querySelectorAll('div.el-tabs__item')]
      .some(x => x.textContent.trim() === 'Schema');
  }
  function tabEl(name) {
    return [...document.querySelectorAll('div.el-tabs__item')]
      .find(x => x.textContent.trim() === name);
  }
  async function tab(name) {
    const t = tabEl(name);
    if (!t) { L('tab-missing', name); return false; }
    dispatch(t); await sleep(1200); L('tab', name); return true;
  }
  function postEditor() {
    if (!window.tinymce) return null;
    return tinymce.editors.find(e => { try { return !!e.getElement().closest('.el-dialog'); } catch (x) { return false; } });
  }
  async function openPost() {
    if (modalOpen()) { L('modal already open'); return true; }
    const li = [...document.querySelectorAll('li.list-item')]
                 .find(x => x.innerText.trim().startsWith(TITLE));
    if (!li) { L('ROW NOT FOUND'); return false; }
    const e = li.querySelector('i.icon-edit1');
    if (!e) { L('PENCIL NOT FOUND'); return false; }
    dispatch(e);
    for (let i = 0; i < 20; i++) { await sleep(800); if (modalOpen()) break; }
    L('modal', modalOpen());
    return modalOpen();
  }
  async function setBody() {
    const html = await (await fetch(BODY_URL, { cache: 'no-store' })).text();
    L('body fetched', html.length);
    if (!/Imagination Farms/.test(html) || !/1,740,000/.test(html)) { L('BODY SANITY FAIL'); return false; }
    await tab('Content'); await sleep(800);
    const ed = postEditor();
    if (!ed) { L('NO POST EDITOR', window.tinymce ? tinymce.editors.length : 'no tinymce'); return false; }
    ed.setContent(html);
    ed.fire('change'); ed.fire('input'); ed.fire('keyup'); ed.fire('blur');
    if (ed.save) ed.save();
    const back = ed.getContent();
    const ta = ed.getElement();
    L('body in/back/textarea', html.length, back.length, (ta && ta.value || '').length);
    L('tables back', (back.match(/<table/g) || []).length);
    return back.length > 2000;
  }
  async function setSchema() {
    const txt = await (await fetch(SCHEMA_URL, { cache: 'no-store' })).text();
    L('schema fetched', txt.length);
    try { JSON.parse(txt); } catch (e) { L('SCHEMA NOT JSON'); return false; }
    if (!await tab('Schema')) return false;
    await sleep(800);
    const cms = [...document.querySelectorAll('.CodeMirror')].filter(c => c.CodeMirror);
    L('codemirrors', cms.length);
    if (!cms.length) return false;
    const cm = cms[cms.length - 1].CodeMirror;
    cm.setValue(txt);
    await sleep(300);
    L('schema len back', cm.getValue().length);
    return cm.getValue().length === txt.length;
  }
  function ceList() {
    return [...document.querySelectorAll('.el-dialog .ie-content, .el-dialog [contenteditable="true"]')];
  }
  function seoFields() {
    return ceList().map((el, i) => {
      let box = el.parentElement, counter = '';
      for (let k = 0; k < 4 && box; k++, box = box.parentElement) {
        const m = (box.innerText || '').match(/(\d+)\s*\/\s*(\d+)/);
        if (m) { counter = m[0]; break; }
      }
      const r = el.getBoundingClientRect();
      return { i, counter, text: (el.innerText || '').slice(0, 70), len: (el.innerText || '').length,
               cls: el.className, y: Math.round(r.y), x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height) };
    });
  }
  function pickDesc() {
    const f = seoFields().find(x => /\/\s*1000/.test(x.counter));
    return f ? f.i : -1;
  }
  function selectAll(i) {
    const el = ceList()[i]; if (!el) { L('no field', i); return false; }
    el.focus();
    const r = document.createRange(); r.selectNodeContents(el);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    L('selectAll', i, 'active=', document.activeElement && document.activeElement.className);
    return true;
  }
  async function caretEnd(i) {
    const el = ceList()[i]; if (!el) return false;
    el.blur(); await sleep(600); el.focus();
    const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    L('caretEnd', i);
    return true;
  }
  function footer() {
    return [...document.querySelectorAll('.el-dialog button, .el-dialog .el-button')]
             .map((b, i) => ({ i, t: (b.innerText || '').trim().slice(0, 30) }));
  }
  function clickFooter(label) {
    const b = [...document.querySelectorAll('.el-dialog button, .el-dialog .el-button')]
                .find(x => (x.innerText || '').trim().toLowerCase() === label.toLowerCase());
    if (!b) { L('footer btn missing', label); return false; }
    dispatch(b); L('clicked', label); return true;
  }
  function state() {
    return { modalOpen: modalOpen(),
             tabs: [...document.querySelectorAll('div.el-tabs__item')].map(x => x.textContent.trim()),
             editors: window.tinymce ? tinymce.editors.length : 0,
             footer: footer(), seo: seoFields() };
  }
  async function prepare() {
    log.length = 0;
    if (!await openPost()) return { ok: false, log };
    const b = await setBody();
    const s = await setSchema();
    await tab('SEO'); await sleep(1000);
    const di = pickDesc();
    L('desc field index', di);
    return { ok: b && s, body: b, schema: s, descIndex: di, seo: seoFields(), log };
  }
  return { log, prepare, openPost, setBody, setSchema, state, seoFields, pickDesc, selectAll, caretEnd,
           footer, clickFooter, tab, dispatch, modalOpen, postEditor };
})();
'PHR ready'

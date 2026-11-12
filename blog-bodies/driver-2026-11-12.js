(function () {
  const RAW = 'https://raw.githubusercontent.com/roger506/phr-graphics/main/blog-bodies/';
  const PHR = {
    log: [],
    info: {},
    L(m) { this.log.push(new Date().toISOString().slice(11, 19) + ' ' + m); },
    sleep(ms) { return new Promise(r => setTimeout(r, ms)); },
    fire(el) {
      const r = el.getBoundingClientRect();
      const o = { bubbles: true, cancelable: true, view: window,
                  clientX: r.x + r.width / 2, clientY: r.y + r.height / 2 };
      ['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click']
        .forEach(t => el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o)));
    },
    modalOpen() {
      return [...document.querySelectorAll('div.el-tabs__item')]
        .some(x => x.textContent.trim() === 'Schema');
    },
    editor() {
      return (window.tinymce ? tinymce.editors : []).find(e => {
        try { return !!e.getElement().closest('.el-dialog'); } catch (_) { return false; }
      });
    },
    tab(name) {
      const t = [...document.querySelectorAll('div.el-tabs__item')]
        .filter(x => x.closest('.el-dialog'))
        .find(x => x.textContent.trim() === name);
      if (t) { this.fire(t); this.L('tab -> ' + name); return true; }
      this.L('TAB NOT FOUND: ' + name); return false;
    },
    rows() {
      return [...document.querySelectorAll('li.list-item')];
    },
    rowFor(title) {
      return this.rows().find(x => x.innerText.trim().startsWith(title));
    },
    pageButtons() {
      const pl = document.querySelector('.page-list');
      return pl ? [...pl.children] : [];
    },
    async findPost(title) {
      for (let p = 1; p <= 8; p++) {
        const r = this.rowFor(title);
        if (r) { this.L('found post row on page ' + p); this.info.rowText = r.innerText.trim().slice(0, 300); return r; }
        const btn = this.pageButtons().find(b => b.textContent.trim() === String(p + 1));
        if (!btn) { this.L('no further pages after ' + p); return null; }
        this.fire(btn); await this.sleep(2500);
      }
      return null;
    },
    async openPost(title) {
      const row = await this.findPost(title);
      if (!row) { this.L('POST ROW NOT FOUND: ' + title); return false; }
      this.fire(row.querySelector('i.icon-edit1'));
      for (let i = 0; i < 40; i++) {
        await this.sleep(500);
        if (this.modalOpen()) { this.L('modal open'); await this.sleep(1500); return true; }
      }
      this.L('MODAL DID NOT OPEN'); return false;
    },
    setBody(html) {
      const ed = this.editor();
      if (!ed) { this.L('NO DIALOG EDITOR'); return false; }
      ed.setContent(html);
      ['change','input','keyup','blur'].forEach(t => ed.fire(t));
      if (ed.save) ed.save();
      const n = ed.getContent().length;
      this.info.bodyLen = n;
      this.L('body set, getContent ' + n + ' chars');
      return n > 500;
    },
    async setSchema(json) {
      if (!this.tab('Schema')) return false;
      await this.sleep(1500);
      const cmEl = [...document.querySelectorAll('.CodeMirror')].find(x => x.closest('.el-dialog')) 
                 || document.querySelector('.CodeMirror');
      if (!cmEl || !cmEl.CodeMirror) { this.L('NO CODEMIRROR'); return false; }
      cmEl.CodeMirror.setValue(json);
      this.info.schemaLen = cmEl.CodeMirror.getValue().length;
      this.L('schema set, ' + this.info.schemaLen + ' chars');
      return true;
    },
    seoFields() {
      return [...document.querySelectorAll('.el-dialog div.ie-content')];
    },
    counters() {
      return [...document.querySelectorAll('.el-dialog *')]
        .filter(e => e.children.length === 0 && /^\d+\s*\/\s*\d+$/.test(e.textContent.trim()))
        .map(e => e.textContent.trim());
    },
    seoSnapshot() {
      return this.seoFields().map((f, i) => ({ i, text: f.innerText.trim().slice(0, 160), len: f.innerText.trim().length }));
    },
    focusField(i) {
      const f = this.seoFields()[i];
      if (!f) { this.L('NO SEO FIELD ' + i); return false; }
      f.focus();
      const r = document.createRange(); r.selectNodeContents(f);
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      this.L('focused+selected SEO field ' + i + ' (was ' + f.innerText.trim().length + ' chars)');
      this.info.focusedField = i;
      return document.activeElement === f || f.contains(document.activeElement);
    },
    footerBtn() {
      return [...document.querySelectorAll('.el-dialog button, .el-dialog .el-button')]
        .find(b => ['Publish', 'Post Now', 'Update'].includes(b.textContent.trim()));
    },
    async prepare(title, bodyFile, schemaFile, descIndex) {
      try {
        this.log = []; this.info = {};
        this.L('prepare start');
        const [body, schema] = await Promise.all([
          fetch(RAW + bodyFile + '?cb=' + Date.now()).then(r => r.text()),
          fetch(RAW + schemaFile + '?cb=' + Date.now()).then(r => r.text())
        ]);
        this.L('fetched body ' + body.length + ' / schema ' + schema.length);
        if (body.length < 500 || schema.length < 100) { this.L('FETCH TOO SHORT, ABORT'); return; }
        if (!(await this.openPost(title))) return;
        if (!this.tab('Content')) return;
        await this.sleep(1200);
        if (!this.setBody(body)) return;
        if (!(await this.setSchema(schema))) return;
        if (!this.tab('SEO')) return;
        await this.sleep(1800);
        this.info.seoBefore = this.seoSnapshot();
        this.info.countersBefore = this.counters();
        this.focusField(descIndex);
        this.L('PREPARE DONE - field focused and selected, ready for keystrokes');
      } catch (e) { this.L('PREPARE ERROR ' + e.message); }
    },
    async publish(expectDescLen, minBodyLen) {
      try {
        this.L('publish gate start');
        const snap = this.seoSnapshot();
        this.info.seoAfter = snap;
        this.info.countersAfter = this.counters();
        const ed = this.editor();
        const bodyLen = ed ? ed.getContent().length : 0;
        this.info.bodyLenAtPublish = bodyLen;
        const desc = snap[this.info.focusedField];
        this.L('gate: bodyLen=' + bodyLen + ' descLen=' + (desc ? desc.len : 'n/a') + ' counters=' + this.info.countersAfter.join(','));
        if (bodyLen < minBodyLen) { this.L('ABORT: body too short'); return; }
        if (!desc || desc.len !== expectDescLen) { this.L('ABORT: desc length mismatch, expected ' + expectDescLen); return; }
        const okCounter = this.info.countersAfter.some(c => parseInt(c.split('/')[0].trim(), 10) === expectDescLen);
        if (!okCounter) { this.L('ABORT: no counter reads ' + expectDescLen + ' (model not committed)'); return; }
        const btn = this.footerBtn();
        if (!btn) { this.L('ABORT: no footer publish button'); return; }
        this.L('clicking footer button: ' + btn.textContent.trim());
        this.fire(btn);
        for (let i = 0; i < 40; i++) {
          await this.sleep(1000);
          if (!this.modalOpen()) { this.L('MODAL CLOSED - published'); return; }
        }
        this.L('modal still open after 40s - check manually');
      } catch (e) { this.L('PUBLISH ERROR ' + e.message); }
    }
  };
  window.PHR = PHR;
  return 'PHR loaded';
})();

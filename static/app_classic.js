// Classic UI enhanced 20250821a: scanning, login, settings, AI models, ops
(function () {
  const TYPES = {
    TEXT: ["docx", "doc", "txt", "md", "rtf"],
    DATA: ["xlsx", "xlsm", "xls", "csv", "tsv", "xml", "parquet"],
    SLIDES: ["pptx", "ppt"],
    PDF: ["pdf"],
    ARCHIVE: ["zip", "rar", "7z"],
    IMAGE: ["jpg", "jpeg", "gif", "png", "tif", "tiff", "bmp", "svg", "webp"],
    VIDEO: ["wmv", "mp4", "avi", "mov", "mkv"],
    AUDIO: ["mp3", "wav", "m4a", "flac"]
  };

  const PATHS = {
    scan: ["/full/scan"],
    exportCSV: ["/full/export_csv"],
    kw: ["/full/keywords"],
    imgKw: ["/full/keywords_image", "/api/keywords_image"],
    clearKW: ["/full/clear_keywords"],
    applyOps: ["/full/apply_ops"],
    normalize: ["/full/normalize"],
    ls: ["/full/ls", "/ls"] // 兼容旧入口
  };

  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));
  const qs = v => encodeURIComponent(v || "");

  let features = {};
  let lastQuery = null;
  let currentPage = 1, totalPages = 1, total = 0;
  let opMode = null; // 当前批量操作模式：move/rename/delete
  let filterWhere = null, filterWhereDoc = null; // 搜索过滤器
  let currentTheme = 'system';

  function applyTheme(theme) {
    currentTheme = theme || 'system';
    const html = document.documentElement;
    if (currentTheme === 'dark') {
      html.setAttribute('data-theme', 'dark');
    } else if (currentTheme === 'light') {
      html.setAttribute('data-theme', 'light');
    } else {
      html.removeAttribute('data-theme');
    }
    console.log('Theme applied:', currentTheme);
  }

  // Listen for system theme changes if in 'system' mode
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (currentTheme === 'system') {
      applyTheme('system');
    }
  });

  function setOpMode(mode) {
    opMode = mode;
    $('#applyMoveBtn').textContent = mode === 'move' ? '执行移动' : '批量移动';
    $('#applyRenameBtn').textContent = mode === 'rename' ? '执行重命名' : '批量重命名';
    $('#applyDeleteBtn').textContent = mode === 'delete' ? '执行删除' : '批量删除';
    updateRowInputs();
  }

  function updateRowInputs() {
    const rows = $$('#tbl tbody tr');
    rows.forEach(tr => {
      const cb = tr.querySelector('.ck');
      const mv = tr.querySelector('.mv');
      const rn = tr.querySelector('.rn');
      const path = cb.dataset.path;
      if (cb.checked) {
        mv.disabled = (opMode !== 'move');
        rn.disabled = (opMode !== 'rename');
        if (opMode === 'move' && !mv.value) mv.value = path;
        if (opMode === 'rename' && !rn.value) rn.value = path.split(/[\\\/]/).pop();
      } else {
        mv.disabled = true; mv.value = '';
        rn.disabled = true; rn.value = '';
      }
    });
  }

  function bind(sel, evt, fn) { const el = $(sel); if (el) el.addEventListener(evt, fn); return el; }

  function toggleLoading(on, msg) {
    const el = $('#loading');
    if (!el) return;
    const txt = el.querySelector('.loading-text');
    if (txt) txt.textContent = msg || '正在处理，请稍候…';
    if (on) el.classList.add('show'); else el.classList.remove('show');
  }

  function humanKBFromBytes(n) { if (n == null || isNaN(n)) return ''; return (Number(n) / 1024).toFixed(1); }
  function humanKBFromAny(v) {
    if (v == null || v === '') return '';
    if (typeof v === 'number') return humanKBFromBytes(v);
    const s = String(v).trim().toLowerCase();
    const m = s.match(/^(\d+(?:\.\d+)?)(kb|mb|gb|b)?$/i);
    if (m) {
      const num = parseFloat(m[1]); const unit = (m[2] || 'b').toLowerCase();
      if (unit === 'kb') return num.toFixed(1);
      if (unit === 'mb') return (num * 1024).toFixed(1);
      if (unit === 'gb') return (num * 1024 * 1024).toFixed(1);
      return humanKBFromBytes(num);
    }
    const n = parseFloat(s); if (!isNaN(n)) return humanKBFromBytes(n);
    return '';
  }
  function parseMTime(row) {
    let v = row.mtime ?? row.mtime_ms ?? row.modified ?? row.modified_ms ?? row.mtime_ts ?? row.mtimeMs;
    if (v == null) {
      const iso = row.mtime_iso || row.modified_iso || row.iso_time;
      if (iso) { try { return new Date(iso).toLocaleString(); } catch (e) { return ''; } }
      return '';
    }
    if (typeof v === 'string') {
      if (/^\d+(\.\d+)?$/.test(v)) v = parseFloat(v);
      else { try { return new Date(v).toLocaleString(); } catch (e) { return ''; } }
    }
    if (v > 1e12) v = v / 1000;
    try { return new Date(v * 1000).toLocaleString(); } catch (e) { return ''; }
  }
  function normJoin(dir, name) {
    if (!dir && !name) return '';
    let p = (dir ? String(dir) : '') + (dir && name ? (/[\\/]$/.test(dir) ? '' : '/') : '') + (name ? String(name) : '');
    if (/^[A-Za-z]:/.test(p) || /\\/.test(p)) p = p.replace(/\//g, '\\');
    return p;
  }
  function getFullPath(row) {
    const full = row.full || row.fullpath || row.full_path || row.absolute || row.abspath || row.path;
    if (full) return String(full);
    const name = row.name || row.filename || row.base || row.basename || '';
    const dir = row.dir || row.directory || row.folder || row.parent || row.dirname || row.path_dir || row.dir_path;
    return normJoin(dir || '', name);
  }
  function getExt(row) {
    let e = row.ext || row.extension || '';
    if (!e) {
      const full = getFullPath(row); const i = String(full).lastIndexOf('.'); if (i >= 0) e = String(full).slice(i + 1);
    }
    return (e || '').toLowerCase();
  }

  async function firstOK(urls, opts) {
    let lastErr = null;
    for (const u of urls) {
      try {
        const r = await fetch(u, Object.assign({ cache: 'no-store', credentials: 'include' }, opts || {}));
        if (r.ok) return { ok: true, r };
        lastErr = new Error('HTTP ' + r.status);
      } catch (e) { lastErr = e; }
    }
    return { ok: false, error: lastErr };
  }

  function customConfirm(msg) {
    return new Promise(resolve => {
      const m = $('#confirmModal');
      $('#confirmMessage').textContent = msg;
      m.style.display = 'flex';
      const ok = () => { m.style.display = 'none'; resolve(true); };
      const no = () => { m.style.display = 'none'; resolve(false); };
      $('#confirmOk').onclick = ok; $('#confirmCancel').onclick = no;
    });
  }
  function customPreview(title, content) {
    const m = $('#previewModal');
    $('#previewTitle').textContent = title;
    $('#previewContent').innerHTML = content;
    m.style.display = 'flex';
    $('#previewClose').onclick = () => { m.style.display = 'none'; $('#previewContent').innerHTML = ''; };
  }

  // ---------- UI helpers ----------
  function fillTypes() {
    const cat = $('#category'), types = $('#types');
    if (!cat || !types) return;
    types.innerHTML = '';
    (TYPES[cat.value] || []).forEach(ext => {
      const o = document.createElement('option'); o.value = ext; o.textContent = ext; types.appendChild(o);
    });
  }

  function showDirModal() {
    const modal = $('#dirModal'), here = $('#dirHere'), list = $('#dirList');
    let cwd = $('#dir').value || '';
    async function refresh() {
      here.textContent = cwd || '(根)';
      const urls = PATHS.ls.map(u => u + (cwd ? ('?dir=' + qs(cwd)) : ''));
      toggleLoading(true, '读取目录…');
      const res = await firstOK(urls);
      toggleLoading(false);
      if (!res.ok) { list.innerHTML = '<li>目录列举失败</li>'; return; }
      try {
        const j = await res.r.json();
        const subs = j.subs || j.items || [];
        list.innerHTML = subs.map(s => {
          const p = typeof s === 'string' ? s : (s.path || s.name || '');
          const n = typeof s === 'string' ? s : (s.name || s.path || '');
          return `<li data-path="${p}">${n}</li>`;
        }).join('');
      } catch (e) {
        list.innerHTML = '<li>目录列举失败</li>';
      }
    }
    list.onclick = e => { const p = e.target?.dataset?.path; if (p) { cwd = p; refresh(); } };
    $('#dirUp').onclick = () => {
      if (/^[A-Za-z]:[\\/]/.test(cwd)) {
        const norm = cwd.replace(/\\+/g, '/'); const idx = norm.lastIndexOf('/');
        cwd = idx > 2 ? norm.slice(0, idx) : norm.slice(0, 3);
      } else {
        const parts = cwd.split('/').filter(Boolean); parts.pop(); cwd = '/' + parts.join('/');
      }
      refresh();
    };
    $('#dirOk').onclick = () => { $('#dir').value = cwd; modal.style.display = 'none'; };
    $('#dirClose').onclick = () => { modal.style.display = 'none'; };
    modal.style.display = 'block'; refresh();
  }

  function renderRows(payload, selectedExts) {
    const tbody = $('#tbl tbody'); if (!tbody) return;
    tbody.innerHTML = '';
    const rows = Array.isArray(payload?.data) ? payload.data : (Array.isArray(payload?.items) ? payload.items : []);
    rows.forEach(it => {
      const ext = getExt(it); if (selectedExts.length && !selectedExts.includes(ext)) return;
      const full = getFullPath(it);
      const dir = it.dir_path || it.dir || it.directory || it.path_dir || '';
      const sizeKB = humanKBFromAny(it.size_kb ?? it.sizeKB ?? it.size_bytes ?? it.size ?? it.bytes);
      const mtime = parseMTime(it);
      const tr = document.createElement('tr');
      const previewDisabled = (it.category === 'VIDEO' && !features.enable_video_preview) || (it.category === 'AUDIO' && !features.enable_audio_preview);
      const kw = Array.isArray(it.keywords) ? it.keywords.join('，') : (it.keywords || '');
      tr.innerHTML = `<td><input type="checkbox" class="ck" data-path="${full}"></td>
        <td>${it.name || it.filename || ''}</td>
        <td>${dir}</td>
        <td>${ext}</td>
        <td>${it.category || ''}</td>
        <td>${sizeKB}</td>
        <td>${mtime}</td>
        <td class="kw">${kw}</td>
        <td class="norm"></td>
        <td><input class="mv" placeholder="新完整路径" disabled></td>
        <td><input class="rn" placeholder="新文件名" disabled></td>
        <td><button class="btn btn-sm pv" ${previewDisabled ? 'disabled' : ''} data-path="${full}" data-ext="${ext}" data-cat="${it.category || ''}">预览</button></td>`;
      const ck = tr.querySelector('.ck');
      ck.addEventListener('change', () => {
        updateRowInputs();
        // Update select-all checkbox state
        const allChecked = $$('#tbl tbody .ck').every(cb => cb.checked);
        const anyChecked = $$('#tbl tbody .ck').some(cb => cb.checked);
        const selectAll = $('#selectAll');
        if (selectAll) {
          selectAll.checked = allChecked;
          selectAll.indeterminate = !allChecked && anyChecked;
        }
      });
      tbody.appendChild(tr);
    });
    updateRowInputs();
  }

  // ---------- 搜索与过滤 ----------

  function highlightText(text, kw) {
    if (!text) return '';
    let html = String(text);
    const words = (kw || '').split(/\s+/).filter(Boolean);
    words.forEach(w => {
      const re = new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      html = html.replace(re, m => `<mark>${m}</mark>`);
    });
    return html;
  }

  function isImageResult(it) {
    const p = String(it.path || it.full || it.fullpath || '');
    const cat = String(it.category || it.cat || it.type || '').toUpperCase();
    return /\.(jpg|jpeg|gif|png|tif|tiff|bmp|webp)$/i.test(p) || cat === 'IMAGE';
  }

  function renderSearchResults(res) {
    const area = $('#searchResults');
    if (!area) return;
    const items = Array.isArray(res?.data) ? res.data : (Array.isArray(res?.items) ? res.items : []);
    area.innerHTML = '';
    items.forEach(it => {
      const content = it.document || it.text || it.content || '';
      const name = it.name || it.filename || it.path?.split(/[\\\/]/).pop() || 'Untitled';
      const path = it.path || it.full || it.fullpath || '';
      let html = highlightText(content, $('#searchInput')?.value || '');
      let extra = '';
      if (isImageResult(it)) {
        const sim = it.similarity ?? it.score ?? '';
        const near = Array.isArray(it.near_duplicates || it.nearDup) ? (it.near_duplicates || it.nearDup) : [];
        const fold = near.length ? `<details><summary>近重复(${near.length})</summary>${near.map(n => `<div>${n.path || n}</div>`).join('')}</details>` : '';
        extra = `<div class="img-extra">相似度:${sim} ${fold}</div>`;
      }
      area.innerHTML += `
        <div class="result-item">
          <div class="result-name">${name}</div>
          <div class="result-path">${path}</div>
          ${extra}
          <div class="result-text">${html}</div>
        </div>`;
    });
  }

  async function doSearch() {
    const q = $('#searchInput')?.value || '';
    const k = parseInt($('#searchK')?.value) || 5;
    const channels = []; if ($('#chkVector')?.checked) channels.push('vector'); if ($('#chkFull')?.checked) channels.push('fulltext'); if ($('#chkRegex')?.checked) channels.push('regex');
    const body = { q, k, channels };
    if (filterWhere) body.where = filterWhere;
    if (filterWhereDoc) body.where_document = filterWhereDoc;
    toggleLoading(true, '搜索中…');
    try {
      const r = await fetch('/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await r.json();
      renderSearchResults(j);
    } catch (e) {
      console.warn('search failed', e);
      const area = $('#searchResults'); if (area) area.textContent = '搜索失败';
    }
    toggleLoading(false);
  }

  function openFilterModal() {
    $('#whereInput').value = filterWhere ? JSON.stringify(filterWhere, null, 2) : '';
    $('#whereDocInput').value = filterWhereDoc ? JSON.stringify(filterWhereDoc, null, 2) : '';
    $('#filterModal').style.display = 'block';
  }
  function closeFilterModal() { $('#filterModal').style.display = 'none'; }
  function applyFilterModal() {
    try { const txt = $('#whereInput').value.trim(); filterWhere = txt ? JSON.parse(txt) : null; } catch (e) { alert('where JSON 无效'); return; }
    try { const txt2 = $('#whereDocInput').value.trim(); filterWhereDoc = txt2 ? JSON.parse(txt2) : null; } catch (e) { alert('where_document JSON 无效'); return; }
    closeFilterModal();
  }

  function applyFeatureToggles(s) {
    const defaults = {
      enable_text: true, enable_data: true, enable_slides: true, enable_pdf: true,
      enable_archive: true, enable_image: true, enable_video: true, enable_audio: true,
      enable_ai_keywords: true, enable_move: true, enable_rename: true, enable_delete: true
    };
    features = Object.assign({}, defaults, s.features || {});
    const map = { TEXT: 'enable_text', DATA: 'enable_data', SLIDES: 'enable_slides', PDF: 'enable_pdf', ARCHIVE: 'enable_archive', IMAGE: 'enable_image', VIDEO: 'enable_video', AUDIO: 'enable_audio' };
    Object.entries(map).forEach(([cat, key]) => {
      const opt = $(`#category option[value="${cat}"]`);
      if (opt) opt.disabled = features[key] === false;
    });
    if (!features.enable_ai_keywords) {
      $('#kw_len')?.setAttribute('disabled', 'disabled');
      $('#kwSeeds')?.setAttribute('disabled', 'disabled');
      $('#kwStrategy')?.setAttribute('disabled', 'disabled');
      $('#kwOnlyEmpty')?.setAttribute('disabled', 'disabled');
      $('#genKwBtn')?.setAttribute('disabled', 'disabled');
      $('#aiRefineBtn')?.setAttribute('disabled', 'disabled');
      $('#clearKwBtn')?.setAttribute('disabled', 'disabled');
      $('#btnImgKW')?.setAttribute('disabled', 'disabled');
    }
    if (!features.enable_move) { $('#applyMoveBtn').disabled = true; }
    if (!features.enable_rename) { $('#applyRenameBtn').disabled = true; }
    if (!features.enable_delete) { $('#applyDeleteBtn').disabled = true; }
  }

  async function updateAIFields() {
    const p = $('#aiProvider')?.value;
    const url = $('#aiUrl'); const key = $('#aiApiKey');
    const urlDiv = url?.parentElement; const keyDiv = key?.parentElement; const modelSel = $('#aiModel');
    if (keyDiv) keyDiv.style.display = (p === 'ollama') ? 'none' : 'block';
    if (urlDiv) urlDiv.style.display = 'block';
    if (p === 'deepseek') { if (url) url.required = true; if (key) key.required = true; }
    else if (p === 'chatgpt') { if (url) url.required = false; if (key) key.required = true; }
    else { if (url) url.required = false; if (key) key.required = false; }
    if (modelSel) {
      const prev = modelSel.value; modelSel.innerHTML = ''; let models = [];
      if (p === 'ollama') {
        try { const r = await fetch('/api/ai/ollama/models', { credentials: 'include' }); const j = await r.json(); models = j.models || []; } catch (e) { models = []; }
      } else if (p === 'chatgpt') {
        models = ['gpt-3.5-turbo', 'gpt-4', 'gpt-4o'];
      } else if (p === 'deepseek') {
        models = ['deepseek-chat', 'deepseek-coder'];
      }
      models.forEach(m => { const o = document.createElement('option'); o.value = m; o.textContent = m; modelSel.appendChild(o); });
      if (prev) modelSel.value = prev;
    }
  }

  function applyKwFilter() {
    const kw = $('#kwFilter')?.value.trim();
    const terms = kw ? kw.split(/\s+/).filter(Boolean) : [];
    const rows = $$('#tbl tbody tr');
    rows.forEach(tr => {
      if (!terms.length) { tr.style.display = ''; return; }
      const text = tr.querySelector('.kw').textContent;
      const ok = terms.every(t => text.includes(t));
      tr.style.display = ok ? '' : 'none';
    });
    const visible = rows.filter(tr => tr.style.display !== 'none').length;
    const el = $('#pageinfo'); if (el) el.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${visible} 项`;
  }

  async function openSettings() {
    const res = await fetch('/full/settings', { credentials: 'include' });
    const s = await res.json();
    // 主题
    if (s.theme) { $$("input[name='theme']").forEach(r => r.checked = (r.value === s.theme)); }
    // AI
    $('#aiProvider').value = s.ai?.provider || 'ollama';
    $('#aiUrl').value = s.ai?.url || '';
    $('#aiApiKey').value = s.ai?.api_key || '';
    await updateAIFields();
    $('#aiModel').value = s.ai?.model || '';
    // 功能
    const f = s.features || {};
    $('#feat_text').checked = !!f.enable_text;
    $('#feat_data').checked = !!f.enable_data;
    $('#feat_slides').checked = !!f.enable_slides;
    $('#feat_pdf').checked = !!f.enable_pdf;
    $('#feat_archive').checked = !!f.enable_archive;
    $('#feat_image').checked = !!f.enable_image;
    $('#feat_video').checked = !!f.enable_video;
    $('#feat_audio').checked = !!f.enable_audio;
    $('#feat_ai_keywords').checked = !!f.enable_ai_keywords;
    $('#feat_move').checked = !!f.enable_move;
    $('#feat_rename').checked = !!f.enable_rename;
    $('#feat_delete').checked = !!f.enable_delete;
    $('#feat_image_caption').checked = !!f.enable_image_caption;
    $('#feat_video_preview').checked = !!f.enable_video_preview;
    $('#feat_audio_preview').checked = !!f.enable_audio_preview;
    // 显示
    $('#aiProvider').addEventListener('change', updateAIFields);
    $('#settingsModal').style.display = 'flex';
  }

  async function saveSettings() {
    const payload = {
      theme: ($$("input[name='theme']:checked")[0]?.value) || 'system',
      ai: {
        provider: $('#aiProvider').value,
        url: $('#aiUrl').value.trim(),
        api_key: $('#aiApiKey').value.trim(),
        model: $('#aiModel').value
      },
      features: {
        enable_text: $('#feat_text').checked,
        enable_data: $('#feat_data').checked,
        enable_slides: $('#feat_slides').checked,
        enable_pdf: $('#feat_pdf').checked,
        enable_archive: $('#feat_archive').checked,
        enable_image: $('#feat_image').checked,
        enable_video: $('#feat_video').checked,
        enable_audio: $('#feat_audio').checked,
        enable_ai_keywords: $('#feat_ai_keywords').checked,
        enable_move: $('#feat_move').checked,
        enable_rename: $('#feat_rename').checked,
        enable_delete: $('#feat_delete').checked,
        enable_image_caption: $('#feat_image_caption').checked,
        enable_video_preview: $('#feat_video_preview').checked,
        enable_audio_preview: $('#feat_audio_preview').checked
      }
    };
    await fetch('/full/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(payload) });
    applyTheme(payload.theme);
    applyFeatureToggles(payload);
    alert('已保存');
    $('#settingsModal').style.display = 'none';
    // location.reload(); // Removed reload for smoother experience
  }

  function onExport() {
    if (!lastQuery) { customConfirm('请先扫描'); return; }
    const { dir, withHash, recur, cat, exts } = lastQuery;
    const url = `${PATHS.exportCSV[0]}?dir=${qs(dir)}&hash=${withHash}&recursive=${recur}&category=${qs(cat)}&types=${qs(exts)}`;
    window.open(url, '_blank');
  }

  async function loadPage(page) {
    if (!lastQuery) return;
    currentPage = page;
    const { dir, recur, pageSize, exts, cat, q, withHash } = lastQuery;
    const params = `dir=${qs(dir)}&recursive=${recur}&page=${page}&page_size=${pageSize}&category=${qs(cat)}&types=${qs(exts)}&hash=${withHash}&q=${qs(q)}`;
    const candidates = PATHS.scan.map(b => `${b}?${params}`);
    toggleLoading(true, '正在扫描文件…');
    const res = await firstOK(candidates);
    toggleLoading(false);
    if (!res.ok) { alert('扫描失败'); return; }
    const j = await res.r.json();
    if (j.ok === false) { alert('扫描失败：' + (j.error || '')); return; }
    renderRows(j, exts ? exts.split(',').filter(Boolean) : []);
    total = j.total || 0; totalPages = Math.max(1, Math.ceil(total / pageSize));
    $('#count').textContent = `扫描结果：共 ${total} 项，共 ${totalPages} 页`;
    $('#pageinfo').textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${$('#tbl tbody').querySelectorAll('tr').length} 项`;
    $('#prev').disabled = currentPage <= 1; $('#next').disabled = currentPage >= totalPages;
  }

  async function onScan() {
    const dir = $('#dir')?.value || '';
    if (!dir) { alert('请先选择目录'); return; }
    lastQuery = {
      dir,
      recur: $('#recur')?.checked ? 1 : 0,
      pageSize: Number($('#page_size')?.value || 500) || 500,
      exts: Array.from($('#types')?.selectedOptions || []).map(o => o.value.toLowerCase()).join(','),
      cat: $('#category')?.value || '',
      q: $('#q')?.value || '',
      withHash: $('#hash')?.checked ? 1 : 0
    };
    await loadPage(1);
    // Enable save to database button after scan
    const saveBtn = $('#saveToDbBtn');
    if (saveBtn) saveBtn.disabled = false;
  }

  async function onSaveToDb() {
    if (!lastQuery) { customConfirm('请先进行扫描').then(() => { }); return; }
    const { dir, recur, cat, exts, withHash } = lastQuery;
    const params = `dir=${qs(dir)}&recursive=${recur}&category=${qs(cat)}&types=${qs(exts)}&hash=${withHash}`;
    const go = await customConfirm(`确认将当前扫描结果保存到 PostgreSQL 数据库？`);
    if (!go) return;

    toggleLoading(true, '正在保存到数据库…');
    try {
      const res = await fetch(`/full/save_to_db?${params}`, { method: 'POST', credentials: 'include' });
      const j = await res.json();
      if (!j.ok) {
        customConfirm(`保存失败：${j.error || '未知错误'}`).then(() => { });
      } else {
        customConfirm(`${j.message || '保存成功'}`).then(() => { });
      }
    } catch (e) {
      customConfirm(`保存失败：${e.message}`).then(() => { });
    }
    toggleLoading(false);
  }

  async function onApplyOps(action) {
    const selected = $$('#tbl tbody .ck:checked');
    if (selected.length === 0) { customConfirm('请选择要操作的文件').then(() => { }); return; }
    const ops = [];
    let msg = '';
    if (action === 'delete') {
      msg = `确认删除 ${selected.length} 个文件吗？此操作会移入回收站。`;
      selected.forEach(cb => ops.push({ action: 'delete', path: cb.dataset.path }));
    } else if (action === 'move') {
      msg = `确认移动 ${selected.length} 个文件吗？`;
      selected.forEach(cb => {
        const dstFull = cb.closest('tr').querySelector('.mv').value.trim();
        if (dstFull) ops.push({ action: 'move', src: cb.dataset.path, dst: dstFull });
      });
    } else if (action === 'rename') {
      msg = `确认重命名 ${selected.length} 个文件吗？`;
      selected.forEach(cb => { const newName = cb.closest('tr').querySelector('.rn').value.trim(); if (newName) ops.push({ action: 'rename', src: cb.dataset.path, new_name: newName }); });
    }
    if (!ops.length) { customConfirm('没有有效的操作参数').then(() => { }); return; }
    const go = await customConfirm(msg); if (!go) return;
    toggleLoading(true, '正在执行操作…');
    const res = await firstOK(PATHS.applyOps, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ops }) });
    toggleLoading(false);
    if (!res.ok) { customConfirm('操作失败：' + res.error).then(() => { }); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm('操作失败：' + (j.error || '')).then(() => { }); return; }
    await loadPage(currentPage);
    customConfirm(`完成 ${j.done} 项${j.errors?.length ? `，失败 ${j.errors.length} 项` : ''}`).then(() => { });
  }
  async function onNormalize() {
    const selected = $("#tbl tbody .ck:checked");
    if (selected.length === 0) { customConfirm("请选择要规范化的文件").then(() => { }); return; }
    const files = selected.map(cb => cb.dataset.path);
    const strategy = $("#normStrategy")?.value || "fallback";
    const toSourceDir = $("#normToSourceDir")?.checked;
    const output_mode = toSourceDir ? "source_dir" : "centralized";

    toggleLoading(true, "正在规范化…");
    const res = await firstOK(PATHS.normalize, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files, on_unsupported: strategy, output_mode })
    });
    toggleLoading(false);
    if (!res.ok) { customConfirm("规范化失败：" + res.error).then(() => { }); return; }
    const j = await res.r.json();
    (j.results || []).forEach(r => {
      const cb = document.querySelector(`#tbl tbody .ck[data-path="${CSS.escape(r.path)}"]`);
      if (cb) {
        const cell = cb.closest("tr").querySelector(".norm");
        if (r.ok) { cell.textContent = "✔"; }
        else if (r.message === "unsupported") { cell.textContent = "⏭"; }
        else { cell.textContent = "✖"; }
        cell.title = (r.out_dir || "") + "\n" + (r.sidecar || "");
      }
    });
  }



  async function genKw(forceLLM = false) {
    const selected = $$('#tbl tbody .ck:checked');
    if (selected.length === 0) { customConfirm('请选择要提取关键词的文件').then(() => { }); return; }

    const onlyEmpty = $('#kwOnlyEmpty')?.checked;
    const forceReprocess = $('#kwForceReprocess')?.checked;

    // Filter targets based on options
    const targets = selected.filter(cb => {
      const kw = cb.closest('tr').querySelector('.kw').textContent.trim();

      // If force reprocess is enabled, process all selected files
      if (forceReprocess) return true;

      // Otherwise, only process empty if that option is checked
      return !onlyEmpty || !kw;
    });

    if (targets.length === 0) {
      const msg = forceReprocess ? '没有选中文件' : '所有选中文件都已有关键词，请勾选"强制重新处理"';
      customConfirm(msg).then(() => { });
      return;
    }

    const paths = targets.map(cb => cb.dataset.path);
    let seeds = $('#kwSeeds')?.value || '';
    seeds = seeds.replace(/[；;]/g, ',').split(',').map(s => s.trim()).filter(Boolean);
    seeds = Array.from(new Set(seeds)).join(',');
    const strategy = $('#kwStrategy')?.value || 'hybrid';
    const kwLen = parseInt($('#kw_len')?.value) || 50;
    toggleLoading(true, '正在提取关键词…');
    const body = { paths, seeds, strategy, force_llm: !!forceLLM, max_chars: kwLen };
    const res = await firstOK(PATHS.kw, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    toggleLoading(false);
    if (!res.ok) { customConfirm('提取失败：' + res.error).then(() => { }); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm('提取失败：' + (j.error || '')).then(() => { }); return; }
    targets.forEach(cb => {
      const kw = j.keywords?.[cb.dataset.path] || [];
      const text = Array.isArray(kw) ? kw.join('，') : kw;
      cb.closest('tr').querySelector('.kw').textContent = text;
    });
    customConfirm(`成功提取 ${Object.keys(j.keywords || {}).length} 个文件的关键词`).then(() => { });
  }

  async function genImgKw() {
    const selected = $$('#tbl tbody .ck:checked');
    if (selected.length === 0) { customConfirm('请先选择图像文件').then(() => { }); return; }
    const paths = selected.map(cb => cb.dataset.path).filter(Boolean);
    if (!paths.length) { customConfirm('未找到文件路径').then(() => { }); return; }
    toggleLoading(true, '正在提取图片关键词…');
    const res = await firstOK(PATHS.imgKw, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths }) });
    toggleLoading(false);
    if (!res.ok) { customConfirm('提取失败：' + res.error).then(() => { }); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm('提取失败：' + (j.error || '')).then(() => { }); return; }
    let okCnt = 0; const fails = [];
    selected.forEach(cb => {
      const info = j.keywords?.[cb.dataset.path];
      const cell = cb.closest('tr')?.querySelector('.kw');
      if (!info) return;
      if (info.ok === false) {
        fails.push(info.error || '');
        if (cell) cell.textContent = '';
      } else {
        okCnt++;
        const kw = info.keywords || [];
        if (cell) cell.textContent = Array.isArray(kw) ? kw.join('，') : kw;
      }
    });
    const failMsg = fails.length ? `，失败 ${fails.length} 个：${fails.join('；')}` : '';
    customConfirm(`提取完成：${okCnt} 个文件${failMsg}`).then(() => { });
  }

  async function onClearKw() {
    const selected = $$('#tbl tbody .ck:checked');
    if (selected.length === 0) { customConfirm('请选择要清除关键词的文件').then(() => { }); return; }
    const paths = selected.map(cb => cb.dataset.path);
    const go = await customConfirm(`确认清除 ${paths.length} 个文件的关键词吗？`); if (!go) return;
    toggleLoading(true, '正在清除关键词…');
    const res = await firstOK(PATHS.clearKW, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths }) });
    toggleLoading(false);
    if (!res.ok) { customConfirm('清除失败：' + res.error).then(() => { }); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm('清除失败：' + (j.error || '')).then(() => { }); return; }
    selected.forEach(cb => cb.closest('tr').querySelector('.kw').textContent = '');
    customConfirm(`已清除 ${j.cleared || 0} 条关键词`).then(() => { });
  }

  function onPreview(e) {
    if (!e.target.classList.contains('pv')) return;
    const btn = e.target;
    const path = btn.dataset.path; const cat = btn.dataset.cat || '';
    let content = '';
    if (cat === 'IMAGE') { content = `<img src="/full/thumb?path=${qs(path)}" alt="图片预览">`; }
    else if (cat === 'VIDEO') { content = `<video controls width="100%"><source src="/full/file?path=${qs(path)}"></video>`; }
    else if (cat === 'AUDIO') { content = `<audio controls><source src="/full/file?path=${qs(path)}"></audio>`; }
    else if (['PDF', 'TEXT', 'SLIDES', 'DATA'].includes(cat)) {
      content = `<iframe src="/full/file?path=${qs(path)}" width="100%" height="420" style="border:none;"></iframe>`;
    } else { content = '<p>该文件类型不支持预览。</p>'; }
    customPreview(path.split(/[\\/]/).pop(), content);
  }

  // ---------- init & binds ----------
  document.addEventListener('DOMContentLoaded', async () => {
    // 读设置，应用功能开关
    try {
      const res = await fetch('/full/settings', { credentials: 'include' });
      const s = await res.json();
      applyFeatureToggles(s || {});
      if (s.theme) applyTheme(s.theme);
    } catch (e) {
      console.warn('读取设置失败', e);
      applyFeatureToggles({});
      applyTheme('system');
    }

    fillTypes();
    bind('#category', 'change', fillTypes);
    bind('#pickDir', 'click', showDirModal);
    bind('#scanBtn', 'click', onScan);
    bind('#saveToDbBtn', 'click', onSaveToDb);
    bind('#prev', 'click', () => { if (currentPage > 1) loadPage(currentPage - 1); });
    bind('#next', 'click', () => { if (currentPage < totalPages) loadPage(currentPage + 1); });
    bind('#exportBtn', 'click', onExport);
    bind('#normalizeBtn', 'click', onNormalize);
    bind('#kwFilterBtn', 'click', applyKwFilter);
    bind('#kwFilter', 'keyup', (e) => { if (e.key === 'Enter') applyKwFilter(); });

    bind('#searchBtn', 'click', doSearch);
    bind('#searchInput', 'keyup', (e) => { if (e.key === 'Enter') doSearch(); });
    bind('#filterBuilderBtn', 'click', openFilterModal);
    bind('#filterOk', 'click', applyFilterModal);
    bind('#filterClose', 'click', closeFilterModal);

    bind('#genKwBtn', 'click', () => genKw(false));
    bind('#aiRefineBtn', 'click', () => genKw(true));
    bind('#clearKwBtn', 'click', onClearKw);
    bind('#btnImgKW', 'click', genImgKw);
    bind('#applyMoveBtn', 'click', () => {
      if (opMode !== 'move') {
        setOpMode('move');
        alert('已进入批量移动模式，请勾选文件并修改“移动目标”，再点击“执行移动”');
      } else {
        setOpMode(null);
        onApplyOps('move');
      }
    });
    bind('#applyRenameBtn', 'click', () => {
      if (opMode !== 'rename') {
        setOpMode('rename');
        alert('已进入批量重命名模式，请勾选文件并修改“重命名为”，再点击“执行重命名”');
      } else {
        setOpMode(null);
        onApplyOps('rename');
      }
    });
    bind('#applyDeleteBtn', 'click', () => {
      if (opMode !== 'delete') {
        setOpMode('delete');
        alert('已进入批量删除模式，请勾选文件，再点击“执行删除”');
      } else {
        setOpMode(null);
        onApplyOps('delete');
      }
    })
    $('#tbl')?.addEventListener('click', onPreview);

    // Select-all checkbox functionality
    bind('#selectAll', 'change', (e) => {
      const checked = e.target.checked;
      $$('#tbl tbody .ck').forEach(cb => {
        cb.checked = checked;
      });
      updateRowInputs();
    });

    bind('#kw_len', 'input', (e) => {
      const val = e.target.value;
      const display = $('#kw_len_val');
      if (display) display.textContent = val;
    });


    // 顶栏：设置 / 登录 / 登出 / 用户名
    const userTools = $('#userTools');
    const currentUser = document.body.dataset.user || '';
    if (userTools) {
      const settingsBtn = document.createElement('button');
      settingsBtn.className = 'btn btn-sm';
      settingsBtn.textContent = '⚙️ 设置';
      settingsBtn.onclick = openSettings;
      userTools.appendChild(settingsBtn);

      if (currentUser) {
        const userBadge = document.createElement('span');
        userBadge.textContent = `🟢 ${currentUser}`;
        userBadge.className = 'small';
        userBadge.style.marginLeft = '8px';
        userTools.appendChild(userBadge);

        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'btn btn-sm';
        logoutBtn.textContent = '退出';
        logoutBtn.style.marginLeft = '8px';
        logoutBtn.onclick = async () => { await fetch('/full/logout', { credentials: 'include' }); location.reload(); };
        userTools.appendChild(logoutBtn);
      } else {
        const loginBtn = document.createElement('button');
        loginBtn.className = 'btn btn-sm';
        loginBtn.textContent = '🔐 登录';
        loginBtn.style.marginLeft = '8px';
        loginBtn.onclick = () => { $('#loginModal').style.display = 'flex'; };
        userTools.appendChild(loginBtn);
      }
    }

    // 设置弹窗按钮
    bind('#settingsSave', 'click', saveSettings);
    bind('#settingsCancel', 'click', () => { $('#settingsModal').style.display = 'none'; });

    // 登录弹窗按钮
    bind('#loginConfirm', 'click', async () => {
      const username = $('#loginUser').value.trim();
      const password = $('#loginPass').value.trim();
      const res = await fetch('/full/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ username, password }) });
      const j = await res.json();
      if (j.ok) { alert('登录成功'); $('#loginModal').style.display = 'none'; location.reload(); }
      else { alert('登录失败：' + (j.error || '未知错误')); }
    });
    bind('#loginCancel', 'click', () => { $('#loginModal').style.display = 'none'; });
  });
})();

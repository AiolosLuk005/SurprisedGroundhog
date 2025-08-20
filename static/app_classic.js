// Classic UI fix 20250818d: batch ops + confirms + preview + /full/* paths
(function(){
  const TYPES={
    TEXT:["docx","doc","txt","md","rtf"],
    DATA:["xlsx","xlsm","xls","csv","tsv","xml","parquet"],
    SLIDES:["pptx","ppt"],
    PDF:["pdf"],
    ARCHIVE:["zip","rar","7z"],
    IMAGE:["jpg","jpeg","gif","png","tif","tiff","bmp","svg","webp"],
    VIDEO:["wmv","mp4","avi","mov","mkv"],
    AUDIO:["mp3","wav","m4a","flac"]
  };

  const $=s=>document.querySelector(s);
  const $$=s=>Array.from(document.querySelectorAll(s));
  const qs=v=>encodeURIComponent(v||"");

  function toggleLoading(on, msg){
    const el = $("#loading");
    if(!el) return;
    const txt = el.querySelector(".loading-text");
    if(txt) txt.textContent = msg || "正在处理，请稍候…";
    if(on) el.classList.add("show"); else el.classList.remove("show");
  }

  // ---- helpers ----
  function humanKBFromBytes(n){ if(n==null||isNaN(n))return ""; return (Number(n)/1024).toFixed(1); }
  function humanKBFromAny(v){
    if(v==null||v==="") return "";
    if(typeof v==="number") return humanKBFromBytes(v);
    const s=String(v).trim().toLowerCase();
    const m=s.match(/^(\d+(?:\.\d+)?)(kb|mb|gb|b)?$/i);
    if(m){ const num=parseFloat(m[1]); const unit=(m[2]||"b").toLowerCase();
      if(unit==="kb") return num.toFixed(1);
      if(unit==="mb") return (num*1024).toFixed(1);
      if(unit==="gb") return (num*1024*1024).toFixed(1);
      return humanKBFromBytes(num);
    }
    const n=parseFloat(s); if(!isNaN(n)) return humanKBFromBytes(n);
    return "";
  }
  function parseMTime(row){
    let v=row.mtime ?? row.mtime_ms ?? row.modified ?? row.modified_ms ?? row.mtime_ts ?? row.mtimeMs ?? null;
    if(v==null){
      const iso=row.mtime_iso||row.modified_iso||row.iso_time;
      if(iso){ try{ return new Date(iso).toLocaleString(); }catch(e){ return ""; } }
      return "";
    }
    if(typeof v==="string"){
      if(/^\d+(\.\d+)?$/.test(v)) v=parseFloat(v);
      else{ try{ return new Date(v).toLocaleString(); }catch(e){ return ""; } }
    }
    if(v>1e12) v=v/1000;
    try{ return new Date(v*1000).toLocaleString(); }catch(e){ return ""; }
  }
  function normJoin(dir,name){
    if(!dir&&!name) return "";
    let p=(dir?String(dir):"")+(dir&&name?(/[\\/]$/.test(dir)?"":"/"):"")+(name?String(name):"");
    if(/^[A-Za-z]:/.test(p)||/\\/.test(p)) p=p.replace(/\//g,"\\");
    return p;
  }
  function getFullPath(row){
    const full=row.full||row.fullpath||row.full_path||row.absolute||row.abspath||row.path;
    if(full) return String(full);
    const name=row.name||row.filename||row.base||row.basename||"";
    const dir=row.dir||row.directory||row.folder||row.parent||row.dirname||row.path_dir||row.dir_path;
    return normJoin(dir||"", name);
  }
  function getExt(row){
    let e=row.ext||row.extension||"";
    if(!e){
      const full=getFullPath(row);
      const i=String(full).lastIndexOf(".");
      if(i>=0) e=String(full).slice(i+1);
    }
    return (e||"").toLowerCase();
  }

  // ---- endpoints ----
  const PATHS={
    scan:["/full/scan"],
    exportCSV:["/full/export_csv"],
    importSQL:["/full/import_mysql"],
    kw:["/full/keywords","/full/kw"],
    clearKW:["/full/clear_keywords"],
    applyOps:["/full/apply_ops"],
    ls:["/ls"] // 会被统一入口重写到 /full/ls
  };
  let lastQuery=null;
  let currentPage=1;
  let totalPages=1;
  async function firstOK(urls,opts){
    let lastErr=null;
    for(const u of urls){
      try{
        const r=await fetch(u,Object.assign({cache:"no-store"},opts||{}));
        if(r.ok) return {ok:true,u,r};
        lastErr=new Error("HTTP "+r.status);
      }catch(e){ lastErr=e; }
    }
    return {ok:false,error:lastErr};
  }

  // ---- confirms & preview ----
  function customConfirm(message) {
    return new Promise((resolve) => {
      const modal = $('#confirmModal');
      $('#confirmMessage').textContent = message;
      modal.style.display = 'flex';
      const onConfirm = () => { modal.style.display = 'none'; resolve(true); };
      const onCancel  = () => { modal.style.display = 'none'; resolve(false); };
      $('#confirmOk').onclick = onConfirm;
      $('#confirmCancel').onclick = onCancel;
    });
  }
  function customPreview(title, content) {
    const modal = $('#previewModal');
    $('#previewTitle').textContent = title;
    $('#previewContent').innerHTML = content;
    modal.style.display = 'flex';
    $('#previewClose').onclick = () => {
      modal.style.display = 'none';
      $('#previewContent').innerHTML = '';
    };
  }

  // ---- UI helpers ----
  function fillTypes(){
    const cat=$("#category"), types=$("#types");
    if(!cat||!types) return;
    types.innerHTML="";
    (TYPES[cat.value]||[]).forEach(ext=>{
      const o=document.createElement("option"); o.value=ext; o.textContent=ext; types.appendChild(o);
    });
  }

  function showDirModal(){
    const modal=$("#dirModal"), here=$("#dirHere"), list=$("#dirList");
    let cwd=$("#dir").value||"";
    async function refresh(){
      here.textContent=cwd||"(根)";
      const urls=PATHS.ls.map(u=>u+(cwd?("?dir="+qs(cwd)):""));
      toggleLoading(true, "读取目录…");
      const res=await firstOK(urls);
      toggleLoading(false);
      if(!res.ok){ list.innerHTML="<li>目录列举失败</li>"; return; }
      try{
        const j=await res.r.json();
        const subs=j.subs||j.items||[];
        list.innerHTML=subs.map(s=>`<li data-path="${s}">${s}</li>`).join("");
      }catch(e){ list.innerHTML="<li>目录列举失败</li>"; }
    }
    list.onclick=(e)=>{ const p=e.target?.dataset?.path; if(p){ cwd=p; refresh(); } };
    $("#dirUp").onclick=()=>{
      if(/^[A-Za-z]:[\\/]/.test(cwd)){
        const norm=cwd.replace(/\\+/g,"/"); const idx=norm.lastIndexOf("/");
        cwd=idx>2 ? norm.slice(0,idx) : norm.slice(0,3);
      }else{
        const parts=cwd.split("/").filter(Boolean); parts.pop(); cwd="/"+parts.join("/");
      }
      refresh();
    };
    $("#dirOk").onclick=()=>{ $("#dir").value=cwd; modal.style.display="none"; };
    $("#dirClose").onclick=()=>{ modal.style.display="none"; };
    modal.style.display="block"; refresh();
  }

  // ---- core actions ----
  async function loadPage(page){
    if(!lastQuery) return;
    const {dir,recur,pageSize,exts,cat,q,withHash}=lastQuery;
    const params=`dir=${qs(dir)}&hash=${withHash}&recursive=${recur}&page=${page}&page_size=${pageSize}&category=${qs(cat)}&types=${qs(exts)}&q=${qs(q)}`;
    const candidates=PATHS.scan.map(b=>`${b}?${params}`);
    toggleLoading(true, "正在扫描文件…");
    const res=await firstOK(candidates);
    toggleLoading(false);
    if(!res.ok){ customConfirm("扫描失败："+(res.error?res.error.message:"接口不可用")).then(()=>{}); return; }
    let j=null;
    try{ j=await res.r.json(); }catch(e){ customConfirm("响应解析失败").then(()=>{}); return; }
    if(!j || !j.ok){ customConfirm("接口返回错误").then(()=>{}); return; }
    const selected=exts?exts.split(","):[];
    renderRows(j, selected);
    applyKwFilter();
    currentPage=page;
    const total=j.total||0;
    totalPages=Math.max(1, Math.ceil(total/pageSize));
    $("#count").textContent=`扫描结果：共 ${total} 项，共 ${totalPages} 页`;
    $("#pageinfo").textContent=`第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${($$("#tbl tbody tr").length)} 项`;
    $("#prev").disabled=currentPage<=1;
    $("#next").disabled=currentPage>=totalPages;
  }

  async function onScan(){
    const dir=($("#dir")?.value||"").trim(); if(!dir){ customConfirm("请选择扫描目录").then(()=>{}); return; }
    lastQuery={
      dir,
      recur:$("#recur")?.checked?1:0,
      pageSize:Number($("#page_size")?.value||500)||500,
      exts:Array.from($("#types")?.selectedOptions||[]).map(o=>o.value.toLowerCase()).join(","),
      cat:$("#category")?.value||"",
      q:$("#q")?.value||"",
      withHash:$("#hash")?.checked?1:0
    };
    await loadPage(1);
  }

  function renderRows(payload, selectedExts){
    const tbody=$("#tbl tbody"); if(!tbody) return;
    tbody.innerHTML="";
    const rows=Array.isArray(payload?.data)?payload.data: Array.isArray(payload?.items)?payload.items: [];
    rows.forEach(it=>{
      const ext=getExt(it);
      if(selectedExts.length && !selectedExts.includes(ext)) return;
      const full=getFullPath(it);
      const dir=it.dir_path||it.dir||it.directory||it.path_dir||"";
      const sizeKB=humanKBFromAny(it.size_kb ?? it.sizeKB ?? it.size_bytes ?? it.size ?? it.bytes);
      const mtime=parseMTime(it);
      const tr=document.createElement("tr");
      tr.innerHTML=`
        <td><input type="checkbox" class="ck" data-path="${full}"></td>
        <td>${it.name||it.filename||""}</td>
        <td>${dir}</td>
        <td>${ext}</td>
        <td>${it.category||""}</td>
        <td>${sizeKB}</td>
        <td>${mtime}</td>
        <td class="kw">${it.keywords||""}</td>
        <td><input class="mv" placeholder="目标目录"></td>
        <td><input class="rn" placeholder="新文件名"></td>
        <td><button class="btn btn-sm pv" data-path="${full}" data-ext="${ext}" data-cat="${it.category||''}">预览</button></td>`;
    tbody.appendChild(tr);
    });
  }

  function applyKwFilter(){
    const kw = $("#kwFilter")?.value.trim();
    const terms = kw ? kw.split(/\s+/).filter(Boolean) : [];
    const rows = $$("#tbl tbody tr");
    rows.forEach(tr=>{
      if(!terms.length){ tr.style.display=""; return; }
      const text = tr.querySelector('.kw').textContent;
      const ok = terms.every(t=>text.includes(t));
      tr.style.display = ok ? '' : 'none';
    });
    const visible = rows.filter(tr=>tr.style.display!=='none').length;
    $("#pageinfo")?.textContent=`第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${visible} 项`;
  }

  async function openSettings(){
    const res = await fetch('/full/settings');
    const s = await res.json();
    if(s.theme){ $$('input[name="theme"]').forEach(r=>r.checked=(r.value===s.theme)); }
    $('#aiProvider').value = s.ai?.provider || 'ollama';
    $('#apiKey').value = s.ai?.api_key || '';
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
    $('#settingsModal').style.display='flex';
  }

  async function saveSettings(){
    const payload={
      theme: ($$('input[name="theme"]:checked')[0]?.value)||'system',
      ai:{
        provider: $('#aiProvider').value,
        api_key: $('#apiKey').value.trim()
      },
      features:{
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
    await fetch('/full/settings', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    alert('已保存');
    $('#settingsModal').style.display='none';
  }

  function onExport(){
    if(!lastQuery){ customConfirm('请先扫描').then(()=>{}); return; }
    const {dir,withHash,recur,cat,exts}=lastQuery;
    const url=`${PATHS.exportCSV[0]}?dir=${qs(dir)}&hash=${withHash}&recursive=${recur}&category=${qs(cat)}&types=${qs(exts)}`;
    window.open(url,'_blank');
  }

  async function onApplyOps(action) {
    const selectedRows = $$('#tbl tbody .ck:checked');
    if (selectedRows.length === 0) { customConfirm("请选择要操作的文件。").then(() => {}); return; }

    const ops = [];
    let confirmMessage = "";

    if (action === 'delete') {
      confirmMessage = `确认删除 ${selectedRows.length} 个文件吗？此操作会移入回收站。`;
      selectedRows.forEach(cb => ops.push({ action: 'delete', path: cb.dataset.path }));
    } else if (action === 'move') {
      confirmMessage = `确认移动 ${selectedRows.length} 个文件吗？`;
      selectedRows.forEach(cb => {
        const row = cb.closest('tr');
        const dst = row.querySelector('.mv').value.trim();
        if (dst) ops.push({ action: 'move', src: cb.dataset.path, dst });
      });
    } else if (action === 'rename') {
      confirmMessage = `确认重命名 ${selectedRows.length} 个文件吗？`;
      selectedRows.forEach(cb => {
        const row = cb.closest('tr');
        const newName = row.querySelector('.rn').value.trim();
        if (newName) ops.push({ action: 'rename', src: cb.dataset.path, new_name: newName });
      });
    }

    if (ops.length === 0) { customConfirm("没有有效的操作数据。").then(() => {}); return; }

    const go = await customConfirm(confirmMessage);
    if (!go) return;

    toggleLoading(true, "正在执行批量操作…");
    const res = await firstOK(PATHS.applyOps, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ops })
    });
    toggleLoading(false);

    if (!res.ok) { customConfirm(`操作失败：${res.error.message}`).then(()=>{}); return; }
    const j = await res.r.json();
    customConfirm(`操作完成。成功 ${j.done} 个，失败 ${j.errors.length} 个。`).then(()=>{ if (j.errors.length) console.error(j.errors); });
  }

  async function onGenKw() {
    const selectedRows = $$('#tbl tbody .ck:checked');
    if (selectedRows.length === 0) { customConfirm("请选择要提取关键词的文件。").then(() => {}); return; }
    const paths = selectedRows.map(cb => cb.dataset.path);
    const maxLen = Math.min(200, Math.max(1, Number($("#kw_len")?.value||50)));

    toggleLoading(true, "正在提取关键词…");
    const res = await firstOK(PATHS.kw, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths, max_len: maxLen })
    });
    toggleLoading(false);

    if (!res.ok) { customConfirm(`提取失败：${res.error.message}`).then(()=>{}); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm(`提取失败：${j.error||'未知错误'}`).then(()=>{}); return; }

    selectedRows.forEach(cb => {
      const path = cb.dataset.path;
      const newKw = j.keywords?.[path] || "";
      cb.closest('tr').querySelector('.kw').textContent = newKw;
    });
    customConfirm(`成功提取 ${Object.keys(j.keywords||{}).length} 个文件的关键词。`).then(()=>{});
  }

  async function onClearKw(){
    const selectedRows = $$('#tbl tbody .ck:checked');
    if (selectedRows.length === 0) { customConfirm("请选择要清除关键词的文件。").then(() => {}); return; }
    const paths = selectedRows.map(cb => cb.dataset.path);
    const go = await customConfirm(`确认清除 ${paths.length} 个文件的关键词吗？`);
    if(!go) return;

    toggleLoading(true, "正在清除关键词…");
    const res = await firstOK(PATHS.clearKW, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    toggleLoading(false);

    if (!res.ok) { customConfirm(`清除失败：${res.error.message}`).then(()=>{}); return; }
    const j = await res.r.json();
    if (!j.ok) { customConfirm(`清除失败：${j.error||'未知错误'}`).then(()=>{}); return; }

    selectedRows.forEach(cb => cb.closest('tr').querySelector('.kw').textContent = "");
    customConfirm(`已清除 ${j.cleared||0} 条关键词。`).then(()=>{});
  }

  function onPreview(event) {
    const btn  = event.target;
    const path = btn.dataset.path;
    const ext  = btn.dataset.ext || "";
    const cat  = btn.dataset.cat || "";

    let content = "";
    if (cat === 'IMAGE') {
      content = `<img src="/full/thumb?path=${qs(path)}" alt="图片预览" />`;
    } else if (cat === 'VIDEO') {
      content = `<video controls width="100%"><source src="/full/file?path=${qs(path)}"></video>`;
    } else if (cat === 'AUDIO') {
      content = `<audio controls><source src="/full/file?path=${qs(path)}"></audio>`;
    } else if (cat === 'PDF' || cat === 'TEXT' || cat === 'SLIDES' || cat === 'DATA') {
      content = `
        <p>内容预览功能待完善，当前以内嵌方式打开原文件。</p>
        <iframe src="/full/file?path=${qs(path)}" width="100%" height="420" style="border:none;"></iframe>`;
    } else {
      content = `<p>该文件类型不支持预览。</p>`;
    }
    customPreview(path.split(/[\\/]/).pop(), content);
  }

  // ---- bind ----
  document.addEventListener("DOMContentLoaded", () => {
  fillTypes();
  $("#category")?.addEventListener("change", fillTypes);
  $("#pickDir")?.addEventListener("click", showDirModal);
  $("#scanBtn")?.addEventListener("click", onScan);
  $("#prev")?.addEventListener("click", ()=>{ if(currentPage>1) loadPage(currentPage-1); });
  $("#next")?.addEventListener("click", ()=>{ if(currentPage<totalPages) loadPage(currentPage+1); });
  $("#exportBtn")?.addEventListener("click", onExport);
  $("#kwFilterBtn")?.addEventListener("click", applyKwFilter);
  $("#kwFilter")?.addEventListener("input", (e)=>{ if(!e.target.value) applyKwFilter(); });

  // 批量操作
  $("#applyMoveBtn")?.addEventListener("click", () => onApplyOps('move'));
  $("#applyRenameBtn")?.addEventListener("click", () => onApplyOps('rename'));
  $("#applyDeleteBtn")?.addEventListener("click", () => onApplyOps('delete'));

  // 关键词
  $("#genKwBtn")?.addEventListener("click", onGenKw);
  $("#clearKwBtn")?.addEventListener("click", onClearKw);

  // 预览（委托）
  $('#tbl tbody')?.addEventListener('click', (e) => {
      if (e.target.classList.contains('pv')) onPreview(e);
  });

  const topbar = document.querySelector('.topbar');
  const settingsBtn = document.createElement('button');
  settingsBtn.textContent = '⚙️ 设置';
  settingsBtn.className = 'btn btn-sm';
  settingsBtn.style.marginLeft = '12px';
  settingsBtn.onclick = openSettings;
  topbar?.appendChild(settingsBtn);

  const user=document.body.dataset.user;
  if(user){
      const userSpan=document.createElement('span');
      userSpan.textContent=`👤 ${user}`;
      userSpan.style.marginLeft='12px';
      topbar?.appendChild(userSpan);
      const logoutBtn=document.createElement('button');
      logoutBtn.textContent='退出';
      logoutBtn.className='btn btn-sm';
      logoutBtn.style.marginLeft='8px';
      logoutBtn.onclick=async()=>{ await fetch('/full/logout'); location.reload(); };
      topbar?.appendChild(logoutBtn);
  }else{
      const loginBtn=document.createElement('button');
      loginBtn.textContent='🔐 登录';
      loginBtn.className='btn btn-sm';
      loginBtn.style.marginLeft='12px';
      loginBtn.onclick=()=>{ document.getElementById('loginModal').style.display='flex'; };
      topbar?.appendChild(loginBtn);
  }

  document.getElementById('settingsClose')?.addEventListener('click', () => {
      document.getElementById('settingsModal').style.display = 'none';
  });
  document.getElementById('settingsSave')?.addEventListener('click', saveSettings);

  document.getElementById('loginConfirm')?.addEventListener('click', async () => {
      const username = document.getElementById('loginUser').value.trim();
      const password = document.getElementById('loginPass').value.trim();
      const res = await fetch('/full/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const j = await res.json();
      if (j.ok) {
        alert('登录成功');
        document.getElementById('loginModal').style.display = 'none';
        location.reload();
      } else {
        alert('登录失败：' + (j.error || '未知错误'));
      }
  });

  document.getElementById('loginCancel')?.addEventListener('click', () => {
      document.getElementById('loginModal').style.display = 'none';
  });
  });
})();

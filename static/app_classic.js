// Classic UI enhanced 20250821: scanning, login, settings, AI models, ops
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

  const PATHS={
    scan:["/full/scan"],
    exportCSV:["/full/export_csv"],
    importSQL:["/full/import_mysql"],
    kw:["/full/keywords"],
    clearKW:["/full/clear_keywords"],
    applyOps:["/full/apply_ops"],
    ls:["/full/ls","/ls"]
  };

  const $=s=>document.querySelector(s);
  const $$=s=>Array.from(document.querySelectorAll(s));
  const qs=v=>encodeURIComponent(v||"");
  function firstDefined(){
    for(var i=0;i<arguments.length;i++){
      var val=arguments[i];
      if(val!==undefined && val!==null) return val;
    }
    return null;
  }
  function bind(sel,evt,fn){ var el=$(sel); if(el) el.addEventListener(evt,fn); return el; }

  let features={};
  let lastQuery=null;
  let currentPage=1,totalPages=1,total=0;

  function toggleLoading(on,msg){
    const el=$('#loading');
    if(!el) return;
    const txt=el.querySelector('.loading-text');
    if(txt) txt.textContent=msg||'正在处理，请稍候…';
    if(on) el.classList.add('show'); else el.classList.remove('show');
  }

  function humanKBFromBytes(n){ if(n==null||isNaN(n)) return ''; return (Number(n)/1024).toFixed(1); }
  function humanKBFromAny(v){
    if(v==null||v==='') return '';
    if(typeof v==='number') return humanKBFromBytes(v);
    const s=String(v).trim().toLowerCase();
    const m=s.match(/^(\d+(?:\.\d+)?)(kb|mb|gb|b)?$/i);
    if(m){ const num=parseFloat(m[1]); const unit=(m[2]||'b').toLowerCase();
      if(unit==='kb') return num.toFixed(1);
      if(unit==='mb') return (num*1024).toFixed(1);
      if(unit==='gb') return (num*1024*1024).toFixed(1);
      return humanKBFromBytes(num);
    }
    const n=parseFloat(s); if(!isNaN(n)) return humanKBFromBytes(n);
    return '';
  }
  function parseMTime(row){
    var v=firstDefined(row.mtime,row.mtime_ms,row.modified,row.modified_ms,row.mtime_ts,row.mtimeMs);
    if(v==null){
      var iso=row.mtime_iso||row.modified_iso||row.iso_time;
      if(iso){ try{return new Date(iso).toLocaleString();}catch(e){return '';}}
      return '';
    }
    if(typeof v==='string'){
      if(/^\d+(\.\d+)?$/.test(v)) v=parseFloat(v); else { try{return new Date(v).toLocaleString();}catch(e){return '';}}
    }
    if(v>1e12) v=v/1000;
    try{return new Date(v*1000).toLocaleString();}catch(e){return '';}
  }
  function normJoin(dir,name){
    if(!dir&&!name) return '';
    let p=(dir?String(dir):'')+(dir&&name?(/[\\/]$/.test(dir)?'':'/'):'')+(name?String(name):'');
    if(/^[A-Za-z]:/.test(p)||/\\/.test(p)) p=p.replace(/\//g,'\\');
    return p;
  }
  function getFullPath(row){
    const full=row.full||row.fullpath||row.full_path||row.absolute||row.abspath||row.path;
    if(full) return String(full);
    const name=row.name||row.filename||row.base||row.basename||'';
    const dir=row.dir||row.directory||row.folder||row.parent||row.dirname||row.path_dir||row.dir_path;
    return normJoin(dir||'',name);
  }
  function getExt(row){
    let e=row.ext||row.extension||'';
    if(!e){
      const full=getFullPath(row); const i=String(full).lastIndexOf('.'); if(i>=0) e=String(full).slice(i+1);
    }
    return (e||'').toLowerCase();
  }

  async function firstOK(urls,opts){
    let lastErr=null;
    for(const u of urls){
      try{
        const r=await fetch(u,Object.assign({cache:'no-store',credentials:'include'},opts||{}));
        if(r.ok) return {ok:true,r};
        lastErr=new Error('HTTP '+r.status);
      }catch(e){ lastErr=e; }
    }
    return {ok:false,error:lastErr};
  }

  function customConfirm(msg){
    return new Promise(resolve=>{
      const m=$('#confirmModal');
      $('#confirmMessage').textContent=msg;
      m.style.display='flex';
      const ok=()=>{m.style.display='none';resolve(true);};
      const no=()=>{m.style.display='none';resolve(false);};
      $('#confirmOk').onclick=ok; $('#confirmCancel').onclick=no;
    });
  }
  function customPreview(title,content){
    const m=$('#previewModal');
    $('#previewTitle').textContent=title;
    $('#previewContent').innerHTML=content;
    m.style.display='flex';
    $('#previewClose').onclick=()=>{m.style.display='none';$('#previewContent').innerHTML='';};
  }

  function fillTypes(){
    const cat=$('#category'), types=$('#types');
    if(!cat||!types) return;
    types.innerHTML='';
    (TYPES[cat.value]||[]).forEach(ext=>{
      const o=document.createElement('option'); o.value=ext; o.textContent=ext; types.appendChild(o);
    });
  }

  function showDirModal(){
    const modal=$('#dirModal'), here=$('#dirHere'), list=$('#dirList');
    let cwd=$('#dir').value||'';
    async function refresh(){
      here.textContent=cwd||'(根)';
      const urls=PATHS.ls.map(u=>u+(cwd?('?dir='+qs(cwd)):'') );
      toggleLoading(true,'读取目录…');
      const res=await firstOK(urls);
      toggleLoading(false);
      if(!res.ok){ list.innerHTML='<li>目录列举失败</li>'; return; }
      try{
        const j=await res.r.json();
        const subs=j.subs||j.items||[];
        list.innerHTML=subs.map(s=>`<li data-path="${s}">${s}</li>`).join('');
      }catch(e){ list.innerHTML='<li>目录列举失败</li>'; }
    }
    list.onclick=function(e){ var p=e.target && e.target.dataset ? e.target.dataset.path : null; if(p){ cwd=p; refresh(); } };
    $('#dirUp').onclick=()=>{
      if(/^[A-Za-z]:[\\/]/.test(cwd)){
        const norm=cwd.replace(/\\+/g,'/'); const idx=norm.lastIndexOf('/');
        cwd=idx>2?norm.slice(0,idx):norm.slice(0,3);
      }else{
        const parts=cwd.split('/').filter(Boolean); parts.pop(); cwd='/' + parts.join('/');
      }
      refresh();
    };
    $('#dirOk').onclick=()=>{ $('#dir').value=cwd; modal.style.display='none'; };
    $('#dirClose').onclick=()=>{ modal.style.display='none'; };
    modal.style.display='block'; refresh();
  }

  function renderRows(payload,selectedExts){
    const tbody=$('#tbl tbody'); if(!tbody) return;
    tbody.innerHTML='';
    var rows = Array.isArray(payload && payload.data) ? payload.data : (Array.isArray(payload && payload.items) ? payload.items : []);
    rows.forEach(function(it){
      const ext=getExt(it); if(selectedExts.length && !selectedExts.includes(ext)) return;
      const full=getFullPath(it);
      const dir=it.dir_path||it.dir||it.directory||it.path_dir||'';
      var sizeVal=firstDefined(it.size_kb,it.sizeKB,it.size_bytes,it.size,it.bytes);
      var sizeKB=humanKBFromAny(sizeVal);
      const mtime=parseMTime(it);
      const tr=document.createElement('tr');
      const previewDisabled=(it.category==='VIDEO'&&!features.enable_video_preview)||(it.category==='AUDIO'&&!features.enable_audio_preview);
      tr.innerHTML=`<td><input type="checkbox" class="ck" data-path="${full}"></td>
        <td>${it.name||it.filename||''}</td>
        <td>${dir}</td>
        <td>${ext}</td>
        <td>${it.category||''}</td>
        <td>${sizeKB}</td>
        <td>${mtime}</td>
        <td class="kw">${it.keywords||''}</td>
        <td><input class="mv" placeholder="目标目录" disabled></td>
        <td><input class="rn" placeholder="新文件名" disabled></td>
        <td><button class="btn btn-sm pv" ${previewDisabled?'disabled':''} data-path="${full}" data-ext="${ext}" data-cat="${it.category||''}">预览</button></td>`;
      const ck=tr.querySelector('.ck');
      const mv=tr.querySelector('.mv');
      const rn=tr.querySelector('.rn');
      ck.addEventListener('change',()=>{ mv.disabled=rn.disabled=!ck.checked; });
      tbody.appendChild(tr);
    });
  }

  function applyFeatureToggles(s){
    features=s.features||{};
    const map={TEXT:'enable_text',DATA:'enable_data',SLIDES:'enable_slides',PDF:'enable_pdf',ARCHIVE:'enable_archive',IMAGE:'enable_image',VIDEO:'enable_video',AUDIO:'enable_audio'};
    Object.entries(map).forEach(([cat,key])=>{ const opt=$(`#category option[value="${cat}"]`); if(opt) opt.disabled=!features[key]; });
    if(!features.enable_ai_keywords){ $('#kw_len').disabled=true; $('#genKwBtn').disabled=true; $('#clearKwBtn').disabled=true; }
    if(!features.enable_move){ $('#applyMoveBtn').disabled=true; }
    if(!features.enable_rename){ $('#applyRenameBtn').disabled=true; }
    if(!features.enable_delete){ $('#applyDeleteBtn').disabled=true; }
  }

  async function updateAIFields(){
    var provEl=$('#aiProvider');
    var p=provEl?provEl.value:'';
    var url=$('#aiUrl'); var key=$('#aiApiKey');
    var urlDiv=url?url.parentElement:null; var keyDiv=key?key.parentElement:null; var modelSel=$('#aiModel');
    if(keyDiv) keyDiv.style.display=(p==='ollama')?'none':'block';
    if(urlDiv) urlDiv.style.display='block';
    if(p==='deepseek'){ if(url) url.required=true; if(key) key.required=true; }
    else if(p==='chatgpt'){ if(url) url.required=false; if(key) key.required=true; }
    else { if(url) url.required=false; if(key) key.required=false; }
    if(modelSel){
      const prev=modelSel.value; modelSel.innerHTML=''; let models=[];
      if(p==='ollama'){
        try{ const r=await fetch('/api/ai/ollama/models',{credentials:'include'}); const j=await r.json(); models=j.models||[]; }catch(e){ models=[]; }
      }else if(p==='chatgpt'){
        models=['gpt-3.5-turbo','gpt-4','gpt-4o'];
      }else if(p==='deepseek'){
        models=['deepseek-chat','deepseek-coder'];
      }
      models.forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; modelSel.appendChild(o); });
      if(prev) modelSel.value=prev;
    }
  }

  function applyKwFilter(){
    var kwEl=$('#kwFilter');
    var kw=kwEl?kwEl.value.trim():'';
    var terms=kw?kw.split(/\s+/).filter(Boolean):[];
    const rows=$$('#tbl tbody tr');
    rows.forEach(tr=>{
      if(!terms.length){ tr.style.display=''; return; }
      const text=tr.querySelector('.kw').textContent;
      const ok=terms.every(t=>text.includes(t));
      tr.style.display=ok?'':'none';
    });
    const visible=rows.filter(tr=>tr.style.display!=='none').length;
    const el=$('#pageinfo'); if(el) el.textContent=`第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${visible} 项`;
  }

  async function openSettings(){
    const res=await fetch('/full/settings',{credentials:'include'});
    const s=await res.json();
    if(s.theme){ $$("input[name='theme']").forEach(r=>r.checked=(r.value===s.theme)); }
    $('#aiProvider').value=(s.ai && s.ai.provider)||'ollama';
    $('#aiUrl').value=(s.ai && s.ai.url)||'';
    $('#aiApiKey').value=(s.ai && s.ai.api_key)||'';
    await updateAIFields();
    $('#aiModel').value=(s.ai && s.ai.model)||'';
    const f=s.features||{};
    $('#feat_text').checked=!!f.enable_text;
    $('#feat_data').checked=!!f.enable_data;
    $('#feat_slides').checked=!!f.enable_slides;
    $('#feat_pdf').checked=!!f.enable_pdf;
    $('#feat_archive').checked=!!f.enable_archive;
    $('#feat_image').checked=!!f.enable_image;
    $('#feat_video').checked=!!f.enable_video;
    $('#feat_audio').checked=!!f.enable_audio;
    $('#feat_ai_keywords').checked=!!f.enable_ai_keywords;
    $('#feat_move').checked=!!f.enable_move;
    $('#feat_rename').checked=!!f.enable_rename;
    $('#feat_delete').checked=!!f.enable_delete;
    $('#feat_image_caption').checked=!!f.enable_image_caption;
    $('#feat_video_preview').checked=!!f.enable_video_preview;
    $('#feat_audio_preview').checked=!!f.enable_audio_preview;
    $('#aiProvider').addEventListener('change', updateAIFields);
    $('#settingsModal').style.display='flex';
  }

  async function saveSettings(){
    var themeInputs=$$("input[name='theme']:checked");
    var themeVal=themeInputs.length?themeInputs[0].value:'system';
    const payload={
      theme: themeVal,
      ai:{
        provider: $('#aiProvider').value,
        url: $('#aiUrl').value.trim(),
        api_key: $('#aiApiKey').value.trim(),
        model: $('#aiModel').value
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
    await fetch('/full/settings',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(payload)});
    alert('已保存');
    $('#settingsModal').style.display='none';
    location.reload();
  }

  function onExport(){
    if(!lastQuery){ customConfirm('请先扫描'); return; }
    const {dir,withHash,recur,cat,exts}=lastQuery;
    const url=`${PATHS.exportCSV[0]}?dir=${qs(dir)}&hash=${withHash}&recursive=${recur}&category=${qs(cat)}&types=${qs(exts)}`;
    window.open(url,'_blank');
  }

  async function loadPage(page){
    if(!lastQuery) return;
    currentPage=page;
    const {dir,recur,pageSize,exts,cat,q,withHash}=lastQuery;
    const params=`dir=${qs(dir)}&recursive=${recur}&page=${page}&page_size=${pageSize}&category=${qs(cat)}&types=${qs(exts)}&hash=${withHash}&q=${qs(q)}`;
    const candidates=PATHS.scan.map(b=>`${b}?${params}`);
    toggleLoading(true,'正在扫描文件…');
    const res=await firstOK(candidates);
    toggleLoading(false);
    if(!res.ok){ alert('扫描失败'); return; }
    const j=await res.r.json();
    if(j.ok===false){ alert('扫描失败：'+(j.error||'')); return; }
    renderRows(j, exts?exts.split(',').filter(Boolean):[]);
    total=j.total||0; totalPages=Math.max(1, Math.ceil(total/pageSize));
    $('#count').textContent=`扫描结果：共 ${total} 项，共 ${totalPages} 页`;
    $('#pageinfo').textContent=`第 ${currentPage} 页 / 共 ${totalPages} 页 · 本页 ${$('#tbl tbody').querySelectorAll('tr').length} 项`;
    $('#prev').disabled=currentPage<=1; $('#next').disabled=currentPage>=totalPages;
  }

  async function onScan(){
    var dirEl=$('#dir');
    var dir=dirEl?dirEl.value:'';
    if(!dir){ alert('请先选择目录'); return; }
    lastQuery={
      dir: dir,
      recur: (function(){ var el=$('#recur'); return el&&el.checked?1:0; })(),
      pageSize: Number((function(){ var el=$('#page_size'); return el?el.value:500; })())||500,
      exts: (function(){ var sel=$('#types'); return Array.from(sel?sel.selectedOptions:[]).map(function(o){return o.value.toLowerCase();}).join(','); })(),
      cat: (function(){ var el=$('#category'); return el?el.value:''; })(),
      q: (function(){ var el=$('#q'); return el?el.value:''; })(),
      withHash: (function(){ var el=$('#hash'); return el&&el.checked?1:0; })()
    };
    await loadPage(1);
  }

  async function onApplyOps(action){
    const selected=$$('#tbl tbody .ck:checked');
    if(selected.length===0){ customConfirm('请选择要操作的文件').then(()=>{}); return; }
    const ops=[];
    let msg='';
    if(action==='delete'){
      msg=`确认删除 ${selected.length} 个文件吗？此操作会移入回收站。`;
      selected.forEach(cb=>ops.push({action:'delete',path:cb.dataset.path}));
    }else if(action==='move'){
      msg=`确认移动 ${selected.length} 个文件吗？`;
      selected.forEach(cb=>{ const dst=cb.closest('tr').querySelector('.mv').value.trim(); if(dst) ops.push({action:'move',src:cb.dataset.path,dst}); });
    }else if(action==='rename'){
      msg=`确认重命名 ${selected.length} 个文件吗？`;
      selected.forEach(cb=>{ const newName=cb.closest('tr').querySelector('.rn').value.trim(); if(newName) ops.push({action:'rename',src:cb.dataset.path,new_name:newName}); });
    }
    if(!ops.length){ customConfirm('没有有效的操作参数').then(()=>{}); return; }
    const go=await customConfirm(msg); if(!go) return;
    toggleLoading(true,'正在执行操作…');
    const res=await firstOK(PATHS.applyOps,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ops})});
    toggleLoading(false);
    if(!res.ok){ customConfirm('操作失败：'+res.error).then(()=>{}); return; }
    const j=await res.r.json();
    if(!j.ok){ customConfirm('操作失败：'+(j.error||'')).then(()=>{}); return; }
    await loadPage(currentPage);
    customConfirm('完成 '+j.done+' 项'+(j.errors && j.errors.length ? '，失败 '+j.errors.length+' 项' : '')).then(()=>{});
  }

  async function onGenKw(){
    const selected=$$('#tbl tbody .ck:checked');
    if(selected.length===0){ customConfirm('请选择要提取关键词的文件').then(()=>{}); return; }
    const paths=selected.map(cb=>cb.dataset.path);
    var maxLenEl=$('#kw_len');
    const maxLen=Number(maxLenEl?maxLenEl.value:50)||50;
    toggleLoading(true,'正在提取关键词…');
    const res=await firstOK(PATHS.kw,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths,max_len:maxLen})});
    toggleLoading(false);
    if(!res.ok){ customConfirm('提取失败：'+res.error).then(()=>{}); return; }
    const j=await res.r.json();
    if(!j.ok){ customConfirm('提取失败：'+(j.error||'' )).then(()=>{}); return; }
    selected.forEach(function(cb){ var kw=(j.keywords && j.keywords[cb.dataset.path]) || ''; cb.closest('tr').querySelector('.kw').textContent=kw; });
    customConfirm(`成功提取 ${Object.keys(j.keywords||{}).length} 个文件的关键词`).then(()=>{});
  }

  async function onClearKw(){
    const selected=$$('#tbl tbody .ck:checked');
    if(selected.length===0){ customConfirm('请选择要清除关键词的文件').then(()=>{}); return; }
    const paths=selected.map(cb=>cb.dataset.path);
    const go=await customConfirm(`确认清除 ${paths.length} 个文件的关键词吗？`); if(!go) return;
    toggleLoading(true,'正在清除关键词…');
    const res=await firstOK(PATHS.clearKW,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths})});
    toggleLoading(false);
    if(!res.ok){ customConfirm('清除失败：'+res.error).then(()=>{}); return; }
    const j=await res.r.json();
    if(!j.ok){ customConfirm('清除失败：'+(j.error||'' )).then(()=>{}); return; }
    selected.forEach(cb=>cb.closest('tr').querySelector('.kw').textContent='');
    customConfirm(`已清除 ${j.cleared||0} 条关键词`).then(()=>{});
  }

  function onPreview(event){
    const btn=event.target;
    const path=btn.dataset.path; const ext=btn.dataset.ext||''; const cat=btn.dataset.cat||'';
    let content='';
    if(cat==='IMAGE'){ content=`<img src="/full/thumb?path=${qs(path)}" alt="图片预览">`; }
    else if(cat==='VIDEO'){ content=`<video controls width="100%"><source src="/full/file?path=${qs(path)}"></video>`; }
    else if(cat==='AUDIO'){ content=`<audio controls><source src="/full/file?path=${qs(path)}"></audio>`; }
    else if(['PDF','TEXT','SLIDES','DATA'].includes(cat)){
      content=`<iframe src="/full/file?path=${qs(path)}" width="100%" height="420" style="border:none;"></iframe>`;
    }else{ content='<p>该文件类型不支持预览。</p>'; }
    customPreview(path.split(/[\\/]/).pop(),content);
  }

  document.addEventListener('DOMContentLoaded', async()=>{
    let settings={};
    try{ const res=await fetch('/full/settings',{credentials:'include'}); settings=await res.json(); applyFeatureToggles(settings); }
    catch(e){ console.warn('读取设置失败',e); applyFeatureToggles({}); }

    fillTypes();
    bind('#category','change', fillTypes);
    bind('#pickDir','click', showDirModal);
    bind('#scanBtn','click', onScan);
    bind('#prev','click', function(){loadPage(currentPage-1);});
    bind('#next','click', function(){loadPage(currentPage+1);});
    bind('#exportBtn','click', onExport);
    bind('#kwFilterBtn','click', applyKwFilter);
    bind('#kwFilter','keyup', function(e){ if(e.key==='Enter') applyKwFilter(); });
    bind('#genKwBtn','click', onGenKw);
    bind('#clearKwBtn','click', onClearKw);
    bind('#applyMoveBtn','click', function(){ onApplyOps('move'); });
    bind('#applyRenameBtn','click', function(){ onApplyOps('rename'); });
    bind('#applyDeleteBtn','click', function(){ onApplyOps('delete'); });
    bind('#tbl','click', function(e){ if(e.target.classList.contains('pv')) onPreview(e); });

    const ut=$('#userTools');
    if(ut){
      if(settings.user){
        ut.innerHTML=`<button class="btn btn-sm" id="settingsBtn">设置</button><button class="btn btn-sm" id="logoutBtn">退出(${settings.user})</button>`;
        $('#logoutBtn').onclick=async()=>{ await fetch('/full/logout',{credentials:'include'}); location.reload(); };
      }else{
        ut.innerHTML=`<button class="btn btn-sm" id="settingsBtn">设置</button><button class="btn btn-sm" id="loginBtn">登录</button>`;
        $('#loginBtn').onclick=()=>{ $('#loginModal').style.display='flex'; };
      }
      $('#settingsBtn').onclick=openSettings;
    }

    bind('#loginConfirm','click',async function(){
      var username=$('#loginUser').value.trim();
      var password=$('#loginPass').value.trim();
      const res=await fetch('/full/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({username:username,password:password})});
      const j=await res.json();
      if(j.ok){ alert('登录成功'); $('#loginModal').style.display='none'; location.reload(); }
      else{ alert('登录失败：'+(j.error||'未知错误')); }
    });
    bind('#loginCancel','click',function(){ $('#loginModal').style.display='none'; });

    bind('#settingsSave','click', saveSettings);
    bind('#settingsCancel','click', function(){ $('#settingsModal').style.display='none'; });
  });
})();

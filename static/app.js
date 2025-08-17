(function(){
  function $id(id){ return document.getElementById(id); }
  function toast(txt, cls){
    var el = $id('msg');
    if(!el) return;
    el.textContent = txt || '';
    el.className = 'msg ' + (cls || '');
  }
  function fmtSize(n){
    if(n==null || isNaN(n)) return '';
    var u=['B','KB','MB','GB','TB'], i=0, v=Number(n);
    while(v>=1024 && i<u.length-1){ v/=1024; i++; }
    return v.toFixed((i===0)?0:1)+' '+u[i];
  }
  function fmtTime(ts){
    if(!ts) return '';
    try{ return new Date(ts*1000).toLocaleString(); }catch(e){ return ''; }
  }

  // 关键：按顺序尝试多条接口路径（哪个能通就用哪个）
  async function tryFetchJSON(urls){
    let lastErr = null;
    for (const u of urls){
      try{
        const r = await fetch(u, {cache:'no-store'});
        // 404/500 不算成功
        if(!r.ok){ lastErr = new Error(`HTTP ${r.status}`); continue; }
        const txt = await r.text();
        // 返回可能是 HTML（错误页），先粗判
        if (txt.trim().startsWith('<')) { lastErr = new Error('HTML returned'); continue; }
        const j = JSON.parse(txt);
        return {ok:true, data:j, url:u};
      }catch(e){
        lastErr = e;
      }
    }
    return {ok:false, error: lastErr};
  }

  async function scan(){
    var dirEl = $id('dirInput');
    var dir = (dirEl && dirEl.value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var ck = $id('ckRecursive');
    var recursive = (ck && ck.checked) ? '1':'0';

    // 可能的后端路径（按顺序尝试）
    const candidates = [
      `/api/scan?dir=${encodeURIComponent(dir)}&recursive=${recursive}&page=1&page_size=500&hash=0`,
      `/full/scan?dir=${encodeURIComponent(dir)}&recursive=${recursive}&page=1&page_size=500&hash=0`,
      `/scan?dir=${encodeURIComponent(dir)}&recursive=${recursive}&page=1&page_size=500&hash=0`
    ];

    toast('正在扫描...');
    const res = await tryFetchJSON(candidates);
    if(!res.ok){
      toast('扫描失败：接口不可用（/api/scan、/full/scan、/scan 都失败）','error');
      console.error('scan error:', res.error);
      return;
    }

    const j = res.data;
    if(!j || j.ok === false){
      toast('扫描失败：'+(j && j.error || '未知错误'),'error');
      return;
    }

    var rows = Array.isArray(j.data) ? j.data : [];
    var tb = ($id('tbl') && $id('tbl').querySelector('tbody'));
    if(!tb){ toast('页面表格未找到','error'); return; }
    tb.innerHTML = '';
    rows.forEach(function(it){
      var tr = document.createElement('tr');
      function td(t){ var d=document.createElement('td'); d.textContent=t||''; return d; }
      tr.appendChild(td(it.name));
      tr.appendChild(td(it.dir));
      tr.appendChild(td(it.ext));
      tr.appendChild(td(fmtSize(it.size)));
      tr.appendChild(td(fmtTime(it.mtime)));
      tb.appendChild(tr);
    });
    toast(`扫描完成：${rows.length} 个文件（使用接口：${res.url}）`);
  }

  async function exportCsv(){
    var dirEl = $id('dirInput');
    var dir = (dirEl && dirEl.value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var ck = $id('ckRecursive');
    var recursive = (ck && ck.checked) ? '1':'0';

    // 依次尝试几条导出路径
    const candidates = [
      `/api/export_csv?dir=${encodeURIComponent(dir)}&recursive=${recursive}`,
      `/full/export_csv?dir=${encodeURIComponent(dir)}&recursive=${recursive}`,
      `/export_csv?dir=${encodeURIComponent(dir)}&recursive=${recursive}`,
      `/full/export?dir=${encodeURIComponent(dir)}&recursive=${recursive}`, // 有些项目叫 /export
      `/export?dir=${encodeURIComponent(dir)}&recursive=${recursive}`
    ];

    // 先探测能返回 200 的哪条，再跳转下载
    for (const u of candidates){
      try{
        const r = await fetch(u, {method:'HEAD', cache:'no-store'});
        if(r.ok){ window.location.href = u; return; }
      }catch(e){}
    }
    // HEAD 不支持时，直接使用第一条，交给后端判断
    window.location.href = candidates[0];
  }

  async function pickDir(){
    var input = $id('dirInput');
    if(!input) return;
    var v = prompt('请输入要扫描的目录绝对路径（如 D:/ 或 C:/Users/...）', input.value||'');
    if(v!=null){ input.value = v; }
  }

  document.addEventListener('DOMContentLoaded', function(){
    var btnPick = $id('btnPick');
    var btnScan = $id('btnScan');
    var btnExport = $id('btnExport');
    if(btnPick) btnPick.addEventListener('click', pickDir);
    if(btnScan) btnScan.addEventListener('click', scan);
    if(btnExport) btnExport.addEventListener('click', exportCsv);
  });
})();

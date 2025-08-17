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

  let lastRows = [];
  let apiBase = null;

  async function detectApi(){
    const bases = ['/api','/full',''];
    for(let b of bases){
      try{
        const r = await fetch(b+'/ping');
        if(r.ok){ apiBase = b; return; }
      }catch(e){}
    }
    apiBase = '/api';
  }

  async function scan(){
    var dir = ($id('dirInput') && $id('dirInput').value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var recursive = ($id('ckRecursive') && $id('ckRecursive').checked)?'1':'0';
    var url = `${apiBase}/scan?dir=${encodeURIComponent(dir)}&recursive=${recursive}&page=1&page_size=500&hash=0`;
    toast('正在扫描...');
    try{
      const r = await fetch(url);
      const j = await r.json();
      if(!j || j.ok === false){ toast('扫描失败：'+(j && j.error || '未知错误'),'error'); return; }
      lastRows = Array.isArray(j.data) ? j.data : [];
      renderTable();
      fillFilters();
      toast(`扫描完成：${lastRows.length} 个文件 (接口:${apiBase})`);
    }catch(e){
      toast('扫描异常：'+e,'error');
    }
  }

  function renderTable(){
    var tb = ($id('tbl') && $id('tbl').querySelector('tbody'));
    if(!tb) return;
    tb.innerHTML = '';
    var cat = $id('selCategory').value || '';
    var typ = $id('selType').value || '';
    var kw = ($id('txtFilter').value || '').toLowerCase();
    lastRows.forEach(function(it){
      if(cat && it.category!==cat) return;
      if(typ && it.ext!==typ) return;
      if(kw && it.name.toLowerCase().indexOf(kw)<0) return;
      var tr = document.createElement('tr');
      function td(t){ var d=document.createElement('td'); d.textContent=t||''; return d; }
      tr.appendChild(td(it.name));
      tr.appendChild(td(it.dir));
      tr.appendChild(td(it.ext));
      tr.appendChild(td(fmtSize(it.size)));
      tr.appendChild(td(fmtTime(it.mtime)));
      tb.appendChild(tr);
    });
  }

  function fillFilters(){
    var catSel=$id('selCategory'), typSel=$id('selType');
    if(!catSel||!typSel) return;
    let cats=new Set(), typs=new Set();
    lastRows.forEach(it=>{ if(it.category) cats.add(it.category); if(it.ext) typs.add(it.ext); });
    catSel.innerHTML='<option value="">全部</option>'+Array.from(cats).map(c=>`<option value="${c}">${c}</option>`).join('');
    typSel.innerHTML='<option value="">全部</option>'+Array.from(typs).map(t=>`<option value="${t}">${t}</option>`).join('');
  }

  async function exportCsv(){
    var dir = ($id('dirInput') && $id('dirInput').value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var recursive = ($id('ckRecursive') && $id('ckRecursive').checked)?'1':'0';
    var url = `${apiBase}/export_csv?dir=${encodeURIComponent(dir)}&recursive=${recursive}`;
    window.location.href=url;
  }

  async function pickDir(){
    var input=$id('dirInput'); if(!input) return;
    var v=prompt('请输入目录绝对路径', input.value||''); if(v!=null){ input.value=v; }
  }

  document.addEventListener('DOMContentLoaded', async function(){
    await detectApi();
    $id('btnPick')?.addEventListener('click', pickDir);
    $id('btnScan')?.addEventListener('click', scan);
    $id('btnExport')?.addEventListener('click', exportCsv);
    $id('selCategory')?.addEventListener('change', renderTable);
    $id('selType')?.addEventListener('change', renderTable);
    $id('txtFilter')?.addEventListener('input', renderTable);
  });
})();
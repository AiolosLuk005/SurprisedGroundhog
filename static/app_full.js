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
    try{
      if(typeof ts==='number'){
        if(ts>1e12) return new Date(ts).toLocaleString();
        return new Date(ts*1000).toLocaleString();
      }
      return new Date(ts).toLocaleString();
    }catch(e){ return ''; }
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
    var dir = ($id('dir') && $id('dir').value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var recursive = ($id('recur') && $id('recur').checked)?'1':'0';
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
    var cat = ($id('category') && $id('category').value) || '';
    var typ = ($id('types') && $id('types').value) || '';
    var kw = ($id('q') && $id('q').value || '').toLowerCase();
    lastRows.forEach(function(it){
      var ext = (it.ext||'').toLowerCase();
      if(cat && it.category!==cat) return;
      if(typ && ext!==typ) return;
      if(kw && (it.name||'').toLowerCase().indexOf(kw)<0) return;
      var tr = document.createElement('tr');
      var tdSel=document.createElement('td');
      var cb=document.createElement('input'); cb.type='checkbox'; cb.dataset.path=it.full_path||''; tdSel.appendChild(cb);
      tr.appendChild(tdSel);
      function td(t){ var d=document.createElement('td'); d.textContent=t||''; return d; }
      tr.appendChild(td(it.name));
      tr.appendChild(td(it.dir_path || it.dir || ''));
      tr.appendChild(td(ext));
      tr.appendChild(td(it.category || ''));
      tr.appendChild(td(fmtSize(it.size_bytes || it.size)));
      tr.appendChild(td(fmtTime(it.mtime_iso || it.mtime)));
      var kwTd = td(Array.isArray(it.keywords)? it.keywords.join('，') : (it.keywords || '')); kwTd.className='kw'; tr.appendChild(kwTd);
      tb.appendChild(tr);
    });
  }

  async function genImgKw(){
    var cbs = Array.from(document.querySelectorAll('#tbl tbody input[type="checkbox"]:checked'));
    if(cbs.length===0){ toast('请先选择图像文件'); return; }
    var paths = cbs.map(cb=>cb.dataset.path).filter(Boolean);
    if(!paths.length){ toast('未找到文件路径','error'); return; }
    toast('正在提取图片关键词...');
    try{
      const r = await fetch(`${apiBase}/keywords_image`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({paths})
      });
      const j = await r.json();
      if(!j || j.ok===false){ toast('提取失败：'+(j&&j.error||''),'error'); return; }
      cbs.forEach(cb=>{
        const kw=j.keywords?.[cb.dataset.path]||[];
        const cell=cb.closest('tr')?.querySelector('.kw');
        if(cell) cell.textContent = Array.isArray(kw)? kw.join('，'):kw;
      });
      toast(`提取完成：${Object.keys(j.keywords||{}).length} 个文件`);
    }catch(e){
      toast('提取异常：'+e,'error');
    }
  }

  function fillFilters(){
    var catSel=$id('category'), typSel=$id('types');
    if(!catSel||!typSel) return;
    let cats=new Set(), typs=new Set();
    lastRows.forEach(it=>{ if(it.category) cats.add(it.category); if(it.ext) typs.add(it.ext); });
    catSel.innerHTML='<option value="">全部</option>'+Array.from(cats).map(c=>`<option value="${c}">${c}</option>`).join('');
    typSel.innerHTML='<option value="">全部</option>'+Array.from(typs).map(t=>`<option value="${t}">${t}</option>`).join('');
  }

  async function exportCsv(){
    var dir = ($id('dir') && $id('dir').value) || '';
    if(!dir){ toast('请先选择或输入目录'); return; }
    var recursive = ($id('recur') && $id('recur').checked)?'1':'0';
    var url = `${apiBase}/export_csv?dir=${encodeURIComponent(dir)}&recursive=${recursive}`;
    window.location.href=url;
  }

  async function pickDir(){
    var input=$id('dir'); if(!input) return;
    var v=prompt('请输入目录绝对路径', input.value||''); if(v!=null){ input.value=v; }
  }

  document.addEventListener('DOMContentLoaded', async function(){
    await detectApi();
    $id('pickDir')?.addEventListener('click', pickDir);
    $id('scanBtn')?.addEventListener('click', scan);
    $id('exportBtn')?.addEventListener('click', exportCsv);
    $id('category')?.addEventListener('change', renderTable);
    $id('types')?.addEventListener('change', renderTable);
    $id('q')?.addEventListener('input', renderTable);
    $id('btnImgKW')?.addEventListener('click', genImgKw);
  });
})();

// Classic UI fix 20250818c: /ls picker + recursive aliases + robust path building
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
    if(/^[A-Za-z]:/.test(p)||/\\/.test(p)) p=p.replace(/\//g,"\\"); // prefer backslashes for Windows drive
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

  const PATHS={
    scan:["/api/scan","/full/scan","/scan"],
    exportCSV:["/api/export_csv","/full/export_csv","/export_csv","/full/export","/export"],
    importSQL:["/api/import_mysql","/full/import_mysql","/import_mysql"],
    kw:["/api/kw","/full/kw","/kw","/api/keywords","/full/keywords","/keywords"],
    applyOps:["/api/apply_ops","/full/apply_ops","/apply_ops"],
    ls:["/ls"]
  };
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

  function fillTypes(){
    const cat=$("#category"), types=$("#types");
    if(!cat||!types) return;
    types.innerHTML="";
    (TYPES[cat.value]||[]).forEach(ext=>{
      const o=document.createElement("option"); o.value=ext; o.textContent=ext; types.appendChild(o);
    });
  }

  // /ls 目录选择弹窗
  function showDirModal(){
    const modal=$("#dirModal"), here=$("#dirHere"), list=$("#dirList");
    let cwd=$("#dir").value||"";
    async function refresh(){
      here.textContent=cwd||"(根)";
      const urls=PATHS.ls.map(u=>u+(cwd?("?dir="+qs(cwd)):""));
      const res=await firstOK(urls);
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

  async function onScan(){
    const dir=($("#dir")?.value||"").trim(); if(!dir){ alert("请选择扫描目录"); return; }
    const recur=$("#recur")?.checked?1:0;
    const pageSize=Number($("#page_size")?.value||500)||500;
    const exts=Array.from($("#types")?.selectedOptions||[]).map(o=>o.value.toLowerCase()).join(",");
    const q=$("#q")?.value||"";

    // 递归参数兼容一揽子别名
    const recurAliases=`recursive=${recur}&recur=${recur}&deep=${recur}&r=${recur}&subdirs=${recur}&include_subdirs=${recur}&walk=${recur}`;
    const params=`dir=${qs(dir)}&${recurAliases}&page=1&page_size=${pageSize}&exts=${qs(exts)}&ext=${qs(exts)}&q=${qs(q)}`;
    const candidates=PATHS.scan.map(b=>`${b}?${params}`);

    let result=null,lastErr=null;
    for(const u of candidates){
      try{
        const r=await fetch(u,{cache:"no-store"});
        if(!r.ok){ lastErr=new Error("HTTP "+r.status); continue; }
        const j=await r.json(); result={ok:true,url:u,data:j}; break;
      }catch(e){ lastErr=e; }
    }
    if(!result){ alert("扫描失败："+(lastErr?lastErr:"接口不可用")); return; }

    const selected=exts?exts.split(","):[];
    renderRows(result.data, selected);
    $("#pageinfo").textContent=`本页 ${($$("#tbl tbody tr").length)} 项 · 接口 ${result.url}`;
  }

  function renderRows(payload, selectedExts){
    const tbody=$("#tbl tbody"); if(!tbody) return;
    tbody.innerHTML="";
    const rows=Array.isArray(payload?.data)?payload.data: Array.isArray(payload?.items)?payload.items: [];
    rows.forEach(it=>{
      const ext=getExt(it);
      if(selectedExts.length && !selectedExts.includes(ext)) return; // 前端二次过滤
      const full=getFullPath(it);
      const sizeKB=humanKBFromAny(it.size_kb ?? it.sizeKB ?? it.size_bytes ?? it.size ?? it.bytes);
      const mtime=parseMTime(it);
      const tr=document.createElement("tr");
      tr.innerHTML=`
        <td><input type="checkbox" class="ck" data-path="${full}"></td>
        <td>${it.name||it.filename||""}</td>
        <td>${full}</td>
        <td>${ext}</td>
        <td>${it.category||""}</td>
        <td>${sizeKB}</td>
        <td>${mtime}</td>
        <td class="kw">${it.keywords||""}</td>
        <td><input class="mv" placeholder="目标目录"></td>
        <td><input class="rn" placeholder="新文件名"></td>
        <td><button class="btn btn-sm pv" data-path="${full}">预览</button></td>`;
      tbody.appendChild(tr);
    });
  }

  document.addEventListener("DOMContentLoaded",()=>{
    fillTypes();
    $("#category")?.addEventListener("change", fillTypes);
    $("#pickDir")?.addEventListener("click", showDirModal);
    $("#scanBtn")?.addEventListener("click", onScan);
  });
})();
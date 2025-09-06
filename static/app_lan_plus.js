// app_lan_plus.js — LAN 加强版（与完整版看齐的前端能力）
const el = (id)=>document.getElementById(id);
const $tbl = el("tbl").querySelector("tbody");
const $types = el("types");
const $category = el("category");
const $dirLabel = el("dirLabel");
const $pickFallback = el("pickFallback");
const $pageSize = el("pageSize");
const $count = el("count");
const $pageInfo = el("pageInfo");
const $secureBadge = el("secureBadge");

const EXT_GROUPS = {
  TEXT:   ["txt","md","rtf","doc","docx","json","log"],
  DATA:   ["csv","xlsx","xls","xml"],
  SLIDES: ["pptx","ppt"],
  PDF:    ["pdf"],
  IMAGE:  ["jpg","jpeg","png","gif","webp","bmp","tif","tiff","svg","heic"],
  AUDIO:  ["mp3","wav","flac","m4a","aac","ogg"],
  VIDEO:  ["mp4","mkv","mov","avi","wmv","webm"]
};

function fillExtOptions(cat=""){
  const exts = cat ? (EXT_GROUPS[cat]||[]) : [...new Set(Object.values(EXT_GROUPS).flat())];
  $types.innerHTML="";
  exts.forEach(x=>{ const o=document.createElement("option"); o.value=x; o.textContent=x; $types.appendChild(o); });
}
fillExtOptions(""); $category.onchange=()=>fillExtOptions($category.value);

let rootHandle=null, pickedFallbackFiles=null;
let files=[]; // 全量
let page=1;

function secureEnough(){
  return location.protocol==="https:" || location.hostname==="localhost";
}
function extOf(name){ const i=name.lastIndexOf("."); return i>=0?name.slice(i+1).toLowerCase():""; }

function updateSecureBadge(){
  $secureBadge.textContent = secureEnough() ? "安全（已启用本地改名/移动）" : "HTTP（已禁用本地改名/移动）";
}

el("pickBtn").onclick=async()=>{
  if(window.showDirectoryPicker && secureEnough()){
    try{
      rootHandle=await window.showDirectoryPicker();
      pickedFallbackFiles=null;
      $dirLabel.textContent=`已选择目录：${rootHandle.name}`;
      updateSecureBadge();
      return;
    }catch(e){ console.warn(e); }
  }
  $pickFallback.click();
};
$pickFallback.onchange=()=>{
  pickedFallbackFiles=$pickFallback.files; rootHandle=null;
  const rel=(pickedFallbackFiles[0]&&pickedFallbackFiles[0].webkitRelativePath)||"";
  $dirLabel.textContent= rel?`已选择目录（兼容模式）：${rel.split("/")[0]}`:"已选择目录（兼容模式）";
  updateSecureBadge();
};

el("scan").onclick=async()=>{
  const selTypes=new Set([...$types.selectedOptions].map(o=>o.value.toLowerCase()));
  const q=el("q").value.trim().toLowerCase();
  const cat=$category.value;
  const seen=new Set();
  files=[];

  async function pushRec(file, rel){
    const e=extOf(file.name);
    if(selTypes.size && !selTypes.has(e)) return;
    if(q && !(file.name.toLowerCase().includes(q) || e.includes(q) || (rel||"").toLowerCase().includes(q))) return;
    if(cat){ const group=EXT_GROUPS[cat]||[]; if(!group.includes(e)) return; }
    const key=rel||file.name;
    if(seen.has(key)) return; seen.add(key);
    const f = file;
    const mod = f.lastModified ? new Date(f.lastModified) : null;
    files.push({ name:f.name, rel:key, ext:e, size:f.size, mtime:mod, file:f, kw:"", cat:guessCat(e) });
  }

  if(rootHandle){
    await walkDir(rootHandle,"",async(handle, rel)=>{ const f=await handle.getFile(); await pushRec(f, rel); });
  }else if(pickedFallbackFiles){
    for(const f of pickedFallbackFiles){ await pushRec(f, f.webkitRelativePath||f.name); }
  }else{
    alert("请先选择目录"); return;
  }
  page=1; render();
};

async function walkDir(dirHandle, prefix, onFile){
  for await (const [name, handle] of dirHandle.entries()){
    const rel = prefix?`${prefix}/${name}`:name;
    if(handle.kind==="directory") await walkDir(handle, rel, onFile);
    else if(handle.kind==="file") await onFile(handle, rel);
  }
}
function guessCat(ext){
  for(const [k,v] of Object.entries(EXT_GROUPS)){ if(v.includes(ext)) return k; }
  return "";
}
function render(){
  const ps = Math.max(1, parseInt($pageSize.value||"200",10));
  const total = files.length;
  const pages = Math.max(1, Math.ceil(total/ps));
  if(page>pages) page=pages;
  const start=(page-1)*ps, end=Math.min(total, start+ps);
  $tbl.innerHTML="";
  for(let i=start;i<end;i++){
    const r=files[i];
    const tr=document.createElement("tr");
    const cb=document.createElement("input"); cb.type="checkbox"; cb.dataset.idx=i;
    const td0=document.createElement("td"); td0.appendChild(cb);
    const td1=document.createElement("td"); td1.textContent=r.name;
    const td2=document.createElement("td"); td2.textContent=r.rel;
    const td3=document.createElement("td"); td3.textContent=r.ext;
    const td4=document.createElement("td"); td4.textContent=r.cat;
    const td5=document.createElement("td"); td5.textContent=Math.round(r.size/1024);
    const td6=document.createElement("td"); td6.textContent=r.mtime? r.mtime.toLocaleString():"";
    const td7=document.createElement("td"); td7.textContent=Array.isArray(r.kw)?r.kw.join('，'):(r.kw||''); td7.className="kw";
    const move=document.createElement("input"); move.placeholder="子目录名"; move.style.width="120px";
    const rename=document.createElement("input"); rename.placeholder="新文件名含扩展名"; rename.style.width="160px";
    const td8=document.createElement("td"); td8.appendChild(move);
    const td9=document.createElement("td"); td9.appendChild(rename);
    tr.append(td0,td1,td2,td3,td4,td5,td6,td7,td8,td9);
    $tbl.appendChild(tr);
  }
  $pageInfo.textContent=`第 ${page}/${Math.max(1,Math.ceil(total/ps))} 页`;
  $count.textContent=`${total} 项`;
}
el("prev").onclick=()=>{ if(page>1){page--; render();}};
el("next").onclick=()=>{ const ps=parseInt($pageSize.value||"200",10); if(page*ps<files.length){page++; render();}};
$pageSize.onchange=()=>render();

async function readTextSample(f, maxBytes=8000){
  const ext = extOf(f.name);
  if(!["txt","md","csv","log","json"].includes(ext)) return "";
  const blob = f.slice(0, maxBytes);
  return await blob.text();
}
el("btnGenKW").onclick=async()=>{
  const seeds = el("kwSeeds").value.trim();
  const selected = [...document.querySelectorAll('tbody input[type="checkbox"]:checked')].map(cb=>parseInt(cb.dataset.idx));
  if(!selected.length){ alert("请先勾选需要生成关键词的文件"); return; }
  const btn = el("btnGenKW"); const old = btn.textContent; btn.disabled=true; btn.textContent="生成中…";
  let ok=0, fail=0;
  for(const idx of selected){
    const r = files[idx]; const row = $tbl.querySelector(`input[data-idx="${idx}"]`)?.closest("tr");
    if(row) row.querySelector(".kw").textContent = "⏳ 生成中...";
    try{
      const sample = await readTextSample(r.file);
      let data;
      if(sample){
        const payload = { text: (r.name + "\n" + sample).slice(0, 4000), seeds, max_len: 50 };
        const resp = await fetch("/api/ai/keywords",{ method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(payload) });
        if(!resp.ok) throw new Error("HTTP "+resp.status);
        data = await resp.json();
      }else{
        const form = new FormData();
        form.append("file", r.file, r.name);
        form.append("seeds", seeds);
        form.append("max_len", "50");
        const resp = await fetch("/api/ai/keywords_file",{ method:"POST", body: form });
        if(!resp.ok) throw new Error("HTTP "+resp.status);
        data = await resp.json();
      }
      if(!data.ok) throw new Error(data.err||"AI 生成失败");
      r.kw = data.keywords || [];
      ok++;
    }catch(e){
      console.error(e);
      r.kw=`❌ 失败: ${e.message||e}`;
      fail++;
    }
    render();
  }
  btn.disabled=false; btn.textContent=old;
  if(fail) alert(`完成：成功 ${ok} 个，失败 ${fail} 个`);
};
el("btnImgKW").onclick=async()=>{
  const selected = [...document.querySelectorAll('tbody input[type="checkbox"]:checked')].map(cb=>parseInt(cb.dataset.idx));
  if(!selected.length){ alert("请先勾选需要生成关键词的文件"); return; }
  const btn = el("btnImgKW"); const old = btn.textContent; btn.disabled=true; btn.textContent="生成中…";
  let ok=0, fail=0;
  for(const idx of selected){
    const r = files[idx]; const row = $tbl.querySelector(`input[data-idx="${idx}"]`)?.closest("tr");
    if(row) row.querySelector(".kw").textContent = "⏳ 生成中...";
    try{
      const form = new FormData();
      form.append("file", r.file, r.name);
      const resp = await fetch("/api/keywords_image",{ method:"POST", body: form });
      if(!resp.ok) throw new Error("HTTP "+resp.status);
      const data = await resp.json();
      if(!data.ok) throw new Error(data.error||"提取失败");
      r.kw = data.keywords || [];
      ok++;
    }catch(e){
      console.error(e);
      r.kw=`❌ 失败: ${e.message||e}`;
      fail++;
    }
    render();
  }
  btn.disabled=false; btn.textContent=old;
  if(fail) alert(`完成：成功 ${ok} 个，失败 ${fail} 个`);
};
el("btnClearKW").onclick=()=>{ files.forEach(f=>f.kw=[]); render(); };

// 导出 CSV（前端生成）
el("btnExportCSV").onclick=()=>{
  const header = ["名称","相对路径","类型","分类","大小KB","修改时间","关键词"];
  const rows = files.map(r=>[r.name,r.rel,r.ext,r.cat,Math.round(r.size/1024), r.mtime? r.mtime.toISOString():"", (Array.isArray(r.kw)?r.kw.join('，'):r.kw||'').replace(/\n/g," ") ]);
  const csv = [header, ...rows].map(a=>a.map(x=>`"${String(x).replace(/"/g,'""')}"`).join(",")).join("\r\n");
  const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="surprised_groundhog_lan.csv"; a.click();
  URL.revokeObjectURL(a.href);
};

// —— 本地批量操作（仅在安全上下文 + showDirectoryPicker 模式可用） —— //
async function ensureFsReady(){
  if(!(window.showDirectoryPicker && secureEnough() && rootHandle)){
    alert("此操作需要在 HTTPS 或 localhost，且使用“选择目录”获取目录权限后才能使用。");
    return false;
  }
  return true;
}
async function getParentDirHandle(rel){
  // rel: "a/b/c.txt" => return dir handle of "a/b"
  const parts = rel.split("/"); parts.pop(); // remove filename
  let dir = rootHandle;
  for(const p of parts){
    if(!p) continue;
    dir = await dir.getDirectoryHandle(p, {create:false});
  }
  return dir;
}
async function moveFile(rel, destSubdir){
  const srcDir = await getParentDirHandle(rel);
  const name = rel.split("/").pop();
  const fileHandle = await srcDir.getFileHandle(name);
  // read
  const f = await fileHandle.getFile();
  // ensure dest dir
  let destDir = rootHandle;
  if(destSubdir && destSubdir.trim()){
    const parts = destSubdir.replace(/^\/+|\/+$/g,"").split("/");
    for(const p of parts){
      destDir = await destDir.getDirectoryHandle(p, {create:true});
    }
  }
  // write
  const newHandle = await destDir.getFileHandle(name, {create:true});
  const w = await newHandle.createWritable(); await w.write(await f.arrayBuffer()); await w.close();
  // delete original
  await srcDir.removeEntry(name);
}
async function renameFile(rel, newName){
  const srcDir = await getParentDirHandle(rel);
  const oldName = rel.split("/").pop();
  const fileHandle = await srcDir.getFileHandle(oldName);
  const f = await fileHandle.getFile();
  // write new
  const newHandle = await srcDir.getFileHandle(newName, {create:true});
  const w = await newHandle.createWritable(); await w.write(await f.arrayBuffer()); await w.close();
  // delete old
  await srcDir.removeEntry(oldName);
}
async function trashFile(rel){
  let trash = await rootHandle.getDirectoryHandle(".trash", {create:true});
  const name = rel.split("/").pop();
  const srcDir = await getParentDirHandle(rel);
  const fileHandle = await srcDir.getFileHandle(name);
  const f = await fileHandle.getFile();
  const newHandle = await trash.getFileHandle(name, {create:true});
  const w = await newHandle.createWritable(); await w.write(await f.arrayBuffer()); await w.close();
  await srcDir.removeEntry(name);
}

el("btnMove").onclick=async()=>{
  if(!await ensureFsReady()) return;
  const selected = [...document.querySelectorAll('tbody input[type="checkbox"]:checked')].map(cb=>parseInt(cb.dataset.idx));
  if(!selected.length){ alert("请勾选需要移动的文件"); return; }
  for(const idx of selected){
    const tr = $tbl.querySelector(`input[data-idx="${idx}"]`).closest("tr");
    const subdir = tr.querySelector("td:nth-child(9) input").value.trim();
    if(!subdir){ continue; }
    await moveFile(files[idx].rel, subdir);
  }
  alert("移动完成（仅 HTTPS/localhost 模式有效）");
};

el("btnRename").onclick=async()=>{
  if(!await ensureFsReady()) return;
  const selected = [...document.querySelectorAll('tbody input[type="checkbox"]:checked')].map(cb=>parseInt(cb.dataset.idx));
  if(!selected.length){ alert("请勾选需要重命名的文件"); return; }
  for(const idx of selected){
    const tr = $tbl.querySelector(`input[data-idx="${idx}"]`).closest("tr");
    const newName = tr.querySelector("td:nth-child(10) input").value.trim();
    if(!newName) continue;
    await renameFile(files[idx].rel, newName);
  }
  alert("重命名完成（仅 HTTPS/localhost 模式有效）");
};

el("btnTrash").onclick=async()=>{
  if(!await ensureFsReady()) return;
  const selected = [...document.querySelectorAll('tbody input[type="checkbox"]:checked')].map(cb=>parseInt(cb.dataset.idx));
  if(!selected.length){ alert("请勾选需要移入回收站的文件"); return; }
  for(const idx of selected) await trashFile(files[idx].rel);
  alert("已移动到 .trash（仅 HTTPS/localhost 模式有效）");
};

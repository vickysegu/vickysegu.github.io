import re, sys, shutil

src = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
html = open(src, encoding='utf-8').read()


def need(cond, msg):
    if not cond:
        sys.exit('GAGAL: ' + msg)

# ---------- 1. HEAD ----------
HEAD = r'''<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Portfolio interaktif Vicky Setia Gunawan — Dosen Bisnis Digital, peneliti, dan web developer. Publikasi, pengajaran, pengabdian, dan materi kuliah dalam tampilan Windows XP.">
<meta name="author" content="Vicky Setia Gunawan">
<meta name="theme-color" content="#245edb">
<link rel="canonical" href="https://vickysegu.github.io/">
<meta property="og:type" content="website">
<meta property="og:title" content="Vicky Setia Gunawan — Windows XP Portfolio">
<meta property="og:description" content="Dosen Bisnis Digital · Peneliti · Web Developer. Jelajahi portfolio dalam tampilan Windows XP.">
<meta property="og:url" content="https://vickysegu.github.io/">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E🖥️%3C/text%3E%3C/svg%3E">'''
html, n = re.subn(r'<meta name="viewport"[^>]*>', lambda m: HEAD, html, count=1)
need(n == 1, 'meta viewport tidak ditemukan')

# ---------- 2. NOSCRIPT ----------
NOSCRIPT = r'''<noscript><div style="position:fixed;inset:0;z-index:99999;overflow:auto;padding:24px;background:#fff;color:#000;font:14px/1.7 Arial,sans-serif">
  <h1>Vicky Setia Gunawan</h1>
  <p>Dosen Bisnis Digital · Universitas Perintis Indonesia</p>
  <ul>
    <li>Email: <a href="mailto:visegu27@gmail.com">visegu27@gmail.com</a></li>
    <li><a href="https://scholar.google.com/citations?user=zxh3WngAAAAJ">Google Scholar</a></li>
  </ul>
  <p>Aktifkan JavaScript untuk melihat portfolio interaktif ini.</p>
</div></noscript>'''
need('<body>' in html, 'tag <body> tidak ditemukan')
html = html.replace('<body>', '<body>\n' + NOSCRIPT, 1)

# ---------- 3. CSS ----------
CSS = r'''
/* ═════════ PATCH v6 ═════════ */
:root{--tb-h:calc(34px + env(safe-area-inset-bottom,0px));}
@supports(height:100dvh){html,body{height:100dvh;}}
.taskbar{height:var(--tb-h);padding-bottom:env(safe-area-inset-bottom,0px);}
.startmenu{bottom:var(--tb-h);}
.tray-popup{bottom:calc(var(--tb-h) + 6px);}
.balloon{bottom:calc(var(--tb-h) + 10px)!important;}
.app-window.maximized{height:calc(100% - var(--tb-h))!important;}
:focus-visible{outline:2px solid #f5a623;outline-offset:1px;}
.dicon:focus-visible{background:rgba(60,120,220,.35);}
button,.dicon,.menubar>span,.sm-item,.task-btn,.exp-file,.oe-msg,.oe-folder,.tbtn,.exp-btn{touch-action:manipulation;}
.dicon,.task-btn,.exp-file,.ms-cell{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}
.welcome{overflow-y:auto;}
.welcome-top{flex:1 0 auto;}
@media (max-height:520px){
  .welcome-top{padding:16px 24px;gap:24px;}
  .welcome-logo{font-size:32px;}
  .welcome-user-avatar{width:52px;height:52px;font-size:24px;}
}
.xp-data-err{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 12px;background:#fff4d6;border-bottom:1px solid #d6a468;color:#7a4a00;font-size:12px;flex-shrink:0;}
.xp-data-err button{padding:3px 12px;font-size:11px;background:linear-gradient(#fff,#ece9d8 85%,#d6d0c5);border:1px solid #003c74;border-radius:3px;}
#expPath{display:none;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:1;}
@media (max-width:720px){
  .app-window,.app-window.maximized{height:calc(100% - var(--tb-h))!important;}
  .task-btn{min-width:38px;max-width:38px;padding:0;justify-content:center;}
  .task-btn span:last-child{display:none;}
  .task-btn span:first-child{font-size:15px;}
  #expPath{display:inline-block;}
}
@media (pointer:coarse){
  .tb-btn{width:32px;height:32px;font-size:14px;}
  .tbtn,.exp-btn{padding:9px 12px;}
  .menubar>span{padding:7px 10px;}
  .tray .tray-btn{padding:6px;}
  .sm-item{padding:11px 12px;}
  .oe-msg-subj{padding:12px 10px 12px 0;}
  input,select,textarea{font-size:16px!important;}
}
'''
need('</style>' in html, '</style> tidak ditemukan')
html = html.replace('</style>', CSS + '</style>', 1)

# ---------- 4. FETCHFOLDER (API dulu, indeks JSON sebagai cadangan) ----------
FETCH = r'''const CACHE_TTL=5*60*1000;
const BLOCK_KEY='xp_gh_block_until';
let indexPromise=null;

function loadIndex(){
  if(!indexPromise){
    indexPromise=fetch('./materi-index.json',{cache:'no-cache'})
      .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(j=>(j&&j.tree)||{})
      .catch(()=>{indexPromise=null;return null;});
  }
  return indexPromise;
}
function readCache(p){try{return JSON.parse(sessionStorage.getItem('xpc_'+p)||'null');}catch(e){return null;}}
function writeCache(p,d){try{sessionStorage.setItem('xpc_'+p,JSON.stringify({t:Date.now(),d}));}catch(e){}}
function dropCache(p){try{sessionStorage.removeItem('xpc_'+p);}catch(e){}}
function apiBlocked(){try{return Date.now()<(+sessionStorage.getItem(BLOCK_KEY)||0);}catch(e){return false;}}
function blockApi(r){
  let until=Date.now()+10*60*1000;
  const reset=r&&r.headers?+r.headers.get('x-ratelimit-reset'):0;
  if(reset)until=Math.min(reset*1000+2000,Date.now()+70*60*1000);
  try{sessionStorage.setItem(BLOCK_KEY,String(until));}catch(e){}
}

async function fetchFolder(path){
  const cached=readCache(path);
  if(cached&&Date.now()-cached.t<CACHE_TTL){window.__materiSource='cache';return cached.d;}
  let apiErr=null;
  if(!apiBlocked()){
    try{
      const url=`https://api.github.com/repos/${GH.owner}/${GH.repo}/contents/${encPath(path)}`;
      const r=await fetch(url,{headers:{'Accept':'application/vnd.github.v3+json'}});
      if(r.ok){
        const files=await r.json();
        if(!Array.isArray(files))throw new Error('Response bukan array');
        writeCache(path,files);
        window.__materiSource='api';
        return files;
      }
      if(r.status===403||r.status===429)blockApi(r);
      let m='HTTP '+r.status;
      if(r.status===404)m=`Folder "${path}" tidak ditemukan`;
      if(r.status===403||r.status===429)m='Rate limit GitHub';
      apiErr=new Error(m);
    }catch(e){apiErr=e;}
  }
  const idx=await loadIndex();
  if(idx&&Array.isArray(idx[path])){window.__materiSource='index';return idx[path];}
  if(cached){window.__materiSource='cache';return cached.d;}
  throw apiErr||new Error('Rate limit GitHub dan materi-index.json belum tersedia');
}

'''
a = html.find('async function fetchFolder(path){')
b = html.find('function renderSidebar(){')
need(a != -1 and b != -1 and a < b, 'fungsi fetchFolder / renderSidebar tidak ditemukan')
html = html[:a] + FETCH + html[b:]

# status "dari indeks" di navigate
html, n = re.subn(r"renderItems\(items\);(\s*)\}catch\(err\)\{",
    lambda m: "renderItems(items);\n    if(window.__materiSource==='index'){const s=document.getElementById('expStatus');if(s)s.textContent+=' · dari indeks';}"
              + m.group(1) + "}catch(err){", html, count=1)
need(n == 1, 'bagian navigate (renderItems + catch) tidak ditemukan')

# refresh menghapus cache path aktif
o1 = "rebind('expRefreshBtn',()=>navigate(state.current,true));"
o2 = "window.__explorerRefresh=()=>navigate(state.current,true);"
need(o1 in html and o2 in html, 'tombol refresh Explorer tidak ditemukan')
html = html.replace(o1, "rebind('expRefreshBtn',()=>{dropCache(state.current);navigate(state.current,true);});", 1)
html = html.replace(o2, "window.__explorerRefresh=()=>{dropCache(state.current);navigate(state.current,true);};", 1)

# ---------- 5. JS PATCH ----------
JS = r'''<script>
/* ═════════ PATCH v6 ═════════ */
(function(){
'use strict';
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const touchy=()=>matchMedia('(pointer:coarse)').matches;
const raf=window.requestAnimationFrame.bind(window);

/* 1. Ketuk sekali membuka ikon desktop (sentuh) + Enter */
const dI=$('#desktopIcons');
dI.addEventListener('click',e=>{
  const el=e.target.closest('.dicon');
  if(!el||!touchy()||e.target.tagName==='INPUT')return;
  openApp(el.dataset.open);
},true);
dI.addEventListener('keydown',e=>{
  const el=e.target.closest('.dicon');
  if(el&&e.target===el&&e.key==='Enter')openApp(el.dataset.open);
});

/* 2. Explorer: ketuk = buka; PDF di tab baru; path di status bar */
const ef=$('#expFiles');
ef.addEventListener('click',e=>{
  const el=e.target.closest('.exp-file');
  if(!el||!touchy())return;
  const name=($('.exp-file-name',el)||{}).textContent||'';
  const isDir=el.dataset.type==='dir';
  const ext=(name.split('.').pop()||'').toLowerCase();
  if(!isDir&&ext==='pdf'){
    const cr=$$('#expCrumb .exp-crumb');
    const base=cr.length?cr[cr.length-1].dataset.path:'Materi';
    window.open('https://vickysegu.github.io/'+(base+'/'+name).split('/').map(encodeURIComponent).join('/'),'_blank','noopener');
    return;
  }
  el.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}));
});
const st=$('#app-explorer .statusbar');
const ep=document.createElement('span');ep.id='expPath';ep.className='zone';
st.insertBefore(ep,st.lastElementChild);
const crumbEl=$('#expCrumb');
new MutationObserver(()=>{
  const c=$$('.exp-crumb',crumbEl);
  ep.textContent=c.length?'📂 '+c[c.length-1].dataset.path:'';
}).observe(crumbEl,{childList:true});

/* 3. Tombol Back menutup jendela teratas */
let armed=false,ignore=false;
function sync(){
  const n=$$('.app-window:not(.hidden)').length;
  if(n>0&&!armed){history.pushState({xp:1},'');armed=true;}
  else if(n===0&&armed){armed=false;ignore=true;history.back();}
}
window.addEventListener('popstate',()=>{
  if(ignore){ignore=false;return;}
  armed=false;
  const id=typeof currentAppId==='function'?currentAppId():null;
  if(id)closeApp(id);
  setTimeout(sync,0);
});

/* 4. Meta/Cmd: buka Start hanya jika ditekan sendirian */
let metaAlone=false;
window.addEventListener('keydown',e=>{
  if(e.key==='Meta'){e.stopImmediatePropagation();metaAlone=true;}
  else metaAlone=false;
},true);
window.addEventListener('keyup',e=>{
  if(e.key==='Meta'&&metaAlone){metaAlone=false;$('#startmenu').classList.toggle('open');}
},true);
window.addEventListener('blur',()=>{metaAlone=false;});

/* 5. Login: ingat sesi + masuk otomatis 6 detik */
const users=$$('.welcome-user');
const hint=document.createElement('div');
hint.style.cssText='margin-top:10px;font-size:12px;opacity:.8;min-height:16px';
$('.welcome-tagline').appendChild(hint);
let autoT=null,left=6;
function cancelAuto(){clearInterval(autoT);autoT=null;hint.textContent='';}
users.forEach(u=>u.addEventListener('click',()=>{cancelAuto();try{sessionStorage.setItem('xp_logged','1');}catch(e){}}));
$('#welcomePower').addEventListener('click',cancelAuto);
let logged=false;try{logged=sessionStorage.getItem('xp_logged')==='1';}catch(e){}
if(logged){users[0].click();}
else{
  hint.textContent='Masuk otomatis dalam '+left+' detik…';
  autoT=setInterval(()=>{
    left--;
    if(left<=0){cancelAuto();users[0].click();}
    else hint.textContent='Masuk otomatis dalam '+left+' detik…';
  },1000);
}
function forgetLogin(){try{sessionStorage.removeItem('xp_logged');}catch(e){}}
$('#shutdownBtn').addEventListener('click',forgetLogin);
const _hd=handleDialog;
handleDialog=function(k){if(k==='logoff')forgetLogin();return _hd.apply(this,arguments);};

/* 6. Tekan lama = klik kanan (sentuh) */
let lp=null,lpFired=false,lpStart={x:0,y:0},lastTouch=0;
const LP='.dicon,.task-btn,.exp-file,.ms-cell,.wallpaper,.tasks,.sel-box';
document.addEventListener('touchstart',e=>{
  lastTouch=Date.now();
  if(e.touches.length!==1)return;
  const t=e.target;
  if(!(t.id==='desktop'||t.closest(LP)))return;
  const p=e.touches[0];lpStart={x:p.clientX,y:p.clientY};
  clearTimeout(lp);lpFired=false;
  lp=setTimeout(()=>{
    lpFired=true;
    t.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:lpStart.x,clientY:lpStart.y}));
    if(navigator.vibrate)try{navigator.vibrate(15);}catch(x){}
  },520);
},{passive:true});
document.addEventListener('touchmove',e=>{
  if(!lp)return;const p=e.touches[0];
  if(Math.hypot(p.clientX-lpStart.x,p.clientY-lpStart.y)>10){clearTimeout(lp);lp=null;}
},{passive:true});
['touchend','touchcancel'].forEach(ev=>document.addEventListener(ev,()=>{
  clearTimeout(lp);lp=null;setTimeout(()=>{lpFired=false;},400);
},{passive:true}));
document.addEventListener('click',e=>{
  if(lpFired){lpFired=false;e.preventDefault();e.stopPropagation();}
},true);
document.addEventListener('contextmenu',e=>{
  if(e.isTrusted&&Date.now()-lastTouch<1500&&touchy()){e.preventDefault();e.stopPropagation();}
},true);

/* 7. Keahlian: bar persentase -> chips + tautan publikasi */
function patchSkills(){
  const g=$('#sec-keahlian .skill-grid');if(!g)return;
  const items=['Web Development','Sistem Informasi','Artificial Intelligence','UI/UX Design','Bisnis Digital'];
  const w=document.createElement('div');
  w.innerHTML='<div class="cp-chips">'+items.map(i=>'<span class="cp-chip">'+i+'</span>').join('')+'</div>'+
    '<div style="margin-top:14px"><button class="cp-action primary" type="button">🌐 Lihat publikasi terkait →</button></div>';
  g.replaceWith(w);
  $('button',w).addEventListener('click',()=>openApp('ie'));
}
const _rp=renderProfile;
renderProfile=function(){const r=_rp.apply(this,arguments);patchSkills();return r;};
if($('#cpMain')&&$('#cpMain').children.length)patchSkills();

/* 8. Banner jika data.json gagal dimuat */
(window.XPI_READY||Promise.resolve()).then(()=>{
  if(window.PORTFOLIO_DATA)return;
  ['ie','control','excel','outlook'].forEach(id=>{
    const mb=$('#app-'+id+' .menubar');if(!mb)return;
    const b=document.createElement('div');b.className='xp-data-err';
    b.innerHTML='⚠️ <span>Data gagal dimuat (data.json tidak ditemukan atau tidak valid).</span> <button type="button">Coba lagi</button>';
    $('button',b).onclick=()=>location.reload();
    mb.after(b);
  });
});

/* 9. Aksesibilitas + sinkron history */
function a11y(){
  const L={min:'Minimize',max:'Maximize',close:'Close'};
  $$('.tb-btn:not([aria-label])').forEach(b=>b.setAttribute('aria-label',L[b.dataset.act]||'Button'));
  $$('.dlg:not([role])').forEach(d=>{
    d.setAttribute('role','dialog');d.setAttribute('aria-modal','true');
    const f=$('input',d)||$('.dlg-actions button',d);if(f)f.focus();
  });
  $$('.dicon:not([role])').forEach(d=>{d.setAttribute('role','button');d.setAttribute('aria-label',d.dataset.label||'');});
}
let pend=false;
new MutationObserver(()=>{
  if(pend)return;pend=true;
  raf(()=>{pend=false;sync();a11y();});
}).observe($('#desktop'),{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
a11y();
console.log('[XP] Patch v6 aktif ✓');
})();
</script>
'''
i = html.rfind('</body>')
need(i != -1, '</body> tidak ditemukan')
html = html[:i] + JS + html[i:]

# ---------- TULIS ----------
shutil.copyfile(src, 'index.backup.html')
open('index.new.html', 'w', encoding='utf-8').write(html)
print('Selesai. Cadangan: index.backup.html | Hasil: index.new.html')

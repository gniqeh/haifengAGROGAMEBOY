const $=id=>document.getElementById(id);
let lastData=null;
async function api(url,opt={}){const r=await fetch(url,opt);if(r.status===401)throw new Error('AUTH');if(!r.ok)throw new Error(await r.text());return r.json();}
function uaShort(s){if(!s)return '';return s.length>55?s.slice(0,55)+'…':s;}
function toast(t){const e=$('toast');e.textContent=t;e.classList.add('show');clearTimeout(e._tm);e._tm=setTimeout(()=>e.classList.remove('show'),2200);}
function gameLabel(id){return id==='quiz1'?'方案 1 · 农业知识答题闯关':'方案 2 · 智慧农业闯关';}
function renderGames(games,active){
  const box=$('gameSwitch');box.innerHTML='';$('activeName').textContent=gameLabel(active);
  games.forEach(g=>{
    const b=document.createElement('button');
    b.className='game-btn'+(g.id===active?' active':'');
    const desc=g.id==='quiz1'?'10 道题 · 单局快速互动 · 原来的农业知识答题闯关':'4 关 × 5 题 · 计时 / 连击 · 更偏游戏化的智慧农业闯关';
    b.innerHTML=`<b>${gameLabel(g.id)}</b><span>${desc}</span>`;
    b.onclick=async()=>{
      if(g.id===active)return;
      const ok=confirm(`确定切换到“${gameLabel(g.id)}”吗？\n\n所有已经打开 8831 的会议屏会在约 2 秒内自动刷新，正在答题的人会被中断。`);
      if(!ok)return;
      [...box.querySelectorAll('button')].forEach(x=>x.disabled=true);
      try{
        await api('/api/admin/active-game',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({game:g.id})});
        toast('已切换，参与端正在自动刷新');
        await load();
      }catch(e){alert('切换失败：'+e.message);await load();}
    };
    box.appendChild(b);
  });
}
async function load(){
  try{
    const d=await api('/api/admin/dashboard');lastData=d;
    $('login').hidden=true;$('main').hidden=false;renderGames(d.games||[],d.active_game);
    const s=d.summary;$('total').textContent=s.total_runs||0;$('ips').textContent=s.unique_ips||0;$('avgScore').textContent=s.avg_score??'-';$('avgRate').textContent=s.avg_rate==null?'-':s.avg_rate+'%';$('perfect').textContent=s.perfect_runs||0;
    const tb=$('rows');tb.innerHTML='';
    d.results.forEach(r=>{const tr=document.createElement('tr');tr.style.cursor='pointer';tr.innerHTML=`<td>${r.submitted_at}</td><td>${r.ip}</td><td><b>${r.score}</b></td><td>${r.right_count}/${r.total}</td><td><span class="tag">${r.rate}%</span></td><td>${r.grade||''}</td><td title="${(r.user_agent||'').replaceAll('"','&quot;')}">${uaShort(r.user_agent)}</td>`;tr.onclick=()=>showDetail(r.id);tb.appendChild(tr);});
  }catch(e){if(e.message==='AUTH'){$('login').hidden=false;$('main').hidden=true;}else console.error(e);}
}
async function showDetail(id){const d=await api('/api/admin/result/'+id);$('detailText').textContent=JSON.stringify(d,null,2);$('detail').showModal();}
$('loginBtn').onclick=async()=>{try{await api('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('pwd').value})});$('err').textContent='';load();}catch(e){$('err').textContent='密码错误';}};
$('pwd').addEventListener('keydown',e=>{if(e.key==='Enter')$('loginBtn').click();});
$('logout').onclick=async()=>{await fetch('/api/admin/logout',{method:'POST'});location.reload();};
$('close').onclick=()=>$('detail').close();
load();setInterval(()=>{if(!$('main').hidden)load();},10000);

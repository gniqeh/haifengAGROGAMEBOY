const $=id=>document.getElementById(id);
const names={survey:'巡田',allocate:'资源配置',ai:'AI协同',event:'突发事件',result:'已完成'};
async function load(){const r=await fetch('/api/admin/dashboard');const d=await r.json();$('online').textContent=d.online;$('total').textContent=d.total;$('done').textContent=d.done;$('avgScore').textContent=d.avg_score??'--';$('avgProfit').textContent=d.avg_profit==null?'--':`${d.avg_profit} 元`;$('rows').innerHTML=d.devices.map((x,i)=>`<tr><td>终端 ${String(i+1).padStart(2,'0')}<br><small>${x.device_id.slice(0,8)}</small></td><td>${x.ip||''}</td><td>${x.scenario_id||'--'}</td><td><span class="pill">${names[x.stage]||x.stage||'--'}</span></td><td>${x.score??'--'}</td><td>${x.profit==null?'--':x.profit+' 元/亩'}</td><td>${x.last_seen||''}</td></tr>`).join('')}
function ws(){const p=location.protocol==='https:'?'wss':'ws';const s=new WebSocket(`${p}://${location.host}/ws/admin`);s.onmessage=()=>load();s.onclose=()=>setTimeout(ws,1200)}
$('resetBtn').onclick=async()=>{if(!confirm('确定清空所有终端和本轮数据？'))return;await fetch('/api/admin/reset',{method:'POST'});load()};
load();ws();setInterval(load,5000);

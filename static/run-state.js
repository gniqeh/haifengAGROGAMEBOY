(function(){
  var GAME=window.__ACTIVE_GAME__||'quiz1';
  var key='agroTerminalIdV1';
  function id(p){return p+((crypto&&crypto.randomUUID)?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2));}
  var terminal;
  try{terminal=localStorage.getItem(key);if(!terminal){terminal=id('term-');localStorage.setItem(key,terminal);}}catch(e){terminal=id('term-');}
  var run=null,answered=0,right=0,answers=[],last='',clicked=null,done=false;
  function send(url,data,keep){try{fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),keepalive:!!keep}).catch(function(){});}catch(e){}}
  function total(){return GAME==='quiz2'?20:10;}
  function score(){var e=document.getElementById(GAME==='quiz2'?'score':'scoreNow');return parseInt(e&&e.textContent,10)||0;}
  function begin(){run=id('run-');answered=0;right=0;answers=[];last='';clicked=null;done=false;send('/api/runs/start',{run_id:run,terminal_id:terminal,game:GAME,total:total()});}
  function feedback(){var e=document.getElementById('fb');return e&&e.classList.contains('show');}
  function sync(){if(!run||!feedback())return;var q=document.getElementById(GAME==='quiz2'?'qtext':'qText');var n=document.getElementById(GAME==='quiz2'?'qnum':'qNow');var qt=(q&&q.textContent||'').trim();var nk=(n&&n.textContent||'').trim()+'|'+qt;if(!qt||nk===last)return;var ok=false,chosen='',correct='';if(clicked){ok=GAME==='quiz2'?clicked.classList.contains('right'):clicked.classList.contains('correct');chosen=(clicked.textContent||'').trim();}var ce=document.querySelector(GAME==='quiz2'?'.opt.right':'.opt.correct');if(ce)correct=(ce.textContent||'').trim();answered++;if(ok)right++;answers.push({question:qt,chosen:chosen,correct:correct,ok:ok});last=nk;send('/api/runs/update',{run_id:run,terminal_id:terminal,game:GAME,status:'playing',answered_count:answered,right_count:right,total:total(),score:score(),rate:Math.round(right/total()*100),answers:answers});clicked=null;}
  function finalVisible(){return GAME==='quiz2'?!!document.querySelector('#final.on'):!!document.querySelector('#resultPanel.active');}
  function finish(){if(!run||done||!finalVisible())return;done=true;var ge=document.getElementById(GAME==='quiz2'?'rank':'gradeTitle');var grade=(ge&&ge.textContent||'').trim();var rate=Math.round(right/total()*100);send('/api/runs/update',{run_id:run,terminal_id:terminal,game:GAME,status:'finished',answered_count:answered,right_count:right,total:total(),score:GAME==='quiz2'?rate:score(),rate:rate,grade:grade,answers:answers},true);}
  document.addEventListener('click',function(e){var s=e.target.closest&&e.target.closest('#btnStart,#startBtn,#btnAgain,#againBtn');if(s){setTimeout(begin,0);return;}var o=e.target.closest&&e.target.closest('.opt');if(o&&run){clicked=o;setTimeout(sync,80);}},true);
  new MutationObserver(function(){if(run){setTimeout(sync,30);setTimeout(finish,60);}}).observe(document.documentElement,{subtree:true,attributes:true,attributeFilter:['class'],childList:true});
  setInterval(function(){if(run&&!done)send('/api/runs/update',{run_id:run,terminal_id:terminal,game:GAME,status:'playing',answered_count:answered,right_count:right,total:total(),score:score(),rate:Math.round(right/total()*100),answers:answers});},15000);
})();

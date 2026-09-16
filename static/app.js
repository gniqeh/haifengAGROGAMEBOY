/* SECTION: state */
(function(){
  var BANK = window.QUESTION_BANK || [];
  var TOTAL = Math.min(BANK.length, 10);
  var PER = 100 / TOTAL;
  var KEY = 'agriInfoQuizBest';
  var SESSION_KEY = 'agriInfoQuizSession';

  var order = [], cur = 0, score = 0, locked = false, records = [];

  var $ = function(id){ return document.getElementById(id); };
  var panels = { start: $('startPanel'), quiz: $('quizPanel'), result: $('resultPanel') };

  function shuffle(a){
    for(var i=a.length-1;i>0;i--){
      var j=Math.floor(Math.random()*(i+1)), t=a[i]; a[i]=a[j]; a[j]=t;
    }
    return a;
  }
  function show(name){
    for(var k in panels){ panels[k].classList.toggle('active', k===name); }
    window.scrollTo(0,0);
  }
  function build(bankIdx){
    var b = BANK[bankIdx];
    var pairs = [];
    for(var i=0;i<b.opts.length;i++){ pairs.push({ text:b.opts[i], correct:(i===b.a) }); }
    shuffle(pairs);
    return { cat:b.cat, q:b.q, pairs:pairs, exp:b.exp, src:b.src };
  }

  function loadBest(){
    try{ var v=localStorage.getItem(KEY); return v?JSON.parse(v):null; }catch(e){ return null; }
  }
  function saveBest(v){
    try{ localStorage.setItem(KEY, JSON.stringify(v)); }catch(e){}
  }
  function renderBest(){
    var b = loadBest();
    $('bestVal').textContent = b ? (b.score + ' 分（' + b.date + '）') : '暂无记录';
  }

  function start(){
    order = shuffle(BANK.map(function(_,i){ return i; })).slice(0, TOTAL);
    cur = 0; score = 0; locked = false; records = [];
    $('qTotal').textContent = TOTAL;
    $('scoreNow').textContent = '0';
    renderBest();
    show('quiz');
    render();
  }

  function replay(el, cls){
    if(!el) return;
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
  }

  function render(){
    locked = false;
    var q = build(order[cur]);
    $('qNow').textContent = cur + 1;
    $('fill').style.width = ((cur) / TOTAL * 100) + '%';
    $('qCat').textContent = q.cat || '农业信息化';
    $('qTag').textContent = '第 ' + (cur+1) + ' / ' + TOTAL + ' 题';
    $('qText').textContent = q.q;

    var qc = document.querySelector('.qcard');
    qc.classList.remove('nope');
    replay(qc, 'swap');
    replay($('qCat'), 'pop');
    replay($('qText'), 'reveal');

    var box = $('opts');
    box.innerHTML = '';
    var letters = ['A','B','C','D'];
    for(var i=0;i<q.pairs.length;i++){
      (function(i){
        var b = document.createElement('button');
        b.className = 'opt pending';
        b.type = 'button';
        b.innerHTML = '<span class="letter">' + letters[i] + '</span><span class="otext"></span>';
        b.querySelector('.otext').textContent = q.pairs[i].text;
        b.setAttribute('aria-label', letters[i] + '：' + q.pairs[i].text);
        b.addEventListener('click', function(){ choose(i); });
        box.appendChild(b);
        setTimeout(function(){
          b.classList.remove('pending');
          if(b.disabled) return;
          b.classList.add('enter');
        }, 60 + i*70);
      })(i);
    }

    var fb = $('fb');
    fb.className = 'fb';
    $('btnNext').disabled = true;
    $('btnNext').textContent = (cur === TOTAL-1) ? '查看成绩 🏁' : '下一题 ➜';
    window.__q = q;
  }

  function choose(i){
    if(locked) return;
    locked = true;
    var q = window.__q;
    var btns = $('opts').querySelectorAll('.opt');
    var picked = q.pairs[i].correct;

    for(var k=0;k<btns.length;k++){
      btns[k].disabled = true;
      btns[k].classList.remove('enter');
      btns[k].classList.remove('pending');
      if(q.pairs[k].correct){ btns[k].classList.add('correct'); }
      else if(k===i){ btns[k].classList.add('wrong'); }
      else { btns[k].classList.add('dim'); }
      var L = btns[k].querySelector('.letter');
      if(q.pairs[k].correct){ L.textContent = '✓'; }
      else if(k===i){ L.textContent = '✗'; }
    }

    if(picked){ score += Math.round(PER); $('scoreNow').textContent = score; }
    $('fill').style.width = ((cur+1) / TOTAL * 100) + '%';

    if(picked){
      replay($('scoreNow').parentNode, 'hit');
      ring($('scoreNow').parentNode);
      spark(btns[i]);
    } else {
      replay(document.querySelector('.qcard'), 'nope');
    }

    var fb = $('fb');
    fb.className = 'fb show ' + (picked ? 'ok' : 'no');
    $('fbIcon').textContent = picked ? '✅' : '❌';
    $('fbWord').textContent = picked ? '回答正确！' : '回答错误';
    $('fbPt').textContent = picked ? ('+' + Math.round(PER) + ' 分') : '+0 分';
    var rightText = '';
    for(var j=0;j<q.pairs.length;j++){ if(q.pairs[j].correct){ rightText = q.pairs[j].text; break; } }
    $('fbExp').innerHTML = (picked ? '' : '<b>正确答案：' + esc(rightText) + '</b><br>') + esc(q.exp);
    $('fbSrc').textContent = '📖 出处：' + q.src;
    $('btnNext').disabled = false;

    records.push({ q:q.q, chosen:q.pairs[i].text, right:rightText, ok:picked });
    fb.scrollIntoView({ behavior:'smooth', block:'nearest' });
  }

  function esc(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function next(){
    if(!locked) return;
    if(cur < TOTAL-1){ cur++; render(); }
    else { finish(); }
  }

  function sessionId(){
    try{
      var id = sessionStorage.getItem(SESSION_KEY);
      if(!id){ id = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : ('q-' + Date.now() + '-' + Math.random().toString(16).slice(2)); sessionStorage.setItem(SESSION_KEY,id); }
      return id;
    }catch(e){ return 'q-' + Date.now() + '-' + Math.random().toString(16).slice(2); }
  }
  function reportResult(payload){
    try{
      fetch('/api/results',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload),
        keepalive:true
      }).catch(function(){});
    }catch(e){}
  }

  function grade(s){
    var r = s / (PER*TOTAL) * 100;
    if(r >= 90) return { e:'🚀', t:'智慧农业带头人', c:'#d95e00', m:'几乎全对！卫星巡田、大棚环控、物联网、电商直播你全都门儿清，回村就能给乡亲们讲一堂课。' };
    if(r >= 70) return { e:'🥈', t:'信息化能手', c:'#0a6a2c', m:'成绩不错！新技术用得明白，再把合规红线和产地冷链这些细节记牢，就能冲满分。' };
    if(r >= 50) return { e:'🥉', t:'新农人新星', c:'#0d8fc2', m:'及格线上有潜力，重点回看直播合规和「最先一公里」这两块，进步会很快。' };
    return { e:'🌱', t:'数字农田学徒', c:'#a05cd8', m:'刚起步不怕，每题都用大白话讲了解析和出处，看完再挑战一次！' };
  }

  function finish(){
    var g = grade(score);
    var right = records.filter(function(r){ return r.ok; }).length;
    var rate = Math.round(right / TOTAL * 100);

    reportResult({ session_id: sessionId(), score: score, right_count: right, total: TOTAL, rate: rate, grade: g.t, answers: records });

    $('gradeEmoji').textContent = g.e;
    var gt = $('gradeTitle');
    gt.textContent = g.t;
    gt.style.color = g.c;
    replay(gt, 'pop');
    $('gradeMsg').textContent = g.m;

    rollTo($('rScore'), 0, score, 900, '');
    rollTo($('rRight'), 0, right, 800, '/' + TOTAL);
    rollTo($('rRate'), 0, rate, 900, '%');

    var sbs = document.querySelectorAll('.sbox');
    for(var bi=0;bi<sbs.length;bi++){
      (function(el, i){
        el.classList.remove('rise');
        el.classList.add('pending');
        setTimeout(function(){ el.classList.remove('pending'); el.classList.add('rise'); }, 120 + i*130);
      })(sbs[bi], bi);
    }
    var beam = $('beam');
    beam.hidden = !(rate >= 90);

    var prev = loadBest(), isNew = !prev || score > prev.score;
    if(isNew && score > 0){
      var d = new Date();
      saveBest({ score:score, date:(d.getMonth()+1) + '月' + d.getDate() + '日' });
    }
    $('newBest').classList.toggle('show', isNew && score > 0);

    var list = $('rvList');
    list.innerHTML = '';
    for(var i=0;i<records.length;i++){
      var r = records[i];
      var d = document.createElement('div');
      d.className = 'rv pending ' + (r.ok ? 'ok' : 'no');
      var head = document.createElement('div');
      head.style.flex = '1 1 auto';
      var rq = document.createElement('div'); rq.className = 'rq';
      rq.textContent = (i+1) + '. ' + r.q;
      var ra = document.createElement('div'); ra.className = 'ra';
      if(r.ok){ ra.textContent = '你的答案：' + r.chosen; }
      else { ra.innerHTML = '你选了：' + esc(r.chosen) + '　→　<b>正确答案：' + esc(r.right) + '</b>'; }
      head.appendChild(rq); head.appendChild(ra);
      var mk = document.createElement('span'); mk.className = 'mk'; mk.textContent = r.ok ? '✓' : '✗';
      d.appendChild(mk); d.appendChild(head);
      list.appendChild(d);
      (function(el, idx){ setTimeout(function(){ el.classList.remove('pending'); el.classList.add('rise'); }, 420 + idx*55); })(d, i);
    }

    show('result');
    if(rate >= 70){ burst(); }
  }

  function rollTo(el, from, to, dur, suffix){
    if(!el){ return; }
    suffix = suffix || '';
    if(to === from || dur <= 0){ el.textContent = to + suffix; return; }
    var t0 = null;
    function step(ts){
      if(t0 === null){ t0 = ts; }
      var p = Math.min(1, (ts - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (to - from) * e) + suffix;
      if(p < 1){ requestAnimationFrame(step); }
      else { el.textContent = to + suffix; }
    }
    requestAnimationFrame(step);
  }

  function ring(host){
    if(!host) return;
    var r = document.createElement('span');
    r.className = 'score-ring';
    host.appendChild(r);
    setTimeout(function(){ if(r.parentNode) r.parentNode.removeChild(r); }, 700);
  }

  function spark(el){
    if(!el) return;
    var rc = el.getBoundingClientRect();
    var cx = rc.left + rc.width/2, cy = rc.top + rc.height/2;
    var emo = ['✨','⭐','🌟','💫','🎯'];
    var N = 14;
    for(var i=0;i<N;i++){
      (function(i){
        var s = document.createElement('span');
        s.className = 'spark';
        s.textContent = emo[i % emo.length];
        var ang = (Math.PI*2/N)*i + Math.random()*0.5;
        var dist = 70 + Math.random()*80;
        s.style.left = cx + 'px';
        s.style.top = cy + 'px';
        s.style.setProperty('--dx', (Math.cos(ang)*dist).toFixed(1) + 'px');
        s.style.setProperty('--dy', (Math.sin(ang)*dist - 26).toFixed(1) + 'px');
        s.style.fontSize = (15 + Math.random()*13) + 'px';
        s.style.animationDelay = (i*16) + 'ms';
        document.body.appendChild(s);
        setTimeout(function(){ if(s.parentNode) s.parentNode.removeChild(s); }, 1200);
      })(i);
    }
  }

  function burst(){
    var emo = ['🎉','📡','🛰️','⭐','🍓','✨','📱','🛒'];
    for(var i=0;i<34;i++){
      (function(i){
        setTimeout(function(){
          var s = document.createElement('span');
          s.className = 'confetti';
          s.textContent = emo[i % emo.length];
          s.style.left = (Math.random()*100) + 'vw';
          s.style.animationDuration = (2.4 + Math.random()*2.2) + 's';
          s.style.fontSize = (18 + Math.random()*22) + 'px';
          document.body.appendChild(s);
          setTimeout(function(){ if(s.parentNode) s.parentNode.removeChild(s); }, 5200);
        }, i*95);
      })(i);
    }
  }

  document.addEventListener('keydown', function(e){
    var k = e.key;
    if(!k) return;
    var up = k.toUpperCase();
    var map = { '1':0,'2':1,'3':2,'4':3,'A':0,'B':1,'C':2,'D':3 };
    if(panels.start.classList.contains('active')){
      if(k===' '||k==='Enter'){ e.preventDefault(); start(); }
      return;
    }
    if(panels.quiz.classList.contains('active')){
      if(map.hasOwnProperty(up) && !locked){
        e.preventDefault();
        var btns = $('opts').querySelectorAll('.opt');
        if(btns[map[up]]) choose(map[up]);
      } else if(k===' '||k==='Enter'){
        if(!locked && !$('btnNext').disabled){ e.preventDefault(); next(); }
      }
      return;
    }
    if(panels.result.classList.contains('active')){
      if(k===' '||k==='Enter'){ e.preventDefault(); start(); }
    }
  });

  $('btnStart').addEventListener('click', start);
  $('btnNext').addEventListener('click', next);
  $('btnAgain').addEventListener('click', start);

  if(!BANK.length){
    $('qText').textContent = '题库未加载：请确认题库脚本与本页位于同一项目目录后刷新重试。';
    $('btnStart').disabled = true;
  }
  renderBest();
})();

(function(){
  var here=window.__ACTIVE_GAME__;
  if(!here)return;
  async function check(){
    try{
      var r=await fetch('/api/active-game',{cache:'no-store'});
      if(!r.ok)return;
      var d=await r.json();
      if(d.active_game && d.active_game!==here){ location.reload(); }
    }catch(e){}
  }
  setInterval(check,2000);
})();

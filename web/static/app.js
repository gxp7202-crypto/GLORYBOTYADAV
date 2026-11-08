/* YADAV LEVEL UP - Ultra Premium Control Center */
/* Main Application Entry Point */

(function initParticles(){
  const cvs=document.getElementById('particleCanvas'),ctx=cvs.getContext('2d');
  let w=0,h=0,particles=[],animId=null;
  const COLORS=['rgba(255,153,51,','rgba(56,225,255,','rgba(31,174,100,','rgba(139,123,255,'];
  function resize(){w=cvs.width=innerWidth;h=cvs.height=innerHeight}
  function Particle(){
    this.reset=()=>{this.x=Math.random()*w;this.y=Math.random()*h;this.r=Math.random()*1.8+0.4;this.vx=(Math.random()-0.5)*0.3;this.vy=(Math.random()-0.5)*0.3;
      this.c=COLORS[Math.floor(Math.random()*COLORS.length)];this.opacity=Math.random()*0.4+0.1}
    this.reset()
    this.update=()=>{this.x+=this.vx;this.y+=this.vy;if(this.x<0||this.x>w||this.y<0||this.y>h)this.reset()}
    this.draw=()=>{ctx.beginPath();ctx.arc(this.x,this.y,this.r,0,Math.PI*2);ctx.fillStyle=this.c+this.opacity+')';ctx.fill()}
  }
  function init(){particles=[];for(let i=0;i<Math.min(120,Math.floor((w*h)/18000));i++)particles.push(new Particle())}
  function loop(){ctx.clearRect(0,0,w,h);particles.forEach(p=>{p.update();p.draw()});animId=requestAnimationFrame(loop)}
  addEventListener('resize',()=>{resize();init()});resize();init();loop()
})();

const API = window.location.origin;
const BRAND = 'YADAV LEVEL UP';
let token = localStorage.getItem('ylu_token') || '';
let tab = 'dashboard';
let pollTimer = null, clockTimer = null, globalTimer = null;
let consoleSquad = null;
let lastStatus = null;
let proxyEnabled = true;

const TABS = [
  {id:'dashboard', label:'Dashboard', icon:'\uD83D\uDCCA'},
  {id:'glory',     label:'Match Play', icon:'\uD83D\uDD25'},
  {id:'create',    label:'Create Squad', icon:'\u2795'},
  {id:'guild',     label:'Guild Ops', icon:'\uD83C\uDFF0'},
  {id:'consoles',  label:'Consoles', icon:'\uD83D\uDCBB'},
];

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];});}
function $id(x){return document.getElementById(x);}
function initials(name){name=String(name||'?');return name.replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'??';}
function fmt(n){n=Number(n)||0;return n.toLocaleString('en-IN');}

async function api(path, opts={}){
  opts.headers = opts.headers || {};
  if(token) opts.headers['X-Admin-Token'] = token;
  if(opts.body && typeof opts.body!=='string'){opts.body=JSON.stringify(opts.body);opts.headers['Content-Type']='application/json';}
  const controller = new AbortController();
  const timeoutId = setTimeout(()=>controller.abort(), 20000);
  opts.signal = controller.signal;
  try{
    const r = await fetch(API+path, opts);
    clearTimeout(timeoutId);
    const raw = await r.text();
    let j;
    try { j = JSON.parse(raw); }
    catch(_) { j = {ok:false, error:'HTTP '+r.status+' — '+raw.slice(0,200)}; }
    if(r.status===401 && path!=='/api/login'){ logout(true); j.ok=false; j.error=j.error||'Session expired'; }
    if(!j.ok && !j.error) j.error = 'HTTP '+r.status;
    return j;
  }catch(e){
    clearTimeout(timeoutId);
    return {ok:false,error:e.name==='AbortError'?'Server did not respond in 20s':'Cannot reach server: '+e.message};
  }
}

function toast(msg, type='info'){
  const t = document.createElement('div');
  t.className = 'toast '+(type==='ok'?'ok':type==='err'?'err':type==='warn'?'warn':'');
  const ic = type==='ok'?'\u2705':type==='err'?'\u26D4':type==='warn'?'\u26A0\uFE0F':'\u2139\uFE0F';
  t.innerHTML = '<span class="ti">'+ic+'</span><span>'+esc(msg)+'</span>';
  $id('toasts').appendChild(t);
  setTimeout(()=>{t.classList.add('out');setTimeout(()=>t.remove(),350);},3800);
}

function confirmBox(title, text){
  return new Promise(res=>{
    const m = $id('modal');
    m.innerHTML = '<div class="modal-card"><h4>'+esc(title)+'</h4><p>'+esc(text)+'</p><div class="modal-actions"><button class="btn ghost" id="mcNo">Cancel</button><button class="btn dng" id="mcYes">Yes, continue</button></div></div>';
    m.classList.add('show');
    const close = v=>{m.classList.remove('show');m.innerHTML='';res(v);};
    $id('mcNo').onclick=()=>close(false); $id('mcYes').onclick=()=>close(true);
    m.onclick=e=>{if(e.target===m)close(false);};
  });
}

function setLoginStatus(msg, type){
  const el = $id('loginStatus');
  if(!el) return;
  el.textContent = msg;
  el.style.color = type==='ok' ? '#22d17a' : type==='err' ? '#ff4d5e' : '#7a849a';
}

async function checkServer(){
  setLoginStatus('\u23F3 Connecting to server\u2026','info');
  try{
    const ctl = new AbortController();
    const t = setTimeout(()=>ctl.abort(), 20000);
    const r = await fetch(API+'/api/ping', {signal:ctl.signal});
    clearTimeout(t);
    if(!r.ok){ setLoginStatus('Server responded HTTP '+r.status,'err'); return; }
    const j = await r.json();
    setLoginStatus(j.ok ? '\u2705 Server online — enter password' : 'Server error: '+(j.error||'unknown'), j.ok?'ok':'err');
  }catch(e){
    setLoginStatus('\u26D4 Cannot reach server'+(e.name==='AbortError'?' (timeout — free tier waking up, wait 30s and retry)':''),'err');
  }
}

async function doLogin(){
  try{
    const pw = $id('pw').value; if(!pw) return toast('Enter the password','warn');
    const btn = $id('loginBtn'); btn.disabled=true; btn.innerHTML='<span class="spin"></span> UNLOCKING\u2026';
    setLoginStatus('Checking password\u2026','info');
    const r = await api('/api/login',{method:'POST',body:{password:pw}});
    btn.disabled=false; btn.textContent='UNLOCK DASHBOARD';
    if(r.ok){
      token=r.token; localStorage.setItem('ylu_token',token);
      setLoginStatus('Unlocked','ok');
      enterApp();
      toast('PREMIUM UNLOCKED — welcome back, boss \uD83C\uDDEE\uD83C\uDDF3','ok');
    } else {
      setLoginStatus('\u26D4 '+(r.error||'Wrong password'),'err');
      toast(r.error||'Wrong password','err');
    }
  }catch(e){
    const btn = $id('loginBtn'); if(btn){ btn.disabled=false; btn.textContent='UNLOCK DASHBOARD'; }
    setLoginStatus('\u26D4 '+String(e),'err');
    toast('Login error: '+String(e),'err');
  }
}

function logout(silent){
  localStorage.removeItem('ylu_token'); token='';
  if(pollTimer) clearInterval(pollTimer);
  if(clockTimer) clearInterval(clockTimer);
  if(globalTimer) clearInterval(globalTimer);
  pollTimer=clockTimer=globalTimer=null;
  $id('app').style.display='none'; $id('login').style.display='flex';
  if(!silent) toast('Signed out','info');
}

function enterApp(){
  $id('login').style.display='none';
  const app = $id('app'); app.style.display='block';
  app.innerHTML = '\n    <div class="mobile-top"><div class="logo">Y+</div><div class="nm">'+BRAND+'</div><div class="spacer"></div>\n      <span class="live-pill" style="margin:0" id="mLive"><span class="dot"></span>LIVE</span></div>\n    <div class="shell">\n      <aside class="sidebar">\n        <div class="side-brand"><div class="logo">Y+</div><div class="nm">'+BRAND+'<small>ULTRA PREMIUM \uD83C\uDDEE\uD83C\uDDF3</small></div><span class="badge b-success" style="font-size:9px;margin-left:10px">PREMIUM</span></div>\n        '+TABS.map(t=>'<div class="nav-item" data-tab="'+t.id+'" onclick="switchTab(\''+t.id+'\')"><span class="ni">'+t.icon+'</span>'+t.label+'</div>').join('')+'\n        <div class="side-foot">\n          <div class="live-pill"><span class="dot" id="hLive"></span>ENGINE LIVE</div>\n          <div class="clock" id="clock">--:--:--</div>\n          <button class="btn dng sm" style="width:100%;justify-content:center;margin-top:12px" onclick="logout()">\uD83D\uDEAA Sign out</button>\n        </div>\n      </aside>\n      <main class="main"><div class="live-strip" id="liveStrip"></div><div id="content"></div></main>\n    </div>\n    <nav class="bottom-nav">'+TABS.map(t=>'<div class="bn" data-tab="'+t.id+'" onclick="switchTab(\''+t.id+'\')"><span class="bi">'+t.icon+'</span>'+t.label.split(' ')[0]+'</div>').join('')+'</nav>';
  startClock(); startGlobalPoll(); switchTab('dashboard');
}

function startClock(){
  if(clockTimer) clearInterval(clockTimer);
  const tick=()=>{const el=$id('clock');if(el)el.textContent=new Date().toLocaleTimeString('en-IN');};
  tick(); clockTimer=setInterval(tick,1000);
}

function setActiveNav(){
  document.querySelectorAll('.nav-item[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));
  document.querySelectorAll('.bn[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));
}

function switchTab(t){
  tab=t; setActiveNav();
  if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
  if(t==='dashboard'){ renderDashboard(true); pollTimer=setInterval(()=>renderDashboard(false),2500); }
  else if(t==='glory'){ renderGlory(); pollTimer=setInterval(refreshGlory,2500); }
  else if(t==='create'){ renderCreate(); }
  else if(t==='guild'){ renderGuild(); pollTimer=setInterval(refreshGuild,2000); }
  else if(t==='consoles'){ renderConsoles(); pollTimer=setInterval(refreshConsoles,2000); }
}

function topbar(title, crumb){
  return '<div class="topbar"><div><h2>'+title+'</h2><div class="crumb">'+crumb+'</div></div><span class="badge b-success" style="font-size:10px">PREMIUM</span><div class="spacer"></div></div>';
}

function animateTo(el,to){
  if(!el) return; to = Number(to)||0; const from = Number(el.dataset.v||0);
  if(from===to){ el.textContent = fmt(to); return; }
  el.dataset.v = to; const start = performance.now(), dur = 750;
  const step = (t)=>{const k = Math.min(1,(t-start)/dur); const e = 1-Math.pow(1-k,3); el.textContent = fmt(Math.round(from+(to-from)*e)); if(k<1) requestAnimationFrame(step);};
  requestAnimationFrame(step);
}

function renderLiveStrip(d){
  const s = $id('liveStrip'); if(!s) return;
  if(!s.dataset.init){
    s.dataset.init = '1';
    s.innerHTML = '<span class="live-pill" id="lsStatus" style="margin:0"><span class="dot" id="lsDot"></span><span id="lsStatusTxt">LIVE</span></span>\n      <span class="ls">\uD83D\uDC65 <b id="lsAcc">0</b> accounts</span><span class="ls">\uD83D\uDD25 <b id="lsGlory">0</b> glory</span>\n      <span class="ls">\u2694\uFE0F <b id="lsMatch">0</b> matches</span><span class="ls">\u2699\uFE0F <b id="lsRun">0</b> workers</span>\n      <span class="ls">\uD83D\uDEE1\uFE0F <b id="lsMode">\u2014</b></span><span class="spacer"></span><span class="ls-clock" id="lsClock">--:--:--</span>';
  }
  const ok = !!(d && d.ok);
  const st=$id('lsStatus'), txt=$id('lsStatusTxt'), dot=$id('lsDot');
  if(st){ st.style.background = ok?'rgba(34,209,122,.12)':'rgba(255,77,94,.16)'; st.style.color = ok?'var(--good)':'#ff9aa4'; }
  if(txt) txt.textContent = ok?'LIVE':'OFFLINE';
  if(dot){ ok ? dot.classList.remove('off') : dot.classList.add('off'); }
  const clk=$id('lsClock'); if(clk) clk.textContent = new Date().toLocaleTimeString('en-IN');
  if(!ok) return;
  animateTo($id('lsAcc'), d.total_accounts);
  animateTo($id('lsGlory'), d.total_gained_exp);
  animateTo($id('lsMatch'), d.total_matches);
  animateTo($id('lsRun'), d.active_workers);
}

async function globalPoll(){
  const [d, ab] = await Promise.all([api('/api/status'), api('/api/antiban')]);
  renderLiveStrip(d);
  const m=$id('lsMode'); if(m && ab && ab.ok) m.textContent = ab.level.toUpperCase();
}
function startGlobalPoll(){ globalPoll(); if(globalTimer) clearInterval(globalTimer); globalTimer = setInterval(globalPoll, 2000); }

async function renderDashboard(first){
  if(first) $id('content').innerHTML = topbar('Dashboard','Real-time overview')+'<div class="grid-stats">'+'<div class="shimmer"></div>'.repeat(4)+'</div>';
  const d = await api('/api/status'); if(!d.ok) return; lastStatus = d;
  const failed = d.failed_uids||[]; const c = $id('content'); if(!c) return;
  let html = topbar('Dashboard','Real-time overview')+'\n    <div class="grid-stats">\n      <div class="stat"><span class="ico">\uD83D\uDEE1\uFE0F</span><div class="lbl">Active Squads</div><div class="num">'+fmt(d.total_squads)+'</div></div>\n      <div class="stat g"><span class="ico">\uD83D\uDC65</span><div class="lbl">Accounts</div><div class="num">'+fmt(d.total_accounts)+'</div></div>\n      <div class="stat c"><span class="ico">\u2694\uFE0F</span><div class="lbl">Total Matches</div><div class="num">'+fmt(d.total_matches)+'</div></div>\n      <div class="stat v"><span class="ico">\u2699\uFE0F</span><div class="lbl">Live Workers</div><div class="num">'+fmt(d.active_workers)+'</div></div>\n    </div>';
  if(failed.length) html += '<div class="alert red"><span class="ai">\u26A0\uFE0F</span><div><b>'+failed.length+' account(s) failed guild op:</b><br>'+failed.map(esc).join(', ')+' \u2014 try again with fresh IDs.</div></div>';

  /* Auto-setup panel */
  html += '\n    <div class="form-card" style="margin-top:24px">\n      <h3>\u26A1 Auto Setup All</h3>\n      <p class="hint">Khud sab hoga: guest accounts \u2192 squads \u2192 guild join \u2192 start \u2192 glory. Aap sirf quantity aur guild ID dein.</p>\n      <div class="form-2col">\n        <div><label class="label">Kitni Squads</label><input class="inp" id="autoCount" type="number" value="3" min="1" max="20"></div>\n        <div><label class="label">Guild ID</label><input class="inp" id="autoGuild" placeholder="Guild ID"></div>\n      </div>\n      <button class="btn go" style="width:100%;margin-top:16px" onclick="autoSetup()">\u26A1 Auto Setup All — Start Glory</button>\n      <span id="autoStatus" style="margin-top:12px;display:block;font-size:13px;color:var(--txt-dim)"></span>\n    </div>';

  html += '<div class="section-title"><span class="bar"></span>Squads</div><div id="squadsWrap"></div>';
  c.innerHTML = html;
  const wrap = $id('squadsWrap');
  if(!d.squads||d.squads.length===0){ wrap.innerHTML = '<div class="empty"><span class="ei">\uD83D\uDEE1\uFE0F</span>No squads yet.<br>Head to <b>Create Squad</b> to spin one up.</div>'; return; }
  wrap.innerHTML = d.squads.map(renderSquadCard).join('');
}

function statusBadge(st){const s=String(st||'STOPPED').toUpperCase();
  const cls = s==='ONLINE'?'b-online':s==='IN_MATCH'?'b-inmatch':s==='CONNECTING'?'b-connecting':s==='ERROR'?'b-error':s==='PAUSED'?'b-connecting':'b-stopped';
  const label = s==='IN_MATCH'?'IN MATCH':s; return '<span class="badge '+cls+'"><span class="bd"></span>'+esc(label)+'</span>';}
function guildBadge(g){const s=String(g||'\u2014').toUpperCase(); const cls = s==='SUCCESS'?'b-success':s==='FAILED'?'b-failed':'b-pending'; return '<span class="badge '+cls+'">\uD83C\uDFF0 '+esc(s)+'</span>';}

function renderSquadCard(s){
  let slots=''; for(let i=0;i<4;i++){ const m=s.members[i];
    if(m){ const gst=String(m.guild_status||'\u2014').toUpperCase();
      slots+='<div class="slot filled"><div class="slot-top"><div class="avatar">'+esc(initials(m.nickname))+'</div>\n        <div style="min-width:0"><div class="nick">'+esc(m.nickname||'?')+'</div><div class="uid">UID '+esc(m.uid)+'</div></div></div>\n        <div class="meta">'+statusBadge(m.status)+'<span>LVL '+(m.level||1)+'</span><span>\u2022 '+(m.matches||0)+' matches</span></div>\n        <div class="meta">'+guildBadge(gst)+'</div>\n        <div class="slot-actions"><button class="btn xs dng" onclick="removeMember('+s.id+',\''+esc(m.uid)+'\')">\uD83D\uDDD1 Remove</button></div></div>';
    } else { slots+='<div class="slot empty">Slot '+(i+1)+' \u00B7 Empty</div>'; }}
  const controls = s.is_started
    ? '<button class="btn sm warn" onclick="restartSquad('+s.id+')">\uD83D\uDD04 Restart</button><button class="btn sm dng" onclick="stopSquad('+s.id+')">\u23F9 Stop</button>'
    : '<button class="btn sm go" onclick="startSquad('+s.id+')">\u25B6 Start</button>';
  return '<div class="squad-card"><div class="sq-head"><h3>\uD83D\uDEE1\uFE0F Squad '+s.id+' '+(s.is_started?'<span class="badge b-running"><span class="bd"></span>RUNNING</span>':'<span class="badge b-stopped">STOPPED</span>')+'</h3>\n    <span class="badge b-pending">'+s.members.length+'/4</span><div class="spacer"></div>'+controls+'<button class="btn sm dng" onclick="deleteSquad('+s.id+')">\uD83D\uDDD1 Delete</button></div><div class="slots">'+slots+'</div></div>';
}

async function renderCreate(){
  let rows=''; for(let i=1;i<=4;i++){
    rows+='<div class="member-row"><span class="sl">Slot '+i+'</span><input class="inp" id="cuid'+i+'" placeholder="Game UID" inputmode="numeric"><input class="inp" id="cpw'+i+'" type="password" placeholder="Password"></div>';
  }
  $id('content').innerHTML = topbar('Create Squad','Add up to 4 accounts')+'\n    <div class="form-card"><h3>\u2795 New Squad</h3><p class="hint">Enter UID + password for 1\u20134 accounts. Create builds the squad; then hit <b>Start</b> on the dashboard to begin matchmaking.</p>'+rows+'\n    <div class="form-row" style="margin-top:14px"><button class="btn info" onclick="createGuestAccount()" style="background:linear-gradient(135deg,#8b7bff,#5b4bcc);color:#fff;border:none;width:100%">\uD83D\uDC7B Create Guest Account (Auto)</button><span id="guestStatus" style="margin-left:12px;font-size:13px;color:var(--txt-dim);margin-top:8px;display:block"></span></div>\\n    <button class="btn go" style="width:100%;justify-content:center;padding:16px;font-size:16px;margin-top:18px" id="createBtn" onclick="createSquad()">\u2705 Create Squad</button></div>';
}
async function createGuestAccount(){
  const st = $id('guestStatus');
  if(!st){ toast('Create Squad tab not loaded. Refresh and try again.','err'); return; }
  const uid = prompt('Enter Guest UID (from Free Fire app → Login as Guest):');
  if(!uid) return;
  const pw = prompt('Enter Guest Password (from Free Fire app):');
  if(!pw) return;
  st.textContent = 'Validating guest account with Garena...';
  const r = await api('/api/account/guest',{method:'POST',body:{uid,pw}});
  if(r.ok){
    st.textContent = 'Created: '+r.nickname+' (UID: '+r.uid+', Pass: '+r.password+') \u2705';
    toast('Guest account '+r.nickname+' created! Level '+r.level+'.','ok');
    renderDashboard(false);
  }else{
    st.textContent = 'Failed: '+r.error;
    toast('Guest create failed: '+r.error,'err');
  }
}

async function autoSetup(){
  const st = $id('autoStatus');
  const count = Number($id('autoCount').value)||1;
  const guild = $id('autoGuild').value.trim();
  if(!guild) return toast('Guild ID required','warn');
  st.textContent = 'Auto setup running... guest accounts → squads → guild → start';
  const r = await api('/api/auto/setup',{method:'POST',body:{squad_count:count,guild_id:guild}});
  if(r.ok){
    st.textContent = 'Done: '+r.squads_created+'/'+r.squads_requested+' squads, guild job '+ (r.guild_jobs[0]?.job_id||'—');
    toast('Auto setup: '+r.message,'ok');
    renderDashboard(false);
  }else{
    st.textContent = 'Failed: '+r.error;
    toast('Auto setup failed: '+r.error,'err');
  }
}

async function createSquad(){ const members=[]; for(let i=1;i<=4;i++){ const uid=$id('cuid'+i).value.trim(); const pw=$id('cpw'+i).value.trim(); if(uid&&pw) members.push({uid,password:pw}); }
  if(!members.length) return toast('Add at least 1 UID + password','warn');
  const b=$id('createBtn'); b.disabled=true; b.innerHTML='<span class="spin"></span> Creating\u2026';
  const r=await api('/api/squad/create',{method:'POST',body:{members}}); b.disabled=false; b.textContent='\u2705 Create Squad';
  if(!r.ok) return toast(r.error||'Create failed','err'); toast('Squad '+r.squad_id+' created','ok');
  tab='dashboard'; setActiveNav(); switchTab('dashboard'); }

async function startSquad(sid){ const r=await api('/api/squad/start',{method:'POST',body:{squad_id:sid}}); r.ok?toast('Squad '+sid+' started','ok'):toast(r.error,'err'); renderDashboard(false); }
async function restartSquad(sid){ if(!await confirmBox('Restart Squad '+sid+'?','All workers will reconnect and matchmaking restarts.'))return; const r=await api('/api/squad/restart',{method:'POST',body:{squad_id:sid}}); r.ok?toast('Squad '+sid+' restarted','ok'):toast(r.error,'err'); renderDashboard(false); }
async function stopSquad(sid){ if(!await confirmBox('Stop Squad '+sid+'?','Workers will be halted until you start again.'))return; const r=await api('/api/squad/stop',{method:'POST',body:{squad_id:sid}}); r.ok?toast('Squad '+sid+' stopped','warn'):toast(r.error,'err'); renderDashboard(false); }
async function deleteSquad(sid){ if(!await confirmBox('Delete Squad '+sid+'?','This removes the squad and all its members permanently.'))return; const r=await api('/api/squad/delete',{method:'POST',body:{squad_id:sid}}); r.ok?toast('Squad '+sid+' deleted','warn'):toast(r.error,'err'); renderDashboard(false); }
async function removeMember(sid,uid){ if(!await confirmBox('Remove '+uid+'?','Member will be pulled from Squad '+sid+'.'))return; const r=await api('/api/squad/remove',{method:'POST',body:{squad_id:sid,uid}}); r.ok?toast('Removed '+uid,'ok'):toast(r.error,'err'); renderDashboard(false); }

function gloryHero(g){ return '<div class="glory-hero"><div><div class="k" style="color:var(--txt-dim);font-size:11.5px;letter-spacing:2px;text-transform:uppercase;font-weight:700">Total Glory Earned</div><div class="big">'+fmt(g.total_gained_exp)+'</div><div style="color:var(--txt-dim);font-size:13px;margin-top:10px">EXP gained across '+fmt(g.total_accounts)+' account(s)</div></div><div class="mini"><div><div class="k">Glory / Hour</div><div class="v" style="color:var(--gold)">'+fmt(g.exp_per_hour)+'</div></div><div><div class="k">Total Matches</div><div class="v">'+fmt(g.total_matches)+'</div></div><div><div class="k">In Match Now</div><div class="v" style="color:var(--saffron)">'+fmt(g.active_matches)+'</div></div></div></div>'; }

function antibanCard(ab){ if(!ab||!ab.ok) return '';
  const by = ab.bypass||{};
  const on = v => v ? '<span style="color:var(--good);font-weight:700">ON</span>' : '<span style="color:var(--bad);font-weight:700">OFF</span>';
  const list = ab.layers||[];
  const total = ab.layer_count || list.length;
  const layers = list.map((l,i)=>{
    const o = (typeof l === 'string') ? {label:l,desc:''} : l;
    return '<div class="ac-layer"><div class="n">'+String(i+1).padStart(2,'0')+'</div>'
      + '<div class="txt"><div class="l">'+esc(o.label||'')+'</div><div class="d">'+esc(o.desc||'')+'</div></div>'
      + '<div class="dot'+(o.on===false?' off':'')+'"></div></div>';
  }).join('');
  return '<div class="form-card antiban-card"><div class="ac-head"><h3>\uD83D\uDEE1\uFE0F Anti-Cheat Stack</h3>'
    + '<div class="ac-count"><b>'+total+'</b><span>layers active</span></div></div>'
    + '<p class="hint"><b style="color:var(--good)">SMART \u00B7 FAST \u00B7 SAFE</b> \u2014 fast 10\u201320s pacing, zero repeatable pattern. Bans come from <i>patterns</i>, not speed. Every layer below kills one.</p>'
    + '<div class="ab-row"><div class="ab-pill on" style="cursor:default">SMART FAST SAFE \u00B7 LOCKED \uD83D\uDD12</div></div>'
    + '<p class="hint" style="margin:16px 0 10px">Match gap <b style="color:#fff">'+ab.match_gap[0]+'\u2013'+ab.match_gap[1]+'s</b> \u00B7 cool-down every <b style="color:#fff">'+(ab.rest_after||'\u2014')+'</b> matches ('+ab.rest[0]+'\u2013'+ab.rest[1]+'s) \u00B7 session cap <b style="color:#fff">'+Math.round((ab.session_cap||5400)/60)+'min</b></p>'
    + '<div class="ac-grid">'+layers+'</div>'
    + '<p class="hint" style="margin:14px 0 0">Wire bypass \u2014 timing '+on(by.timing_jitter)+' \u00B7 packet '+on(by.packet_jitter)+' \u00B7 hello '+on(by.hello_delay)+' \u00B7 KA '+on(by.ka_jitter)+' \u00B7 safe mode '+on(by.safe_play_mode)+'</p></div>'; }

function networkCard(net){ if(!net||!net.ok) return '';
  return '<div class="networkCard"><h3>\uD83C\uDF10 Proxy Rotation</h3><p class="hint">Rotate outbound traffic across a proxy pool so no single IP carries every account. One per line \u2014 <b>http://user:pass@ip:port</b> or <b>socks5://ip:port</b>. New requests pick these up instantly.</p>\n    <textarea class="proxyBox" id="proxyBox" rows="4" spellcheck="false" placeholder="http://user:pass@1.2.3.4:8080&#10;socks5://5.6.7.8:1080">'+esc((net.proxies||[]).join('\n'))+'</textarea>\n    <div class="proxyActions"><label class="ab-pill '+(net.use_proxy?'on':'')+'" id="proxyToggle" onclick="toggleProxy()">'+(net.use_proxy?'\u25CF Enabled':'\u25CB Disabled')+'</label><button class="btn info" id="proxySave" onclick="saveProxy()">\uD83D\uDCBE Save Pool</button><button class="btn" id="proxyFetch" style="background:linear-gradient(135deg,#1fae64,#0d8a4a);color:#fff" onclick="fetchProxies()">\u26A1 Fetch Free Proxies</button><span class="proxyStatus" id="proxyStatus">'+net.count+' prox'+(net.count===1?'y':'ies')+' loaded</span></div></div>'; }

async function fetchProxies(){
  const b = $id('proxyFetch'); const st = $id('proxyStatus');
  if(b){ b.disabled = true; b.textContent = '\u23F3 Fetching\u2026'; }
  if(st) st.textContent = 'downloading GitHub lists\u2026';
  const r = await api('/api/proxy/fetch',{method:'POST',body:{limit:800,validate:true}});
  if(!r.ok){ toast(r.error||'fetch failed','err'); if(b){b.disabled=false;b.textContent='\u26A1 Fetch Free Proxies';} return; }
  // poll until the background job finishes
  for(let i=0;i<170;i++){
    const s = await api('/api/proxy/status');
    if(s && s.running===false && (s.last_run || s.last_error)){
      if(st) st.textContent = (s.alive||0)+' live proxies \u00B7 '+(s.candidates||0)+' checked';
      toast(s.last_error ? ('Proxy fetch error: '+s.last_error) : ('\u26A1 '+(s.alive||0)+' live proxies loaded'), s.last_error?'err':'ok');
      if(b){ b.disabled=false; b.textContent='\u26A1 Fetch Free Proxies'; }
      refreshGlory();
      return;
    }
    if(st) st.textContent = 'validating proxies\u2026 ('+(s.candidates||0)+' found)';
    await new Promise(r=>setTimeout(r,1500));
  }
  if(b){ b.disabled=false; b.textContent='\u26A1 Fetch Free Proxies'; }
  toast('Still checking proxies \u2014 give it another minute','warn');
}

async function toggleProxy(){ proxyEnabled=!proxyEnabled; const b=$id('proxyToggle'); if(b){ b.classList.toggle('on',proxyEnabled); b.textContent = proxyEnabled?'\u25CF Enabled':'\u25CB Disabled'; } }
async function saveProxy(){ const raw = ($id('proxyBox')||{}).value || ''; const proxies = raw.split('\n').map(s=>s.trim()).filter(Boolean);
  const r = await api('/api/network',{method:'POST',body:{proxies, enabled:proxyEnabled}});
  r.ok ? toast('Proxy pool saved ('+r.count+')','ok') : toast(r.error||'failed','err'); refreshGlory(); }

function acctCard(a, rank){
  const pct = Math.max(0, Math.min(100, Number(a.progress_pct)||0)); const st = String(a.status||'STOPPED').toUpperCase();
  const nd = Number(a.needed_for_level)||0; const isHi = a.level >= 50;
  return '<div class="acct"><span class="rank">#'+rank+'</span><div class="acct-top"><div class="avatar">'+esc(initials(a.nickname))+'</div>\n    <div style="min-width:0"><div class="nick" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(a.nickname||'?')+'</div><div class="uid">UID '+esc(a.uid)+'</div></div></div>\n    <div class="arow" style="justify-content:flex-start;gap:8px">'+statusBadge(st)+(a.is_paused?'<span class="badge b-connecting">PAUSED</span>':'')+'</div>\n    <div><div class="arow"><span class="lvl">Level '+a.level+' \u2192 '+(a.next_level||(a.level+1))+'</span><span>'+pct+'%</span></div><div class="prog '+(isHi?'hi':'')+'"><i style="width:'+pct+'%"></i></div><div class="arow" style="margin-top:6px;font-size:12px"><span>'+fmt(a.earned_in_level)+' / '+fmt(nd)+' EXP this level</span></div></div>\n    <div class="arow"><span>\u2694\uFE0F Matches</span><b>'+fmt(a.matches)+'</b></div><div class="arow"><span>\uD83D\uDD25 Glory gained</span><b style="color:var(--gold)">+'+fmt(a.gained_exp)+'</b></div><div class="arow"><span>\u23F3 To next level</span><b>'+fmt(a.remaining_exp)+'</b></div><div class="arow"><span>\uD83C\uDFF7\uFE0F '+esc(a.mode_label||a.mode||'Battle Royale')+'</span><span>'+esc(a.region||'')+'</span><div class="arow" style="margin-top:10px"><button class="btn small danger" style="width:100%" onclick="removeAccount('+esc(a.uid)+')">\uD83D\uDDD1 Remove Account</button></div></div>'; }

async function removeAccount(uid){
  if(!confirm('Remove UID '+uid+' from the dashboard?\n\nThis stops its worker and blocks it from coming back.')) return;
  const r = await api('/api/account/remove',{method:'POST',body:{uid:String(uid)}});
  r.ok ? toast('Removed '+uid,'ok') : toast(r.error||'remove failed','err');
  refreshGlory();
}

async function renderGlory(){ const c=$id('content'); if(c && !c.querySelector('.glory-hero')) c.innerHTML = topbar('Match Play for Glory','Live level-up progress')+'<div class="shimmer" style="height:140px;margin-bottom:20px"></div>'; await refreshGlory(); }
async function refreshGlory(){ const [g, ab, net] = await Promise.all([api('/api/glory'), api('/api/antiban'), api('/api/network')]); if(!g.ok) return; proxyEnabled = !!(net && net.ok && net.use_proxy); const c=$id('content'); if(!c) return;
  const accs = g.accounts||[]; c.innerHTML = topbar('Match Play for Glory','Live level-up progress')+ gloryHero(g) + '<div class="premium-2col">'+antibanCard(ab)+networkCard(net)+'</div>' + '<div class="section-title"><span class="bar"></span>Glory Leaderboard</div>' + (accs.length ? '<div class="grid-accts">'+accs.map((a,i)=>acctCard(a,i+1)).join('')+'</div>' : '<div class="empty"><span class="ei">\uD83D\uDD25</span>No accounts playing yet.<br>Create a squad and hit <b>Start</b> to begin earning glory.</div>'); }

async function setAntiban(lvl){ const r = await api('/api/antiban',{method:'POST',body:{level:lvl}}); r.ok ? toast('Anti-ban profile: '+lvl,'ok') : toast(r.error||'failed','err'); refreshGlory(); }

async function renderGuild(){ $id('content').innerHTML = topbar('Guild Ops','Join / Leave / Owner spam')+'\n  <div class="form-card"><h3>\uD83C\uDFF0 Single Account</h3><p class="hint">Run a guild action for one UID \u2014 works for accounts outside any squad too.</p>\n  <div class="form-2col" style="margin-bottom:14px"><div><label class="label">Guild ID</label><input class="inp" id="gGuildId" placeholder="Guild ID"></div><div><label class="label">Action</label><select class="inp" id="gAction"><option value="JOIN">Join</option><option value="LEAVE">Leave</option><option value="OWNER_SPAM">Owner Spam (Join + Friend Request)</option></select></div></div>\n  <div class="form-2col" style="margin-bottom:16px"><div><label class="label">UID</label><input class="inp" id="gUid" placeholder="Game UID" inputmode="numeric"></div><div><label class="label">Password</label><input class="inp" id="gPw" type="password" placeholder="Password"></div></div><button class="btn info" onclick="guildOne(this)">\uD83D\uDE80 Run For This UID</button></div>\n  <div class="form-card"><h3>\u26A1 Batch \u2014 All Squad Accounts</h3><p class="hint">Fire the action across every account currently loaded in squads.</p>\n  <div class="form-3col" style="margin-bottom:16px"><div><label class="label">Guild ID</label><input class="inp" id="gBatchGuildId" placeholder="Guild ID"></div><div><label class="label">Action</label><select class="inp" id="gBatchAction"><option value="JOIN">Join</option><option value="LEAVE">Leave</option><option value="OWNER_SPAM">Owner Spam</option></select></div><div><label class="label">Owner UID <span style="opacity:.6">(spam only)</span></label><input class="inp" id="gOwnerUid" placeholder="auto-detect if empty" inputmode="numeric"></div></div><button class="btn warn" onclick="guildBatch(this)">\u26A1 Run On All Accounts</button></div>\n  <div class="section-title"><span class="bar"></span>Recent Jobs</div><div id="guildResult"></div>'; refreshGuild(); }
async function guildOne(btn){ const guild_id=$id('gGuildId').value.trim(); const action=$id('gAction').value; const uid=$id('gUid').value.trim(); const password=$id('gPw').value.trim(); if(!guild_id||!uid||!password) return toast('Guild ID + UID + password required','warn');
  btn.disabled=true; btn.innerHTML='<span class="spin"></span> Queued\u2026'; const r=await api('/api/guild/one',{method:'POST',body:{guild_id,action,uid,password}}); btn.disabled=false; btn.textContent='\uD83D\uDE80 Run For This UID'; r.ok?toast('Guild task started for '+uid,'ok'):toast(r.error,'err'); }
async function guildBatch(btn){ const guild_id=$id('gBatchGuildId').value.trim(); const action=$id('gBatchAction').value; const owner_uid=$id('gOwnerUid').value.trim(); if(!guild_id) return toast('Guild ID required','warn');
  btn.disabled=true; btn.innerHTML='<span class="spin"></span> Launching\u2026'; const r=await api('/api/guild/run',{method:'POST',body:{guild_id,action,owner_uid}}); btn.disabled=false; btn.textContent='\u26A1 Run On All Accounts'; r.ok?toast('Batch job #'+r.job_id+' started ('+r.total+' accounts)','ok'):toast(r.error,'err'); }
async function refreshGuild(){ const [hist,d] = await Promise.all([api('/api/guild/jobs'), api('/api/status')]); const el=$id('guildResult'); if(!el) return;
  let h=''; if(d.ok && d.failed_uids && d.failed_uids.length) h+='<div class="alert red"><span class="ai">\u26A0\uFE0F</span><div><b>'+d.failed_uids.length+' failed:</b> '+d.failed_uids.map(esc).join(', ')+'</div></div>';
  if(hist&&hist.ok&&hist.jobs&&hist.jobs.length){ for(const job of hist.jobs.slice().reverse().slice(0,6)){
    const results=Object.entries(job.results||{}); const ok=results.filter(([,r])=>r.ok).length; const fail=results.filter(([,r])=>!r.ok).length;
    h+='<div class="form-card" style="margin-bottom:16px"><div class="sq-head" style="margin-bottom:14px"><h3>\uD83C\uDFAF Job #'+job.id+'</h3><span class="badge b-pending">'+esc(job.guild_id)+'</span><span class="badge b-pending">'+esc(job.action)+'</span>'+(job.done?'<span class="badge b-success"><span class="bd"></span>DONE</span>':'<span class="badge b-connecting"><span class="bd"></span>RUNNING</span>')+'</div>\n      <div class="grid-stats" style="margin-bottom:0"><div class="stat"><div class="lbl">Total</div><div class="num">'+(results.length||job.uids.length)+'</div></div><div class="stat g"><div class="lbl">Success</div><div class="num">'+ok+'</div></div><div class="stat"><div class="lbl">Failed</div><div class="num" style="background:linear-gradient(90deg,#ff8b96,#ff4d5e);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">'+fail+'</div></div></div><div class="guild-grid">';
    for(const [uid,r] of results) h+='<div class="gitem '+(r.ok?'ok':'fail')+'"><div class="u">'+esc(uid)+'<span class="badge '+(r.ok?'b-success':'b-failed')+'">'+(r.ok?'OK':'FAIL')+'</span></div>'+(r.msg?'<div class="m">'+esc(r.msg)+'</div>':'')+(r.detail?'<div class="m" style="opacity:.7">'+esc(r.detail)+'</div>':'')+'</div>';
    h+='</div></div>'; }} else h+='<div class="empty"><span class="ei">\uD83C\uDFF0</span>No guild jobs yet.</div>'; el.innerHTML=h; }

async function renderConsoles(){ const d=await api('/api/status'); if(!d.ok) return;
  let h=topbar('Consoles','Per-squad live logs')+'<div class="alert info"><span class="ai">\uD83D\uDCBB</span><div>Each squad streams its own console. Pick a squad below.</div></div>';
  if(!d.squads||!d.squads.length){ h+='<div class="empty"><span class="ei">\uD83D\uDCBB</span>No squads to display.</div>'; $id('content').innerHTML=h; return; }
  if(consoleSquad===null||!d.squads.find(s=>s.id===consoleSquad)) consoleSquad=d.squads[0].id;
  h+='<div class="console-tabs">'; for(const s of d.squads) h+='<button class="btn sm '+(consoleSquad===s.id?'info':'')+'" onclick="selectConsole('+s.id+')">\uD83D\uDCBB Squad '+s.id+'</button>'; h+='</div><div id="consoleBox"></div>'; $id('content').innerHTML=h; loadConsole(consoleSquad); }
function selectConsole(sid){ consoleSquad=sid; renderConsoles(); }
async function refreshConsoles(){ if(consoleSquad!==null) loadConsole(consoleSquad); }
async function loadConsole(sid){ const d=await api('/api/squad/logs?squad_id='+sid); const box=$id('consoleBox'); if(!box) return;
  const logs=(d.ok&&d.logs)||[]; let lines=''; if(!logs.length){ lines='<div class="log-line info"><span class="m">waiting for squad '+sid+' activity\u2026</span></div>'; }
  else { for(const l of logs) lines+='<div class="log-line '+(l.lvl||'info')+'"><span class="t">['+esc(l.t)+']</span><span class="m">'+esc(l.m)+'</span></div>'; }
  box.innerHTML='<div class="console"><div class="console-top"><span class="td t1"></span><span class="td t2"></span><span class="td t3"></span><span class="ttl">yadav@levelup:~/squad-'+sid+'$ tail -f</span></div><div class="console-body" id="consoleBody">'+lines+'<div class="log-line"><span class="m" style="color:var(--txt-dim)">$</span><span class="cursor"></span></div></div></div>'; const body=$id('consoleBody'); if(body) body.scrollTop=body.scrollHeight; }

/* BOOT */
(async function boot(){
  if(token){
    const d = await api('/api/status');
    if(d.ok){ enterApp(); return; }
    logout(true);
  }
  $id('login').style.display='flex';
  checkServer();
})();
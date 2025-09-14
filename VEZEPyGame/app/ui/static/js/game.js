(function(){
  const canvas = document.getElementById('world');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');

  // World config (simple Palworld-like vibe via biomes & critters)
  const W = canvas.width, H = canvas.height;
  const rng = (min,max)=>Math.random()*(max-min)+min;
  // Noise helpers for terrain
  const SEED = 1337;
  function hash(x,y){
    let t = x*374761393 + y*668265263 + SEED*1442695040888963407;
    t = (t ^ (t>>13)) * 1274126177;
    return ((t ^ (t>>16)) >>> 0) / 4294967295;
  }
  const lerp=(a,b,t)=>a+(b-a)*t;
  const smoothstep=(t)=>t*t*(3-2*t);
  function valueNoise2D(x,y){
    const x0=Math.floor(x),y0=Math.floor(y),x1=x0+1,y1=y0+1;
    const sx=smoothstep(x-x0), sy=smoothstep(y-y0);
    const n00=hash(x0,y0), n10=hash(x1,y0), n01=hash(x0,y1), n11=hash(x1,y1);
    const ix0=lerp(n00,n10,sx), ix1=lerp(n01,n11,sx);
    return lerp(ix0,ix1,sy);
  }
  function fbm(x,y,scale=0.05,oct=4){
    let amp=1,freq=1,sum=0,norm=0;
    for(let i=0;i<oct;i++){
      sum += valueNoise2D(x*scale*freq, y*scale*freq)*amp;
      norm += amp; amp*=0.5; freq*=2;
    }
    return sum/norm;
  }

  const player = {
    x: W/2, y: H/2, vx:0, vy:0,
    speed:2.2, baseSpeed:2.2, hp:100, xp:0, level:1,
    stamina:100, maxStamina:100,
    cds: { q: 0, e: 0 },
    rollCooldown: 0, iFrames: 0,
  };
  // Input bus: keyboard + Metaverse IO (WS)
  const keys = {}; // pressed state
  const impulses = {}; // one-shot triggers {q:true}
  window.addEventListener('keydown', e=> { keys[e.key.toLowerCase()] = true; });
  window.addEventListener('keyup', e=> { keys[e.key.toLowerCase()] = false; });
  function consumeImpulse(k){ if(impulses[k]){ delete impulses[k]; return true; } return false; }
  // Metaverse IO via WS: accepts {type:'input', press:['w'], release:['q'], impulse:{e:true}}
  (function connectInputsWS(){
    try{
      const proto = location.protocol==='https:'?'wss':'ws';
      const url = `${proto}://${location.host}/events`;
      const ws = new WebSocket(url);
      ws.onmessage = (ev)=>{
        try{
          const data = JSON.parse(ev.data);
          if(data && data.type === 'input'){
            (data.press||[]).forEach(k=> keys[String(k).toLowerCase()] = true);
            (data.release||[]).forEach(k=> keys[String(k).toLowerCase()] = false);
            const imp = data.impulse||{}; Object.keys(imp).forEach(k=> { if(imp[k]) impulses[String(k).toLowerCase()] = true; });
          }
        }catch(_){/* ignore */}
      };
      ws.onclose = ()=>{ setTimeout(connectInputsWS, 2000); };
      ws.onerror = ()=>{ try{ ws.close(); }catch(_){ } };
    }catch(_){ /* ignore in non-ws env */ }
  })();

  // Realistic terrain: height & moisture maps
  const TW=100, TH=60;
  const heightMap = Array.from({length:TH}, (_,y)=> Array.from({length:TW}, (_,x)=> fbm(x,y,0.09,4)));
  const moistMap  = Array.from({length:TH}, (_,y)=> Array.from({length:TW}, (_,x)=> fbm(x+999,y+999,0.07,3)));
  function tileColor(x,y){
    const h=heightMap[y][x], m=moistMap[y][x];
    if(h<0.35) return h<0.25?'#0b132b':'#16324f'; // deep/shallow water
    if(h<0.4) return '#c2b280'; // beach
    if(h<0.65) return m>0.55?'#0e1b12':'#233524'; // grass/forest
    if(h<0.80) return '#3a2f1b'; // highland
    return '#5a5a5a'; // mountain
  }
  function isWaterAt(px,py){
    const cw=W/TW, ch=H/TH; const x=Math.floor(px/cw), y=Math.floor(py/ch);
    if(x<0||y<0||x>=TW||y>=TH) return false;
    return heightMap[y][x] < 0.35;
  }
  function hAt(px,py){
    const cw=W/TW, ch=H/TH; const gx=px/cw, gy=py/ch;
    const x0=Math.floor(gx), y0=Math.floor(gy);
    const x1=Math.min(TW-1,x0+1), y1=Math.min(TH-1,y0+1);
    const sx=smoothstep(gx-x0), sy=smoothstep(gy-y0);
    const h00=heightMap[y0]?.[x0]??0, h10=heightMap[y0]?.[x1]??0, h01=heightMap[y1]?.[x0]??0, h11=heightMap[y1]?.[x1]??0;
    const ix0=lerp(h00,h10,sx), ix1=lerp(h01,h11,sx);
    return lerp(ix0,ix1,sy);
  }

  const critters = Array.from({length:25}, ()=>({
    x:rng(40,W-40), y:rng(40,H-40), r:rng(6,12),
    color:['#7dd3fc','#fca5a5','#a7f3d0','#fde68a'][Math.floor(Math.random()*4)],
    vx:rng(-0.7,0.7), vy:rng(-0.7,0.7)
  }));

  // NPCs (Phase 2): simple FSMs
  const npcs = Array.from({length:12}, (_,i)=>({
    id:i+1, x:rng(60,W-60), y:rng(60,H-60), vx:0, vy:0,
    speed:rng(1.2,1.8), state:'idle', timer:rng(1,3), color:'#93c5fd'
  }));

  function updateNPC(n){
    n.timer -= 0.016;
    const dx = player.x - n.x, dy = player.y - n.y; const d = Math.hypot(dx,dy);
    // State transitions
    if(d < 70 && n.state !== 'flee'){ n.state='approach'; }
    else if(d > 200 && n.state !== 'patrol'){ n.state='idle'; }

    if(n.state==='idle'){
      if(n.timer<=0){ n.state='patrol'; n.timer=rng(1.5,3.5); n.vx=rng(-1,1); n.vy=rng(-1,1); }
      else { n.vx*=0.95; n.vy*=0.95; }
    } else if(n.state==='patrol'){
      if(n.timer<=0){ n.state='idle'; n.timer=rng(0.8,1.5); }
    } else if(n.state==='approach'){
      const ux = dx/(d||1), uy = dy/(d||1);
      n.vx = ux; n.vy = uy;
      if(d<40){ n.state='flee'; n.timer=rng(0.8,1.5); }
    } else if(n.state==='flee'){
      const ux = -dx/(d||1), uy = -dy/(d||1);
      n.vx = ux; n.vy = uy;
      if(n.timer<=0) n.state='idle';
    }
    const len = Math.hypot(n.vx, n.vy) || 1;
    n.x += (n.vx/len) * n.speed;
    n.y += (n.vy/len) * n.speed;
    n.x = Math.max(12, Math.min(W-12, n.x));
    n.y = Math.max(12, Math.min(H-12, n.y));
  }

  // Boss (Phase 3)
  const boss = { x: W*0.75, y: H*0.35, r: 24, color:'#f87171', hp: 300, maxHp: 300, engaged: false, atkTimer: 0, telegraph: null, phase:1, stagger:0, exposed:0, parryT:null };
  function maybeEngageBoss(){
    const dx = boss.x - player.x, dy = boss.y - player.y; const d = Math.hypot(dx,dy);
    if(d < 60){ boss.engaged = true; }
  }
  function updateBoss(){
    if(!boss.engaged) return;
    boss.atkTimer -= 0.016;
    if(boss.atkTimer <= 0){
      if(boss.hp < boss.maxHp*0.5) boss.phase = 2;
      const roll = Math.random();
      if(roll < 0.4){
        boss.telegraph = {type:'aoe', x: boss.x, y: boss.y, r: 80, t: 0.6};
      } else if(roll < 0.8){
        boss.telegraph = {type:'aoe', x: player.x, y: player.y, r: boss.phase===1?60:80, t: 0.5};
      } else {
        spawnVolley(boss, player);
        boss.telegraph = null;
      }
      boss.parryT = boss.telegraph ? boss.telegraph.t : 0.4;
      boss.atkTimer = boss.phase===1? 3.0 : 2.2;
    }
    if(boss.telegraph){
      boss.telegraph.t -= 0.016;
      if(boss.telegraph.t <= 0){
        // Resolve damage if player is within telegraphed radius
        const tg = boss.telegraph; boss.telegraph = null;
        const dx = (tg.x - player.x), dy = (tg.y - player.y); const d = Math.hypot(dx,dy);
        const inHit = d <= tg.r;
        const parryWin = Math.abs(boss.parryT ?? 0) < 0.12 && consumeImpulse('f');
        if(inHit){
          if(parryWin){ boss.stagger = Math.min(100, boss.stagger + 30); }
          else if(player.iFrames>0){ /* dodged */ }
          else { player.hp = Math.max(0, player.hp - 18); if(window.hitFlash) window.hitFlash(); }
        }
        if(boss.stagger>=100){ boss.exposed = 2.0; boss.stagger = 0; }
      }
    }
    if(boss.exposed>0) boss.exposed = Math.max(0, boss.exposed - 0.016);
  }

  // Quests: tracked with progress and rewards
  let nextQuestId = 4;
  const quests = [
    { id:1, text:'Gather 3 glowing shards', type:'collect', need:3, have:0, rewardXp:50, main:true, done:false, rewarded:false },
    { id:2, text:'Speak with 5 NPCs', type:'talk', need:5, have:0, rewardXp:35, main:true, done:false, rewarded:false },
    { id:3, text:'Defeat the boss', type:'boss', need:1, have:0, rewardXp:100, main:true, done:false, rewarded:false },
  ];
  let rating = 0; let finished = false;
  let completionist = 0;
  const sideQuestPool = [
    { type:'explore', text:'Explore the highlands ridge', need:1, rewardXp:25 },
    { type:'collect', text:'Collect 5 forest petals', need:5, rewardXp:30 },
    { type:'talk', text:'Help 3 villagers', need:3, rewardXp:20 },
  ];
  function spawnSideQuest(){
    if(sideQuestPool.length===0) return;
    const tpl = sideQuestPool.shift();
    quests.push({ id: nextQuestId++, text: tpl.text, type: tpl.type, need: tpl.need, have:0, rewardXp: tpl.rewardXp, main:false, done:false, rewarded:false });
  }

  // Progress sync (backend)
  const getProgressUser = ()=>{
    const el = document.getElementById('mini-inv-user');
    const v = (el && el.value && el.value.trim()) || 'demo';
    return v;
  };
  async function loadProgress(){
    const u = getProgressUser();
    try{
      const res = await fetch(`/progress/${encodeURIComponent(u)}`);
      if(!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if(typeof data.xp === 'number') player.xp = data.xp;
      if(typeof data.level === 'number') player.level = data.level;
      const states = Array.isArray(data.quests) ? data.quests : [];
      states.forEach(st=>{
        const q = quests.find(q=> q.id === st.id);
        if(!q) return;
        if(typeof st.have === 'number') q.have = st.have;
        if(typeof st.need === 'number') q.need = st.need;
        if(typeof st.done === 'boolean') q.done = st.done;
        if(typeof st.rewarded === 'boolean') q.rewarded = st.rewarded;
      });
    }catch(_){ /* ignore; start fresh if offline */ }
  }
  async function saveProgress(){
    const u = getProgressUser();
    try{
      const payload = {
        user_id: u,
        xp: player.xp,
        level: player.level,
        quests: quests.map(q=>({ id:q.id, have:q.have||0, need:q.need||1, done:!!q.done, rewarded:!!q.rewarded })),
      };
      await fetch(`/progress/${encodeURIComponent(u)}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    }catch(_){ /* ignore transient errors */ }
  }
  // Kick initial progress load, then periodic save
  loadProgress();
  setInterval(saveProgress, 30000);

  function drawWorld(){
    // parallax camera offset (simple): bias background slightly opposite to player velocity for TPP feel
    const camX = -player.vx * 3;
    const camY = -player.vy * 3;
    // background terrain
    const cellW = W/TW, cellH = H/TH;
    for(let y=0;y<TH;y++){
      for(let x=0;x<TW;x++){
        ctx.fillStyle = tileColor(x,y);
        ctx.fillRect(x*cellW + camX*0.3, y*cellH + camY*0.3, cellW+1, cellH+1);
      }
    }

    // critters
    critters.forEach(c=>{
      c.x += c.vx; c.y += c.vy;
      if(c.x<c.r||c.x>W-c.r) c.vx*=-1;
      if(c.y<c.r||c.y>H-c.r) c.vy*=-1;
      ctx.beginPath();
      ctx.fillStyle = c.color;
      ctx.arc(c.x+camX*0.1,c.y+camY*0.1,c.r,0,Math.PI*2);
      ctx.fill();
    });

    // player
    ctx.beginPath();
    ctx.fillStyle = '#e5e7eb';
    ctx.arc(player.x, player.y, 10, 0, Math.PI*2);
    ctx.fill();
    // reticle (direction cue)
    const dirLen = Math.hypot(player.vx, player.vy) || 1;
    const rx = player.x + (player.vx/dirLen)*18;
    const ry = player.y + (player.vy/dirLen)*18;
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(229,231,235,0.65)';
    ctx.arc(rx, ry, 5, 0, Math.PI*2);
    ctx.stroke();

    // NPCs
    npcs.forEach(n=>{
      ctx.beginPath();
      ctx.fillStyle = n.color;
      ctx.arc(n.x+camX*0.05, n.y+camY*0.05, 6, 0, Math.PI*2);
      ctx.fill();
    });

    // Boss
    ctx.beginPath();
    ctx.fillStyle = boss.color;
    ctx.arc(boss.x+camX*0.03, boss.y+camY*0.03, boss.r, 0, Math.PI*2);
    ctx.fill();
  if(boss.engaged){
      // Telegraph
      if(boss.telegraph){
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(248,113,113,0.6)';
        ctx.setLineDash([8,6]);
        ctx.arc(boss.telegraph.x, boss.telegraph.y, boss.telegraph.r, 0, Math.PI*2);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      // Boss bars now shown in sidebar HUD
    }

    // UI overlay
      // HUD moved to sidebar (updated via updateHUD())
      if(window.updateHUD){
        window.updateHUD({
          hp: player.hp, maxHp: 100,
          stamina: player.stamina, maxStamina: player.maxStamina,
          cds: { q: player.cds.q, e: player.cds.e, dodge: player.rollCooldown },
          lock: !!lockTarget,
          rating, completionist, finished,
          level: player.level, xp: player.xp,
          boss: { hp: boss.hp, maxHp: boss.maxHp, stagger: boss.stagger, engaged: boss.engaged, phase: boss.phase },
        });
      }
    // Completion and other HUD elements are in sidebar
  }

  function update(){
    // movement & sprint
    player.vx = (keys['d']||keys['arrowright']?1:0) - (keys['a']||keys['arrowleft']?1:0);
    player.vy = (keys['s']||keys['arrowdown']?1:0) - (keys['w']||keys['arrowup']?1:0);
    const len = Math.hypot(player.vx, player.vy) || 1;
    const sprinting = (keys['shift'] && (keys['w']||keys['arrowup']));
    const canSprint = sprinting && player.stamina > 0;
    player.speed = player.baseSpeed * (canSprint ? 1.8 : 1);
    // slope-aware movement + avoid water
    const nextX = player.x + (player.vx/len) * player.speed;
    const nextY = player.y + (player.vy/len) * player.speed;
    const h0 = hAt(player.x, player.y), h1 = hAt(nextX, nextY);
    const dh = h1 - h0;
    const slopeMul = 1 - Math.max(-0.15, Math.min(0.15, dh*2.5));
    const stepX = (player.vx/len) * player.speed * slopeMul;
    const stepY = (player.vy/len) * player.speed * slopeMul;
    const tx = player.x + stepX, ty = player.y + stepY;
    if(!isWaterAt(tx, player.y)) player.x = tx;
    if(!isWaterAt(player.x, ty)) player.y = ty;
    player.x = Math.max(10, Math.min(W-10, player.x));
    player.y = Math.max(10, Math.min(H-10, player.y));
    // stamina drain/regain
    if(canSprint){ player.stamina = Math.max(0, player.stamina - 0.5); }
    else { player.stamina = Math.min(player.maxStamina, player.stamina + 0.25); }
    if(player.rollCooldown>0) player.rollCooldown = Math.max(0, player.rollCooldown - 0.016);
    if(player.iFrames>0) player.iFrames = Math.max(0, player.iFrames - 0.016);

    // abilities (E interact, Q ability) with simple cooldowns
    if(player.cds.q>0) player.cds.q = Math.max(0, player.cds.q - 0.016);
    if(player.cds.e>0) player.cds.e = Math.max(0, player.cds.e - 0.016);
    if((keys['q'] || consumeImpulse('q')) && player.cds.q === 0){
      // radial pulse (visual only)
      pulse( player.x, player.y );
      player.cds.q = 5.0; // 5s cooldown
    }
    if((keys['e'] || consumeImpulse('e')) && player.cds.e === 0){
      // interact: attract nearby critters briefly
      interact();
      player.cds.e = 3.0; // 3s cooldown
      // engage boss if near
      maybeEngageBoss();
    }
    // roll/dodge with i-frames
    if((keys[' '] || consumeImpulse(' ')) && player.rollCooldown===0 && player.stamina>10){
      const len2 = Math.hypot(player.vx, player.vy) || 1;
      const ux = (player.vx||1)/len2, uy=(player.vy||0)/len2;
      player.x += ux*22; player.y += uy*22;
      player.iFrames = 0.45; player.rollCooldown = 1.0; player.stamina -= 12;
    }

    // simple progression: gain tiny xp over time
    player.xp += 0.02;
    if(player.xp >= 10*player.level){ player.level++; }

    // update DOM side panels
      // Update sidebar HUD
      if(window.updateHUD){
        window.updateHUD({
          hp: player.hp, maxHp: 100,
          stamina: player.stamina, maxStamina: player.maxStamina,
          cds: { q: player.cds.q, e: player.cds.e, dodge: player.rollCooldown },
          lock: !!lockTarget,
          rating, completionist, finished,
          level: player.level, xp: player.xp,
          boss: { hp: boss.hp, maxHp: boss.maxHp, stagger: boss.stagger, engaged: boss.engaged, phase: boss.phase },
        });
      }
      const q = document.getElementById('quests');
      if(q){
        q.innerHTML = '';
        quests.forEach(quest=>{
          const pct = Math.min(100, Math.floor((quest.have/(quest.need||1))*100));
          const li = document.createElement('li');
          li.innerHTML = `• ${quest.text} <span style="float:right;color:#9aa">${(quest.have||0).toFixed(quest.type==='collect'?1:0)}/${quest.need||1}</span>
            <div style="background:#1f2937;height:6px;border-radius:4px;margin-top:4px"><div style="height:6px;border-radius:4px;background:${quest.done?'#10b981':'#60a5fa'};width:${pct}%"></div></div>`;
          q.appendChild(li);
        });
        const mains = quests.filter(q=>q.main);
        const totalNeed = mains.reduce((s,q)=> s + (q.need||1), 0);
        const totalHave = mains.reduce((s,q)=> s + (q.have||0), 0);
        rating = Math.min(100, Math.floor((totalHave/totalNeed)*100));
        finished = mains.every(q=> q.done);
        const totalNeedAll = quests.reduce((s,q)=> s + (q.need||1), 0);
        const totalHaveAll = quests.reduce((s,q)=> s + (q.have||0), 0);
        completionist = Math.min(100, Math.floor((totalHaveAll/Math.max(1,totalNeedAll))*100));
      }

  // NPC and Boss updates
  npcs.forEach(updateNPC);
  updateBoss();
  updateCombat();

    // Minor contact damage if too close to boss while engaged
    if(boss.engaged){
      const dx = boss.x - player.x, dy = boss.y - player.y; const d = Math.hypot(dx,dy);
  if(d < boss.r+6 && player.iFrames<=0){ player.hp = Math.max(0, player.hp - 0.1); if(window.hitFlash) window.hitFlash(); }
    }

    // Quest updates and rewards
    const qCollect = quests.find(q=>q.type==='collect' && !q.done);
    if(qCollect){
      let nearby = 0; critters.forEach(c=>{ if(Math.hypot(c.x-player.x, c.y-player.y) < 40) nearby++; });
      if(nearby>=1){ qCollect.have = Math.min(qCollect.need, (qCollect.have||0) + 0.01); }
      if(qCollect.have>=qCollect.need){
        qCollect.have=qCollect.need; qCollect.done=true;
        if(!qCollect.rewarded){
          player.xp+=qCollect.rewardXp; qCollect.rewarded=true; spawnSideQuest();
          addToast('Quest complete: '+qCollect.text);
          award('glow_shard', Math.max(1, Math.round(qCollect.need||1)));
          // persist important milestones promptly
          saveProgress();
        }
      }
    }
    const qTalk = quests.find(q=>q.type==='talk' && !q.done);
    if(qTalk && (window.__talked_once__||0)>0){
      qTalk.have = Math.min(qTalk.need, (qTalk.have||0) + (window.__talked_once__||0)); window.__talked_once__=0;
      if(qTalk.have>=qTalk.need){
        qTalk.have=qTalk.need; qTalk.done=true;
        if(!qTalk.rewarded){
          player.xp+=qTalk.rewardXp; qTalk.rewarded=true; spawnSideQuest();
          addToast('Quest complete: '+qTalk.text);
          award('villager_token', 1);
          saveProgress();
        }
      }
    }
    const qBoss = quests.find(q=>q.type==='boss' && !q.done);
    if(qBoss && boss.hp<=0){
      qBoss.have = qBoss.need; qBoss.done=true;
      if(!qBoss.rewarded){
        player.xp+=qBoss.rewardXp; qBoss.rewarded=true;
        addToast('Boss defeated!');
        award('boss_trophy', 1);
        award('legendary_core', 1);
        saveProgress();
      }
    }

  }

  // visual pulse effect
  let pulses = [];
  function pulse(x,y){
    pulses.push({x,y,r:8,alpha:0.9});
  }
  function drawPulses(){
    pulses.forEach(p=>{
      p.r += 3; p.alpha *= 0.95;
      ctx.beginPath();
      ctx.strokeStyle = `rgba(124,77,255,${p.alpha})`;
      ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
      ctx.stroke();
    });
    pulses = pulses.filter(p=> p.alpha > 0.05);
  }
  function drawProjectiles(){
    projectiles.forEach(p=>{
      ctx.beginPath(); ctx.fillStyle='#f59e0b'; ctx.arc(p.x, p.y, 4, 0, Math.PI*2); ctx.fill();
    });
  }
  function drawSwings(){
    swings.forEach(s=>{
      const alpha = Math.max(0, Math.min(1, s.t/0.18));
      ctx.beginPath(); ctx.strokeStyle = `rgba(236,253,245,${alpha})`; ctx.lineWidth = (s.r>20? 4:2);
      ctx.arc(player.x, player.y, s.r+8*(1-alpha), 0, Math.PI*2); ctx.stroke(); ctx.lineWidth=1;
    });
  }

  // Simple toasts system
  let toasts=[];
  function addToast(msg){ toasts.push({msg, t: 2.8}); }
  async function award(sku, qty){
    try{
      addToast(`+ ${sku} x${qty}`);
      await fetch(`/inventory/${encodeURIComponent('demo')}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ sku, qty }) });
    }catch(_){ /* ignore network issues */ }
  }
  function drawToasts(){
    // draw top-right stacked
    const x = W - 10, y0 = 14; let y = y0;
    for(let i=toasts.length-1;i>=0;i--){ const t=toasts[i];
      t.t -= 0.016; if(t.t<=0){ toasts.splice(i,1); continue; }
    }
    ctx.textAlign='right'; ctx.font='13px system-ui';
    toasts.forEach(t=>{
      const w = ctx.measureText(t.msg).width + 16;
      ctx.fillStyle='rgba(0,0,0,0.55)'; ctx.fillRect(x-w, y-12, w, 20);
      ctx.fillStyle='#e5e7eb'; ctx.fillText(t.msg, x-8, y+2);
      y += 24;
    });
    ctx.textAlign='left';
  }

  function interact(){
    // pull nearby critters slightly towards player for a moment
    critters.forEach(c=>{
      const dx = player.x - c.x, dy = player.y - c.y;
      const d = Math.hypot(dx,dy);
      if(d < 120){ c.vx += (dx/d)*0.2; c.vy += (dy/d)*0.2; }
    });
    // NPC dialog
    const n = nearestNPC(80);
    if(n){
      const modal = document.getElementById('modal');
      const title = document.getElementById('modal-title');
      const body = document.getElementById('modal-body');
      if(modal && title && body){
        title.textContent = 'Villager';
        body.innerHTML = '<div>Welcome, traveler! Beware the boss to the east. Press Q/E to use abilities, Space to dodge, F to parry!</div>';
        modal.style.display = 'flex';
        window.__talked_once__ = (window.__talked_once__||0) + 1;
      }
    }
  }

  // Lock-on and combat
  function nearestNPC(radius){
    let best=null, bd=1e9; npcs.forEach(n=>{ const d=Math.hypot(n.x-player.x, n.y-player.y); if(d<bd){ bd=d; best=n; } });
    return bd<=radius?best:null;
  }
  let lockTarget=null;
  function findLockTarget(){
    const db=Math.hypot(boss.x-player.x,boss.y-player.y);
    if(db<200) return boss; return nearestNPC(200);
  }
  window.addEventListener('keydown', (e)=>{
    if(e.key==='Tab'){ e.preventDefault(); lockTarget = findLockTarget(); }
    const k=e.key.toLowerCase(); if(k==='j'||k==='k'||k==='f'||k===' '){ impulses[k]=true; }
  }, true);
  canvas.addEventListener('mousedown', ()=>{ impulses['j']=true; });

  const swings=[]; const projectiles=[];
  function spawnSwing(kind){
    const rad = kind==='heavy'?26:18; const dmg = kind==='heavy'?22:12;
    swings.push({x:player.x, y:player.y, r:rad, t:0.18, dmg});
  }
  function spawnVolley(src,dst){
    for(let i=0;i<5;i++){
      const ang = Math.atan2(dst.y-src.y, dst.x-src.x) + (i-2)*0.15;
      projectiles.push({x:src.x, y:src.y, vx:Math.cos(ang)*3.0, vy:Math.sin(ang)*3.0, t:3.0});
    }
  }
  function updateCombat(){
    // swings
    for(let i=swings.length-1;i>=0;i--){ const s=swings[i]; s.t-=0.016; if(s.t<=0){ swings.splice(i,1); continue; }
      const db = Math.hypot(boss.x - s.x, boss.y - s.y);
      if(boss.engaged && db <= boss.r + s.r){
        const mult = boss.exposed>0 ? 2.0 : 1.0;
        const dmg = s.dmg*mult; boss.hp = Math.max(0, boss.hp - dmg); boss.stagger = Math.min(100, boss.stagger + (s.dmg*0.5));
      }
    }
    // projectiles
    for(let i=projectiles.length-1;i>=0;i--){ const p=projectiles[i]; p.t-=0.016; p.x+=p.vx; p.y+=p.vy; if(p.t<=0){ projectiles.splice(i,1); continue; }
      if(Math.hypot(p.x-player.x, p.y-player.y) < 10){ if(player.iFrames<=0){ player.hp=Math.max(0,player.hp-8);} projectiles.splice(i,1); }
    }
    // inputs
    if(consumeImpulse('j')) spawnSwing('light');
    if(consumeImpulse('k')) { if(player.stamina>8){ spawnSwing('heavy'); player.stamina-=8; } }
  }

  function loop(){
    // If 2D canvas hidden (3D mode active), keep loop lightweight
    if(canvas.style.display === 'none'){
      requestAnimationFrame(loop);
      return;
    }
    ctx.clearRect(0,0,W,H);
    drawWorld();
    drawPulses();
    drawProjectiles();
    drawSwings();
    drawToasts();
    update();
    requestAnimationFrame(loop);
  }
  loop();
})();

(function(){
  const canvas = document.getElementById('world');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');

  // World config (simple Palworld-like vibe via biomes & critters)
  const W = canvas.width, H = canvas.height;
  const rng = (min,max)=>Math.random()*(max-min)+min;

  const player = { x: W/2, y: H/2, vx:0, vy:0, speed:2.2, hp:100, xp:0, level:1 };
  const keys = {};
  window.addEventListener('keydown', e=> keys[e.key.toLowerCase()] = true);
  window.addEventListener('keyup', e=> keys[e.key.toLowerCase()] = false);

  const biomes = [
    { name:'Meadow', color:'#0e1b12' },
    { name:'Shore', color:'#0b1a24' },
    { name:'Mesa', color:'#23160f' },
  ];
  const biomeMap = [];
  for(let y=0;y<60;y++){
    const row=[];
    for(let x=0;x<100;x++){
      row.push(biomes[Math.floor(Math.random()*biomes.length)]);
    }
    biomeMap.push(row);
  }

  const critters = Array.from({length:25}, ()=>({
    x:rng(40,W-40), y:rng(40,H-40), r:rng(6,12),
    color:['#7dd3fc','#fca5a5','#a7f3d0','#fde68a'][Math.floor(Math.random()*4)],
    vx:rng(-0.7,0.7), vy:rng(-0.7,0.7)
  }));

  const quests = [
    { id:1, text:'Gather 3 glowing shards', done:false },
    { id:2, text:'Tame a sky-flutter', done:false },
    { id:3, text:'Explore the mesa biome', done:false },
  ];

  function drawWorld(){
    // background biomes
    const cellW = W/100, cellH = H/60;
    for(let y=0;y<60;y++){
      for(let x=0;x<100;x++){
        ctx.fillStyle = biomeMap[y][x].color;
        ctx.fillRect(x*cellW, y*cellH, cellW, cellH);
      }
    }

    // critters
    critters.forEach(c=>{
      c.x += c.vx; c.y += c.vy;
      if(c.x<c.r||c.x>W-c.r) c.vx*=-1;
      if(c.y<c.r||c.y>H-c.r) c.vy*=-1;
      ctx.beginPath();
      ctx.fillStyle = c.color;
      ctx.arc(c.x,c.y,c.r,0,Math.PI*2);
      ctx.fill();
    });

    // player
    ctx.beginPath();
    ctx.fillStyle = '#e5e7eb';
    ctx.arc(player.x, player.y, 10, 0, Math.PI*2);
    ctx.fill();

    // UI overlay
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.fillRect(10,10,200,60);
    ctx.fillStyle = '#d1d5db';
    ctx.font = '14px system-ui';
    ctx.fillText(`HP ${player.hp}`, 20, 32);
    ctx.fillText(`Lv ${player.level}  XP ${player.xp}`, 20, 52);
  }

  function update(){
    player.vx = (keys['d']||keys['arrowright']?1:0) - (keys['a']||keys['arrowleft']?1:0);
    player.vy = (keys['s']||keys['arrowdown']?1:0) - (keys['w']||keys['arrowup']?1:0);
    const len = Math.hypot(player.vx, player.vy) || 1;
    player.x += player.vx/len * player.speed;
    player.y += player.vy/len * player.speed;
    player.x = Math.max(10, Math.min(W-10, player.x));
    player.y = Math.max(10, Math.min(H-10, player.y));

    // simple progression: gain tiny xp over time
    player.xp += 0.02;
    if(player.xp >= 10*player.level){ player.level++; }

    // update DOM side panels
    const stats = document.getElementById('player-stats');
    if(stats){
      stats.innerHTML = `
        <div>HP: ${player.hp.toFixed(0)}</div>
        <div>Level: ${player.level}</div>
        <div>XP: ${player.xp.toFixed(1)}</div>
      `;
    }
    const q = document.getElementById('quests');
    if(q && !q.dataset.inited){
      quests.forEach(quest=>{
        const li = document.createElement('li');
        li.textContent = `• ${quest.text}`;
        q.appendChild(li);
      });
      q.dataset.inited = '1';
    }
  }

  function loop(){
    ctx.clearRect(0,0,W,H);
    drawWorld();
    update();
    requestAnimationFrame(loop);
  }
  loop();
})();

export async function start3D({ THREE, mount, world }){
  // Basic three.js scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f1624);
  scene.fog = null;
  const camera = new THREE.PerspectiveCamera(60, (mount.clientWidth||960)/(mount.clientHeight||540), 0.1, 1000);
  camera.position.set(0, 6, 12);
  const renderer = new THREE.WebGLRenderer({ antialias:true });
  renderer.setSize(mount.clientWidth||960, mount.clientHeight||540);
  mount.appendChild(renderer.domElement);

  // Lights
  const hemi = new THREE.HemisphereLight(0xffffff, 0x202020, 0.8);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8); dir.position.set(5,10,2); scene.add(dir);

  // Worlds presets and dynamic ground rebuild
  const matEarth = new THREE.MeshStandardMaterial({ color: 0x1f3d2d, roughness:0.9, metalness:0.1 });
  const matVeze  = new THREE.MeshStandardMaterial({ color: 0x09111a, roughness:0.6, metalness:0.2 });
  const matDunes = new THREE.MeshStandardMaterial({ color: 0xc2a574, roughness:1.0, metalness:0.0 });
  const matSnow  = new THREE.MeshStandardMaterial({ color: 0xf5f7fb, roughness:0.98, metalness:0.02 });
  let groundGeo = new THREE.PlaneGeometry(200,200,1,1);
  const ground = new THREE.Mesh(groundGeo, matEarth);
  ground.rotation.x = -Math.PI/2; ground.receiveShadow = true; scene.add(ground);
  // Single grid helper, styled for VEZE; hidden on EARTH
  const grid = new THREE.GridHelper(200, 80, 0x22d3ee, 0x0ea5e9);
  grid.material.opacity = 0.2; grid.material.transparent = true; grid.position.y = 0.01; scene.add(grid);
  grid.visible = false;

  // Snow particle system (created on-demand for SNOW)
  let snow = null; let snowParams = { count: 1500, area: 160, yTop: 40, yBottom: -2, fall: 8 };
  function ensureSnow(on){
    if(on && !snow){
      const g = new THREE.BufferGeometry();
      const n = snowParams.count; const area = snowParams.area;
      const pos = new Float32Array(n*3);
      for(let i=0;i<n;i++){
        pos[i*3+0] = (Math.random()*2-1) * area;
        pos[i*3+1] = Math.random()*snowParams.yTop;
        pos[i*3+2] = (Math.random()*2-1) * area;
      }
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      const m = new THREE.PointsMaterial({ color: 0xffffff, size: 0.08, transparent:true, opacity:0.9, depthWrite:false });
      snow = new THREE.Points(g, m);
      scene.add(snow);
    } else if(!on && snow){
      scene.remove(snow); snow.geometry.dispose?.(); snow.material.dispose?.(); snow=null;
    }
  }

  function displaceEarth(posAttr){
    for(let i=0;i<posAttr.count;i++){
      const x = posAttr.getX(i); const y = posAttr.getY(i);
      const h = (Math.sin(x*0.08) * Math.cos(y*0.07) + Math.sin((x+y)*0.03)) * 1.6;
      posAttr.setZ(i, h);
    }
  }
  function displaceDunes(posAttr){
    for(let i=0;i<posAttr.count;i++){
      const x = posAttr.getX(i); const y = posAttr.getY(i);
      // Dune-like ridges: layered sine waves with absolute to sharpen crests
      const r1 = Math.abs(Math.sin(x*0.05) * Math.cos(y*0.02));
      const r2 = Math.abs(Math.sin((x*0.12 + y*0.07)))*0.6;
      const base = (r1*1.2 + r2) * 2.2; // height ~ like desert dunes
      posAttr.setZ(i, base - 1.2);
    }
  }
  function displaceSnow(posAttr){
    for(let i=0;i<posAttr.count;i++){
      const x = posAttr.getX(i); const y = posAttr.getY(i);
      const h = (Math.sin(x*0.03) + Math.cos(y*0.04) + Math.sin((x+y)*0.02)) * 0.8;
      posAttr.setZ(i, h);
    }
  }

  function rebuildGroundFor(name){
    const nm = String(name||'EARTH').toUpperCase();
    let seg = 1; let mat = matEarth; let fog = null; let showGrid=false;
    if(nm==='EARTH'){ seg=120; mat=matEarth; showGrid=false; fog=null; }
    else if(nm==='VEZE'){ seg=1; mat=matVeze; showGrid=true; fog=null; }
    else if(nm==='DUNES'){ seg=180; mat=matDunes; showGrid=false; fog=null; }
    else if(nm==='SNOW'){ seg=140; mat=matSnow; showGrid=false; fog=new THREE.Fog(0xcfe7ff, 20, 140); }
    // geometry
    const geo = new THREE.PlaneGeometry(200,200,seg,seg);
    const pos = geo.attributes.position;
    if(nm==='EARTH') displaceEarth(pos);
    else if(nm==='DUNES') displaceDunes(pos);
    else if(nm==='SNOW') displaceSnow(pos);
    geo.computeVertexNormals();
    ground.geometry.dispose?.();
    ground.geometry = geo; groundGeo = geo;
    ground.material = mat;
    grid.visible = showGrid;
    // lighting accents
    if(nm==='VEZE'){ dir.color.setHex(0x6ee7b7); hemi.color.setHex(0x60a5fa); scene.background = new THREE.Color(0x0b0e14); scene.fog = null; ensureSnow(false); }
    else if(nm==='EARTH'){ dir.color.setHex(0xffffff); hemi.color.setHex(0xffffff); scene.background = new THREE.Color(0x0f1624); scene.fog = null; ensureSnow(false); }
    else if(nm==='DUNES'){ dir.color.setHex(0xffe0a3); hemi.color.setHex(0xfff1c2); scene.background = new THREE.Color(0x33230f); scene.fog = null; ensureSnow(false); }
    else if(nm==='SNOW'){ dir.color.setHex(0xeaf3ff); hemi.color.setHex(0xccddff); scene.background = new THREE.Color(0xbfd7ff); scene.fog = fog; ensureSnow(true); }
    // Rebuild navmesh for new terrain
    if(typeof buildNavMesh === 'function') buildNavMesh();
  }

  function applyWorld(name){ rebuildGroundFor(name); }
  applyWorld(world||'EARTH');

  // Player: try GLTF, fallback to procedural full-body avatar (primitives)
  const player = new THREE.Group(); scene.add(player);
  function buildProceduralAvatar(){
    const group = new THREE.Group();
    const skin = new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness:0.6, metalness:0.1 });
    // Torso
    const torso = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.2, 0.5), skin); torso.position.y = 1.6; group.add(torso);
    // Head
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.32, 16, 16), skin); head.position.y = 2.5; group.add(head);
    // Arms
    const lArm = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.9, 12), skin); lArm.position.set(-0.65, 1.7, 0); lArm.rotation.z = Math.PI/2.2; group.add(lArm);
    const rArm = lArm.clone(); rArm.position.x = 0.65; rArm.rotation.z = -Math.PI/2.2; group.add(rArm);
    // Legs
    const lLeg = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 1.1, 12), skin); lLeg.position.set(-0.28, 0.6, 0); group.add(lLeg);
    const rLeg = lLeg.clone(); rLeg.position.x = 0.28; group.add(rLeg);
    group.userData.limbRefs = { lArm, rArm, lLeg, rLeg };
    group.userData.isFallback = true;
    return group;
  }
  let body = buildProceduralAvatar();
  player.add(body);
  player.position.set(0, 1, 0);
  let mixer = null; let actions = {}; let activeAction = null;
  async function tryLoadGLTF(){
    try{
      // Prefer locally bundled loader to avoid CSP/external dependency
      let GLTFLoaderCtor = null;
      try{
        ({ GLTFLoader: GLTFLoaderCtor } = await import('/static/js/vendor/GLTFLoader.js'));
      }catch(e){
        // Support non-module loader that attaches to global THREE
        GLTFLoaderCtor = (window && window.THREE && window.THREE.GLTFLoader) ? window.THREE.GLTFLoader : null;
      }
      if(!GLTFLoaderCtor) throw new Error('GLTFLoader not available locally');
      const loader = new GLTFLoaderCtor();
      // Optional: DRACO support if available
      try{
        let DRACOLoaderCtor = null;
        try{ ({ DRACOLoader: DRACOLoaderCtor } = await import('/static/js/vendor/DRACOLoader.js')); }
        catch(_e){ DRACOLoaderCtor = (window && window.THREE && window.THREE.DRACOLoader) ? window.THREE.DRACOLoader : null; }
        if(DRACOLoaderCtor){
          const dracoLoader = new DRACOLoaderCtor();
          // Expect decoders under /static/js/vendor/draco/ (place .wasm/.js there)
          dracoLoader.setDecoderPath('/static/js/vendor/draco/');
          if(typeof loader.setDRACOLoader === 'function') loader.setDRACOLoader(dracoLoader);
        }
      }catch(_){ /* optional */ }
      // Load your local model (drop hero.glb under /static/models/)
      const url = '/static/models/hero.glb';
      const gltf = await loader.loadAsync(url);
      const model = gltf.scene;
      model.scale.set(1.0, 1.0, 1.0);
      // Replace fallback
      player.remove(body); body.geometry.dispose?.(); body.material.dispose?.();
      body = model; body.userData.isFallback = false; player.add(body);
      // Animations
      mixer = new THREE.AnimationMixer(body);
      gltf.animations.forEach(clip=>{
        actions[clip.name] = mixer.clipAction(clip);
      });
      // default to Idle
      if(actions['Idle']){ activeAction = actions['Idle']; activeAction.play(); }
    }catch(_){ /* missing loader or asset: keep fallback capsule */ }
  }
  tryLoadGLTF();

  // NPCs/Boss: simple colored capsules
  const npcs = [];
  function randomPoint(range=15){ return new THREE.Vector3((Math.random()*2-1)*range, 1, (Math.random()*2-1)*range); }
  for(let i=0;i<8;i++){
    const g = new THREE.Mesh(new THREE.CapsuleGeometry(0.4, 0.9, 4, 8), new THREE.MeshStandardMaterial({ color: 0x93c5fd }));
    g.position.copy(randomPoint()); scene.add(g);
    npcs.push({mesh:g, state:'idle', timer: Math.random()*2+1, waypoint: randomPoint(), speed: 2.2});
  }
  const boss = new THREE.Mesh(new THREE.CapsuleGeometry(0.7, 1.8, 6, 12), new THREE.MeshStandardMaterial({ color: 0xf87171 }));
  boss.position.set(8,1, -6); scene.add(boss);
  const bossState = { hp: 500, max: 500, engaged:false, atkT: 0, phase:1, stagger:0, exposed:0 };

  // Progress sync (3D: xp/level only)
  const getProgressUser = ()=>{ const el = document.getElementById('mini-inv-user'); return (el && el.value && el.value.trim()) || 'demo'; };
  let xp3d = 0, lvl3d = 1;
  async function loadProgress(){ try{ const res = await fetch(`/progress/${encodeURIComponent(getProgressUser())}`); if(res.ok){ const d=await res.json(); if(typeof d.xp==='number') xp3d=d.xp; if(typeof d.level==='number') lvl3d=d.level; } }catch(_){}}
  async function saveProgress(){ try{ const p={ user_id:getProgressUser(), xp: xp3d, level: lvl3d, quests: [] }; await fetch(`/progress/${encodeURIComponent(p.user_id)}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(p) }); }catch(_){}}
  loadProgress(); setInterval(saveProgress, 30000);

  // Input and movement
  const keys = new Set();
  window.addEventListener('keydown', (e)=> keys.add(e.key.toLowerCase()));
  window.addEventListener('keyup',   (e)=> keys.delete(e.key.toLowerCase()));
  const vel = new THREE.Vector3();
  const forward = new THREE.Vector3();
  const right = new THREE.Vector3();
  let stamina=100, maxStamina=100, rollCD=0, iFrames=0;
  let hp=120, maxHp=120; // simple 3D placeholder vitals
  const baseSpeed=4.0;

  // Camera follow
  const camTarget = new THREE.Vector3();

  // Projectiles & Telegraphs
  const projectiles = [];
  const telegraphs = [];
  function spawnVolley(src, dst){
    for(let i=0;i<5;i++){
      const dirv = new THREE.Vector3().subVectors(dst, src).normalize();
      const angle = (i-2)*0.12;
      const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0), angle);
      dirv.applyQuaternion(q);
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), new THREE.MeshStandardMaterial({ color: 0xf59e0b }));
      m.position.copy(src.clone().add(new THREE.Vector3(0,0.9,0)));
      scene.add(m);
      projectiles.push({mesh:m, v: dirv.multiplyScalar(8), t:3});
    }
  }
  function spawnRing(pos, radius=2, color=0xf87171, life=0.8){
    const ringGeo = new THREE.RingGeometry(radius*0.95, radius, 32);
    const ringMat = new THREE.MeshBasicMaterial({ color, transparent:true, opacity:0.6, side:THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI/2; ring.position.copy(pos.clone());
    scene.add(ring);
    telegraphs.push({mesh:ring, t: life, radius});
  }

  // Time anchors (simple)
  let anchor = null;
  function setAnchor(){ anchor = { p: player.position.clone(), t: performance.now() }; }
  function rewind(){ if(anchor){ player.position.copy(anchor.p); } }
  function forwardStep(){ player.position.add(new THREE.Vector3(0,0,-1)); }

  // Public API for outer UI
  const api = {
    pause(){ paused = true; },
    resume(){ paused = false; },
    setWorld(name){ applyWorld(name); },
    anchor: setAnchor,
    rewind,
    forward: forwardStep,
  };

  // Main loop
  let paused = false;
  const tmp = new THREE.Vector3();
  // Camera shake on damage (subtle, decays)
  let shakeT = 0, shakeAmp = 0;
  
  // three-pathfinding integration (local vendor preferred, CDN fallback)
  let Pathfinding = null; let pathfinder = null; const zoneId = 'level';
  async function importPathfinding(){
    if(Pathfinding) return;
    try{
      ({ Pathfinding } = await import('/static/js/vendor/three-pathfinding.module.js'));
    }catch(_e){
      try{ ({ Pathfinding } = await import('https://unpkg.com/three-pathfinding@0.9.0/dist/three-pathfinding.module.js')); }
      catch(_){ Pathfinding = null; }
    }
  }
  async function buildNavMesh(){
    await importPathfinding();
    if(!Pathfinding){ pathfinder = null; return; }
    try{
      pathfinder = new Pathfinding();
      // Prefer baked navmesh zone/geometry if available
      let zone = null;
      try{
        const zres = await fetch('/static/models/navmesh.zone.json', { cache: 'no-store' });
        if(zres.ok){ zone = await zres.json(); }
      }catch(_){ /* ignore */ }
      if(!zone){
        try{
          let GLTFLoaderCtor = null;
          try{ ({ GLTFLoader: GLTFLoaderCtor } = await import('/static/js/vendor/GLTFLoader.js')); }
          catch(e){ GLTFLoaderCtor = (window && window.THREE && window.THREE.GLTFLoader) ? window.THREE.GLTFLoader : null; }
          if(GLTFLoaderCtor){
            const loader = new GLTFLoaderCtor();
            const glb = await loader.loadAsync('/static/models/navmesh.glb');
            const mesh = glb.scene.getObjectByProperty('type','Mesh') || glb.scene.children.find(n=> n.isMesh);
            if(mesh && mesh.geometry){
              const navGeo2 = mesh.geometry.clone();
              navGeo2.computeVertexNormals?.();
              zone = Pathfinding.createZone(navGeo2);
            }
          }
        }catch(_){ /* ignore */ }
      }
      if(!zone){
        // Fallback to ground-derived zone
        ground.updateMatrixWorld(true);
        const navGeo = ground.geometry.clone();
        if(typeof navGeo.applyMatrix4 === 'function') navGeo.applyMatrix4(ground.matrixWorld);
        zone = Pathfinding.createZone(navGeo);
      }
      if(zone){ pathfinder.setZoneData(zoneId, zone); }
    }catch(_){ pathfinder = null; }
  }
  // Initial navmesh build (async)
  buildNavMesh();
  // Simple grid A* pathfinding over ground extents (fallback when no navmesh)
  const nav = { cols: 60, rows: 60, half: 100 }; // ground is ~200x200
  function w2g(v){ // world to grid
    const gx = Math.floor((v.x + nav.half) / (2*nav.half) * nav.cols);
    const gy = Math.floor((v.z + nav.half) / (2*nav.half) * nav.rows);
    return {x: Math.max(0, Math.min(nav.cols-1, gx)), y: Math.max(0, Math.min(nav.rows-1, gy))};
  }
  function g2w(n){ // grid to world (center of cell)
    const cw = (2*nav.half)/nav.cols, ch = (2*nav.half)/nav.rows;
    const x = -nav.half + n.x*cw + cw*0.5;
    const z = -nav.half + n.y*ch + ch*0.5;
    return new THREE.Vector3(x, 1, z);
  }
  function getNeighbors(n){ return [
    {x:n.x+1,y:n.y}, {x:n.x-1,y:n.y}, {x:n.x,y:n.y+1}, {x:n.x,y:n.y-1}
  ].filter(p=> p.x>=0 && p.y>=0 && p.x<nav.cols && p.y<nav.rows); }
  function h(a,b){ return Math.abs(a.x-b.x) + Math.abs(a.y-b.y); }
  function getPath(start, end){
    // Prefer navmesh when available
    if(pathfinder && Pathfinding){
      try{
        const group = pathfinder.getGroup(zoneId, start);
        const path = pathfinder.findPath(start, end, zoneId, group);
        if(path && path.length) return path.map(p=> new THREE.Vector3(p.x, 1, p.z));
      }catch(_){ /* fall back below */ }
    }
    // Grid A* fallback
    const s = w2g(start), e = w2g(end);
    const key = (n)=> n.x+','+n.y;
    const open = [s]; const came = new Map();
    const gScore = new Map([[key(s),0]]); const fScore = new Map([[key(s), h(s,e)]]);
    while(open.length){
      let ci=0; let cf=Infinity; for(let i=0;i<open.length;i++){ const k=key(open[i]); const f=fScore.get(k) ?? Infinity; if(f<cf){ cf=f; ci=i; } }
      const current = open.splice(ci,1)[0];
      if(current.x===e.x && current.y===e.y){
        const path=[current]; let ck=key(current);
        while(came.has(ck)){ const prev=came.get(ck); path.push(prev); ck=key(prev); }
        path.reverse();
        return path.map(g2w);
      }
      for(const nb of getNeighbors(current)){
        const nk = key(nb); const ck = key(current);
        const tent = (gScore.get(ck) ?? Infinity) + 1;
        if(tent < (gScore.get(nk) ?? Infinity)){
          came.set(nk, current); gScore.set(nk, tent); fScore.set(nk, tent + h(nb,e));
          if(!open.find(o=> o.x===nb.x && o.y===nb.y)) open.push(nb);
        }
      }
    }
    return [end.clone()];
  }

  function step(dt){
    if(paused) return;
    // Movement
    forward.set(0,0,-1).applyQuaternion(camera.quaternion); forward.y=0; forward.normalize();
    right.copy(forward).cross(camera.up).normalize();
    vel.set(0,0,0);
    if(keys.has('w')||keys.has('arrowup')) vel.add(forward);
    if(keys.has('s')||keys.has('arrowdown')) vel.add(forward.clone().multiplyScalar(-1));
    if(keys.has('d')||keys.has('arrowright')) vel.add(right);
    if(keys.has('a')||keys.has('arrowleft')) vel.add(right.clone().multiplyScalar(-1));
  const running = keys.has('shift') && (keys.has('w')||keys.has('arrowup')) && stamina>0;
    const speed = baseSpeed * (running?1.6:1.0);
    if(vel.lengthSq()>0) vel.normalize().multiplyScalar(speed*dt);
    player.position.add(vel);
    // Clamp to ground bounds
    player.position.x = Math.max(-98, Math.min(98, player.position.x));
    player.position.z = Math.max(-98, Math.min(98, player.position.z));

  if(running) stamina=Math.max(0, stamina-20*dt); else stamina=Math.min(maxStamina, stamina+10*dt);
    if(rollCD>0) rollCD=Math.max(0, rollCD-dt);
    if(iFrames>0) iFrames=Math.max(0, iFrames-dt);

    // Roll (space)
    if(keys.has(' ') && rollCD===0 && stamina>15){
      const dir2 = vel.lengthSq()>0 ? vel.clone().normalize() : forward.clone();
      player.position.add(dir2.multiplyScalar(6));
      iFrames = 0.45; rollCD=1.0; stamina-=15; keys.delete(' ');
    }

  // Face camera forward direction
  const lookTarget = player.position.clone().add(forward);
  if(body.userData.isFallback){
    // Face forward and swing limbs if moving
    body.lookAt(lookTarget);
    const limbs = body.userData.limbRefs;
    if(limbs){
      const spd = Math.min(1.5, vel.length());
      limbs.lArm.rotation.x = Math.sin(performance.now()*0.01)*0.6*spd;
      limbs.rArm.rotation.x = Math.sin(performance.now()*0.01 + Math.PI)*0.6*spd;
      limbs.lLeg.rotation.x = Math.sin(performance.now()*0.01 + Math.PI)*0.5*spd;
      limbs.rLeg.rotation.x = Math.sin(performance.now()*0.01)*0.5*spd;
    }
  }

    // Engage boss if near
  if(player.position.distanceTo(boss.position) < 4){ bossState.engaged = true; }

    // Boss attacks
    bossState.atkT -= dt;
    if(bossState.engaged && bossState.atkT<=0){
      const phase = bossState.hp < bossState.max*0.5 ? 2 : 1; bossState.phase = phase;
      if(Math.random()<0.6){ // targeted AOE telegraph + volley
        spawnRing(player.position.clone(), bossState.phase===1?2:3);
      }
      spawnVolley(boss.position, player.position);
      bossState.atkT = phase===1? 2.5: 1.8;
    }

    // Projectiles update
    for(let i=projectiles.length-1;i>=0;i--){
      const p = projectiles[i]; p.t -= dt; p.mesh.position.add(p.v.clone().multiplyScalar(dt));
      if(p.mesh.position.distanceTo(player.position) < 0.8){
        if(iFrames<=0){ hp = Math.max(0, hp-10); iFrames=0.6; if(window.hitFlash) window.hitFlash(); shakeT=0.25; shakeAmp=Math.min(0.25, shakeAmp+0.12); }
        scene.remove(p.mesh); projectiles.splice(i,1); continue;
      }
      if(p.t<=0){ scene.remove(p.mesh); projectiles.splice(i,1); }
    }
    for(let i=telegraphs.length-1;i>=0;i--){
      const t=telegraphs[i]; t.t -= dt; t.mesh.material.opacity *= 0.96;
      if(t.t<=0){
        // AOE damage on expiration
        const dist = new THREE.Vector2(player.position.x - t.mesh.position.x, player.position.z - t.mesh.position.z).length();
        if(dist <= t.radius + 0.5 && iFrames<=0){ hp = Math.max(0, hp-20); iFrames=0.6; if(window.hitFlash) window.hitFlash(); shakeT=0.35; shakeAmp=Math.min(0.3, shakeAmp+0.18); }
        scene.remove(t.mesh); telegraphs.splice(i,1);
      }
    }

    // NPC waypoint/pathing: multi-segment following of A* path
    for(const npc of npcs){
      npc.timer -= dt;
      if(!npc.path || npc.path.length===0){
        npc.path = getPath(npc.mesh.position, npc.waypoint);
      }
      if(npc.path && npc.path.length){
        const next = npc.path[0]; const to = next.clone().sub(npc.mesh.position); to.y=0; const d = to.length();
        if(d < 0.3){ npc.path.shift(); }
        else { to.normalize().multiplyScalar(npc.speed*dt); npc.mesh.position.add(to); npc.mesh.lookAt(npc.mesh.position.clone().add(to.clone().setY(0.0001))); }
      }
      // reroll waypoint periodically or when close
      if(npc.timer<=0 || npc.mesh.position.distanceTo(npc.waypoint) < 0.6){ npc.waypoint = randomPoint(); npc.timer = Math.random()*3+2; npc.path = getPath(npc.mesh.position, npc.waypoint); }
    }

    // Camera follow
    camTarget.copy(player.position).add(new THREE.Vector3(0,2,6));
    if(shakeT>0){ shakeT-=dt; const s = shakeAmp*0.7; camera.position.lerp(camTarget, 0.08); camera.position.x += (Math.random()*2-1)*s; camera.position.y += (Math.random()*2-1)*s*0.6; camera.position.z += (Math.random()*2-1)*s; shakeAmp*=0.92; } else { camera.position.lerp(camTarget, 0.08); shakeAmp*=0.9; }
    camera.lookAt(player.position.clone().add(new THREE.Vector3(0,1,0)));

    // Snow update
    if(snow){
      const attr = snow.geometry.getAttribute('position');
      const arr = attr.array; const n = arr.length/3;
      for(let i=0;i<n;i++){
        const ix=i*3; arr[ix+1] -= snowParams.fall*dt*(0.6+Math.random()*0.6);
        if(arr[ix+1] < snowParams.yBottom){ arr[ix+0]=(Math.random()*2-1)*snowParams.area; arr[ix+1]=snowParams.yTop; arr[ix+2]=(Math.random()*2-1)*snowParams.area; }
      }
      attr.needsUpdate = true;
    }
  }

  let last = performance.now();
  function animate(){
    const now = performance.now();
    const dt = Math.min(0.05, (now-last)/1000); last = now;
    step(dt);
    if(mixer) mixer.update(dt);
    // Switch animation state if GLTF loaded
    if(mixer && actions){
      const moving = vel.lengthSq()>0.0001;
      const running = keys.has('shift') && (keys.has('w')||keys.has('arrowup'));
      const want = running && moving && actions['Run'] ? 'Run' : (moving && actions['Walk'] ? 'Walk' : (actions['Idle']?'Idle':null));
      if(want && actions[want] && activeAction !== actions[want]){
        if(activeAction){ activeAction.fadeOut(0.15); }
        activeAction = actions[want]; activeAction.reset().fadeIn(0.15).play();
      }
    }
    renderer.render(scene, camera);
    // Publish HUD state for 3D
    if(window.updateHUD){
      window.updateHUD({
        hp, maxHp,
        stamina, maxStamina,
        cds: { q: 0, e: 0, dodge: rollCD },
        lock: false,
        rating: 0, completionist: 0, finished: hp<=0,
        level: lvl3d, xp: xp3d,
        boss: { hp: bossState.hp, maxHp: bossState.max, stagger: bossState.stagger, engaged: bossState.engaged, phase: bossState.phase },
      });
    }
    requestAnimationFrame(animate);
  }
  animate();

  // Resize handler
  const resize = ()=>{
    const w = mount.clientWidth, h = mount.clientHeight;
    renderer.setSize(w,h); camera.aspect = w/h; camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize); ro.observe(mount);

  return api;
}

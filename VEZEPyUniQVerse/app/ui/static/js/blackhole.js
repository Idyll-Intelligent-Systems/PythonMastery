(function(){
  const c = document.getElementById('blackhole');
  if(!c) return;
  const dpr = Math.min(window.devicePixelRatio||1, 2);
  const ctx = c.getContext('2d');
  function resize(){ c.width = innerWidth*dpr; c.height = innerHeight*dpr; }
  window.addEventListener('resize', resize, {passive:true});
  resize();

  const root = document.body;
  function getAccent(){
    const cs = getComputedStyle(root);
    // Extract accent color and build two tints
    const accent = cs.getPropertyValue('--accent').trim() || '#7c4dff';
    return accent;
  }
  let mouseX = innerWidth/2, mouseY = innerHeight/2;
  window.addEventListener('mousemove', (e)=>{ mouseX = e.clientX; mouseY = e.clientY; }, {passive:true});

  const stars = Array.from({length: 260}, () => ({
    x: Math.random()*c.width,
    y: Math.random()*c.height,
    z: Math.random()*1+0.2,
    layer: Math.random()<0.5 ? 1 : 2,
  }));

  function rgba(hex, a){
    // support #rrggbb
    if(/^#?[0-9a-fA-F]{6}$/.test(hex)){
      const h = hex.replace('#','');
      const r = parseInt(h.slice(0,2),16), g = parseInt(h.slice(2,4),16), b = parseInt(h.slice(4,6),16);
      return `rgba(${r},${g},${b},${a})`;
    }
    return `rgba(124,77,255,${a})`;
  }

  function step(){
    const ax = getAccent();
    const parallaxX = (mouseX - innerWidth/2) / innerWidth; // -0.5..0.5
    const parallaxY = (mouseY - innerHeight/2) / innerHeight;
    ctx.clearRect(0,0,c.width,c.height);
    for(const s of stars){
      // gentle pull toward center (blackhole)
      s.x += (c.width/2 - s.x) * 0.0008 * s.z;
      s.y += (c.height/2 - s.y) * 0.0008 * s.z;
      // parallax drift by mouse
      const drift = s.layer===1 ? 8 : 16;
      const px = parallaxX * drift * dpr;
      const py = parallaxY * drift * dpr;
      const r = (1.2 + s.z*1.8)*dpr;
      const glow = 0.18 + s.z*0.6;
      ctx.fillStyle = rgba(ax, glow);
      ctx.beginPath(); ctx.arc(s.x + px, s.y + py, r, 0, Math.PI*2); ctx.fill();
      s.z += 0.002; if(s.z>1.25){ s.x = Math.random()*c.width; s.y=Math.random()*c.height; s.z = 0.2; }
    }
    requestAnimationFrame(step);
  }
  step();
})();

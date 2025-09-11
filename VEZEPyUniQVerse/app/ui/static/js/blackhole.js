(function(){
  const c = document.getElementById('blackhole');
  if(!c) return;
  const dpr = Math.min(window.devicePixelRatio||1, 2);
  const ctx = c.getContext('2d');
  function resize(){ c.width = innerWidth*dpr; c.height = innerHeight*dpr; }
  window.addEventListener('resize', resize, {passive:true});
  resize();

  const stars = Array.from({length: 250}, () => ({
    x: Math.random()*c.width,
    y: Math.random()*c.height,
    z: Math.random()*1+0.2,
  }));

  function step(){
    ctx.clearRect(0,0,c.width,c.height);
    for(const s of stars){
      s.x += (c.width/2 - s.x) * 0.0008 * s.z;
      s.y += (c.height/2 - s.y) * 0.0008 * s.z;
      const r = (1.5 + s.z*1.5)*dpr;
      ctx.fillStyle = `rgba(200,230,255,${0.2 + s.z*0.8})`;
      ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, Math.PI*2); ctx.fill();
      s.z += 0.002; if(s.z>1.2){ s.x = Math.random()*c.width; s.y=Math.random()*c.height; s.z = 0.2; }
    }
    requestAnimationFrame(step);
  }
  step();
})();

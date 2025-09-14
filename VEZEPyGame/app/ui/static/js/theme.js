(function(){
  const root = document.body;
  const THEMES = ['theme-dark','theme-light','theme-futuristic'];
  const ACCENTS = ['accent-gold','accent-silver','accent-red','accent-purple','accent-violet','accent-navy','accent-orange'];
  try{
    const t = localStorage.getItem('veze_theme');
    if(t){ root.classList.remove(...THEMES); root.classList.add(t); }
  }catch(_){/* ignore */}
  try{
    const a = localStorage.getItem('veze_accent');
    if(a){ const rm = ACCENTS.filter(c=>root.classList.contains(c)); if(rm.length) root.classList.remove(...rm); root.classList.add(a); }
  }catch(_){/* ignore */}
  // Listen for cross-tab updates
  window.addEventListener('storage', (e)=>{
    if(e.key==='veze_theme' && typeof e.newValue==='string'){
      root.classList.remove(...THEMES); root.classList.add(e.newValue);
    }
    if(e.key==='veze_accent' && typeof e.newValue==='string'){
      const rm = ACCENTS.filter(c=>root.classList.contains(c)); if(rm.length) root.classList.remove(...rm); root.classList.add(e.newValue);
    }
  });
})();

(function(){
  const root = document.body;
  const themeBtn = document.getElementById('theme-toggle');
  const chips = Array.from(document.querySelectorAll('.chip[data-accent]'));
  const THEMES = ['theme-dark','theme-light','theme-futuristic'];
  const ACCENTS = ['accent-gold','accent-silver','accent-red','accent-purple','accent-violet','accent-navy','accent-orange'];
  let themeIdx = 2; // default futuristic
  let accentIdx = 0; // default gold

  function applyTheme(saved){
    root.classList.remove(...THEMES);
    const next = saved && THEMES.includes(saved) ? saved : THEMES[themeIdx];
    root.classList.add(next);
    try{ localStorage.setItem('veze_theme', next); }catch(_){/* ignore */}
  }
  function applyAccent(saved){
    const toRemove = ACCENTS.filter(c=>root.classList.contains(c));
    if(toRemove.length) root.classList.remove(...toRemove);
    const next = saved && ACCENTS.includes(saved) ? saved : ACCENTS[accentIdx];
    root.classList.add(next);
    try{ localStorage.setItem('veze_accent', next); }catch(_){/* ignore */}
  }

  // init from localStorage
  try{
    const savedTheme = localStorage.getItem('veze_theme');
    if(savedTheme){ themeIdx = Math.max(0, THEMES.indexOf(savedTheme)); }
    const savedAccent = localStorage.getItem('veze_accent');
    if(savedAccent){ accentIdx = Math.max(0, ACCENTS.indexOf(savedAccent)); }
  }catch(_){/* ignore */}
  applyTheme(THEMES[themeIdx]);
  applyAccent(ACCENTS[accentIdx]);

  // handlers
  if(themeBtn){
    themeBtn.addEventListener('click', ()=>{
      themeIdx = (themeIdx+1)%THEMES.length;
      applyTheme(THEMES[themeIdx]);
    });
  }
  if(chips.length){
    function setActiveChip(name){
      chips.forEach(ch=>{
        ch.classList.toggle('active', ch.dataset.accent===name);
      });
    }
    // Initialize active visual state
    setActiveChip(ACCENTS[accentIdx]);
    chips.forEach(ch=>{
      ch.addEventListener('click', ()=>{
        const name = ch.dataset.accent;
        const idx = ACCENTS.indexOf(name);
        if(idx>=0){ accentIdx = idx; applyAccent(name); setActiveChip(name); }
      });
    });
  }

  // Cross-tab sync for theme/accent
  window.addEventListener('storage', (e)=>{
    if(e.key === 'veze_theme' && typeof e.newValue === 'string'){
      applyTheme(e.newValue);
    }
    if(e.key === 'veze_accent' && typeof e.newValue === 'string'){
      applyAccent(e.newValue);
      if(chips.length){
        chips.forEach(ch=> ch.classList.toggle('active', ch.dataset.accent===e.newValue));
      }
    }
  });
})();

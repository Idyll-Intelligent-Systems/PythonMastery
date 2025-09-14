(function(){
  // Tiny client to call XEngine APIs relative to current path (works behind /xengine)
  async function j(url, opts){
    const r = await fetch(url, Object.assign({headers:{'Accept':'application/json'}}, opts||{}));
    if(!r.ok) throw new Error('request failed');
    const ct = r.headers.get('content-type')||'';
    return ct.includes('application/json') ? r.json() : r.text();
  }

  async function load(){
    const trendsEl = document.querySelector('#trends');
    const intelForm = document.querySelector('#intel-form');
    const intelOut = document.querySelector('#intel-out');
    const postForm = document.querySelector('#post-form');
    const postOut = document.querySelector('#post-out');
    const grokForm = document.querySelector('#grok-form');
    const grokOut = document.querySelector('#grok-out');
    const actEl = document.querySelector('#activity');
    const catList = document.querySelector('#catalog-list');
    const catDetail = document.querySelector('#catalog-detail');
    const chartCanvas = document.querySelector('#metrics-chart');
    let chart;

    // Trends
    try { const d = await j('api/trends'); if(trendsEl){ trendsEl.innerHTML = d.trends.map(t=>`<li><span>#</span>${t.tag.replace(/^#/,'')} <em>${t.volume}</em></li>`).join(''); } } catch(e){}

    // Intel
    if(intelForm){ intelForm.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const u = intelForm.querySelector('input[name=username]').value.trim();
      if(!u) return;
      intelOut.textContent = 'Loading...';
      try{ const d = await j(`api/users/${encodeURIComponent(u)}`); intelOut.textContent = JSON.stringify(d,null,2);
        setIntelSource(d && d.source === 'xapi' ? 'xapi' : 'sandbox');
        // metrics
        try{
          const m = await j(`api/users/${encodeURIComponent(u)}/metrics`);
          if(chartCanvas){ const data = {labels:['Followers','Following','Tweets','Listed'], datasets:[{label: u, data:[m.followers_count,m.following_count,m.tweet_count,m.listed_count], backgroundColor:'rgba(124,77,255,0.35)', borderColor:'rgba(124,77,255,0.9)', borderWidth:2}]};
            if(chart) chart.destroy(); chart = new Chart(chartCanvas.getContext('2d'), {type:'bar', data, options:{responsive:true, plugins:{legend:{display:false}}}});
          }
        }catch(_){}
      }catch(e){ intelOut.textContent = 'Error'; }
    });
      // Auto-fetch default handle if present
      try{
        const def = intelForm.querySelector('input[name=username]').value.trim();
        if(def){
          const ev = new Event('submit');
          intelForm.dispatchEvent(ev);
        }
      }catch(_){ }
    }

    // Post
    if(postForm){ postForm.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const text = postForm.querySelector('textarea[name=text]').value.trim();
      const postNow = !!postForm.querySelector('input[name=post_now]')?.checked;
      if(!text) return;
      postOut.textContent = 'Queueing...';
      try{ const d = await j('api/post', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, post_now: postNow})}); postOut.textContent = JSON.stringify(d); showToast('Queued: '+text.slice(0,40)); }catch(e){ postOut.textContent='Error'; }
    }); }

    // Grok
    if(grokForm){ grokForm.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const prompt = grokForm.querySelector('textarea[name=prompt]').value.trim();
      if(!prompt) return;
      grokOut.textContent = 'Thinking...';
      try{ const d = await j('api/grok', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({prompt})}); grokOut.textContent = d.reply || JSON.stringify(d); }catch(e){ grokOut.textContent='Error'; }
    }); }
    // Catalog tabs
    bindCatalog();

    // Live status check
    const liveBtn = document.querySelector('#live-check');
    const liveOut = document.querySelector('#live-status');
    const writeBadge = document.querySelector('#write-badge');
    async function refreshLive(){
      try{
        const s = await j('api/live/status');
        if(liveOut){ if(s.live){ liveOut.textContent = 'live ok'; liveOut.classList.remove('badge-sandbox'); liveOut.classList.add('badge-xapi'); liveOut.title = 'Bearer token detected and working'; } else { liveOut.textContent = s.reason || 'offline'; liveOut.classList.remove('badge-xapi'); liveOut.classList.add('badge-sandbox'); liveOut.title = 'Live data unavailable'; } }
        if(writeBadge){ if(s.posting_ready){ writeBadge.textContent = 'write enabled'; writeBadge.classList.remove('badge-off'); writeBadge.classList.add('badge-write'); writeBadge.title = 'POST_TO_X_ENABLED and keys present'; } else { writeBadge.textContent = 'off'; writeBadge.classList.remove('badge-write'); writeBadge.classList.add('badge-off'); writeBadge.title = 'Write disabled or keys missing'; } }
      }catch(_){ if(writeBadge){ writeBadge.textContent = 'off'; writeBadge.classList.remove('badge-write'); writeBadge.classList.add('badge-off'); } }
    }
    if(liveBtn && liveOut){
      liveBtn.addEventListener('click', async ()=>{
        liveBtn.disabled = true; const prev = liveBtn.textContent; liveBtn.textContent = 'Checking...';
        liveOut.style.display = 'inline-block'; liveOut.textContent = '';
        await refreshLive();
        liveBtn.textContent = prev; liveBtn.disabled = false;
      });
      // Also fetch status once on load
      refreshLive();
    }

    // Activity live: try WS, fallback to polling. Bind toggle.
  const wsToggle = document.querySelector('#ws-direct');
  setWsStatus('connecting');
    if(wsToggle){
      // Initialize from localStorage
      try{ wsToggle.checked = localStorage.getItem('xengine_ws_direct') === '1'; }catch(_){}
      wsToggle.addEventListener('change', ()=>{
        try{ localStorage.setItem('xengine_ws_direct', wsToggle.checked ? '1' : '0'); }catch(_){}
        // Reconnect with new mode
        tryWsActivity(true);
      });
    }
    tryWsActivity();
  }

  async function loadCatalog(kind){
    if(!kind) return; const list = document.querySelector('#catalog-list'); if(!list) return;
    try{ const d = await j(`api/catalog/${encodeURIComponent(kind)}`);
      list.innerHTML = d.items.map(i=>`<li><a href="#" data-kind="${kind}" data-id="${i.id}">${i.name||i.id}</a></li>`).join('');
    }catch(e){ list.innerHTML = '<li>Error</li>'; }
  }
  function bindCatalog(){
    const list = document.querySelector('#catalog-list'); if(!list) return;
    list.addEventListener('click', async (ev)=>{
      const a = ev.target.closest('a[data-id]'); if(!a) return; ev.preventDefault();
      try{ const d = await j(`api/catalog/${a.dataset.kind}/${a.dataset.id}`);
        document.querySelector('#catalog-detail').textContent = JSON.stringify(d,null,2);
      }catch(e){ document.querySelector('#catalog-detail').textContent = 'Error'; }
    });
    const tabs = Array.from(document.querySelectorAll('.tabs .btn'));
    tabs.forEach(b=> b.addEventListener('click', ()=> loadCatalog(b.dataset.kind)));
    if(tabs[0]) loadCatalog(tabs[0].dataset.kind);
  }

  async function pollActivity(){
    const el = document.querySelector('#activity'); if(!el) return;
    try{ const d = await j('api/activity/recent'); el.innerHTML = d.events.slice().reverse().map(e=>{
      return `<li>${e.type==='queued'?'🛰️ Queued':'✅ Processed'} — ${e.text|| (e.task?e.task.text:'') }</li>`;
    }).join(''); }catch(e){}
    setTimeout(pollActivity, 3000);
  }

  function renderEvents(list){
    const el = document.querySelector('#activity'); if(!el) return;
    el.innerHTML = list.slice().reverse().map(e=>{
      const icon = e.type==='queued'?'🛰️':'✅';
      return `<li class="activity-item"><span class="icon">${icon}</span> <span class="txt">${e.text|| (e.task?e.task.text:'')}</span></li>`;
    }).join('');
  }

  let _wsObj = null;
  function setIntelSource(src){
    const badge = document.querySelector('#intel-src'); if(!badge) return;
    badge.textContent = src === 'xapi' ? 'xapi' : 'sandbox';
    badge.title = src === 'xapi' ? 'Live data via X API' : 'Sandbox data';
    badge.classList.remove('badge-sandbox','badge-xapi');
    badge.classList.add(src === 'xapi' ? 'badge-xapi' : 'badge-sandbox');
  }
  function setWsStatus(state){
    const dot = document.querySelector('#ws-status'); if(!dot) return;
    const txt = document.querySelector('#ws-status-text');
    dot.classList.remove('ws-connecting','ws-connected','ws-polling');
    if(state==='connected'){
      dot.classList.add('ws-connected'); dot.title = 'Live via WebSocket'; dot.setAttribute('aria-label','Live via WebSocket'); if(txt) txt.textContent = 'Live';
    }
    else if(state==='polling'){
      dot.classList.add('ws-polling'); dot.title = 'Using REST polling'; dot.setAttribute('aria-label','Using REST polling'); if(txt) txt.textContent = 'Polling';
    }
    else {
      dot.classList.add('ws-connecting'); dot.title = 'Connecting...'; dot.setAttribute('aria-label','Connecting'); if(txt) txt.textContent = 'Connecting…';
    }
  }
  function tryWsActivity(forceReconnect){
    const el = document.querySelector('#activity'); if(!el) return pollActivity();
    if(_wsObj && !forceReconnect) return; // already connected or attempted
    if(_wsObj){ try{ _wsObj.close(); }catch(_){ } _wsObj = null; }
    try{
      // Choose proxied or direct URL
      const direct = document.querySelector('#ws-direct')?.checked;
      const isHttps = location.protocol==='https:';
      let wsUrl;
      if(direct){
        // Direct to service port (only works in local HTTP; in HTTPS/Codespaces this will likely fail or be blocked)
        const proto = isHttps ? 'wss' : 'ws';
        const host = (location.hostname || 'localhost');
        wsUrl = `${proto}://${host}:8006/ws/activity`;
      } else {
        // Proxied through UniQVerse
        const proto = isHttps ? 'wss' : 'ws';
        wsUrl = `${proto}://${location.host}/xengine/ws/activity`;
      }
      const ws = new WebSocket(wsUrl);
      _wsObj = ws;
      let events = [];
      setWsStatus('connecting');
      ws.onmessage = (ev)=>{
        try{ const d = JSON.parse(ev.data); if(d.events){ events = events.concat(d.events); if(events.length>100) events = events.slice(-100); renderEvents(events); } else { try{ ws.close(); }catch(_){ } } }catch(_){ try{ ws.close(); }catch(_){} }
      };
      ws.onopen = ()=>{ setWsStatus('connected'); };
      ws.onerror = ()=>{
        try{ ws.close(); }catch(_){}
        _wsObj = null;
        // On error: if direct mode, fallback to proxied once; otherwise fallback to polling
        const toggle = document.querySelector('#ws-direct');
        if(toggle && toggle.checked){
          // one-time fallback to proxied without mutating the toggle
          try{ const prev = toggle.checked; toggle.checked = false; setWsStatus('connecting'); tryWsActivity(true); toggle.checked = prev; }catch(_){ setWsStatus('polling'); pollActivity(); }
        } else {
          setWsStatus('polling');
          pollActivity();
        }
      };
      ws.onclose = ()=>{ if(_wsObj===ws){ _wsObj = null; } setWsStatus('polling'); pollActivity(); };
    }catch(_){ setWsStatus('polling'); pollActivity(); }
  }

  function showToast(msg){ const t = document.querySelector('#toast'); if(!t) return; t.textContent = msg; t.style.display='block'; setTimeout(()=>{ t.style.display='none'; }, 2000); }

  window.addEventListener('DOMContentLoaded', load);
})();

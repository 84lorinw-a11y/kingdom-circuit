/* Fan engagement. Test delivery is disabled; production uses existing Google Analytics. */
(function (root) {
  'use strict';
  const STORE = 'kc-fan-test-events-v1', JOURNEY = 'kc-fan-empty-journey-v1';
  const EVENTS = new Set(['artist_view','artist_select','show_view','page_engagement','empty_shows_impression','empty_shows_click','event_select','ticket_referral','instagram_referral','facebook_referral','artist_social_click','artist_jump_select','artist_suggestion_open','search_results','form_start','form_attempt','form_success','form_error','web_performance','site_error','traffic_arrival','state_select','collection_select']);
  const KEYS = new Set(['page_type','page_path','artist_name','show_name','placement','action','platform','referral_type','destination_host','destination_path','result_count','search_term','state','dates','artist_filter','show_type','form_type','error_type','metric','value','lcp_ms','layout_shift_sum','max_interaction_ms','viewport','source_artist','source_action','source','medium','campaign','referrer_host','visible_seconds','scroll_percent','show_count']);
  function safeText(value) {
    const s = String(value ?? '').trim().replace(/[\x00-\x1f]/g,' ');
    // Never collect contact information, URLs, long numbers or submitted fields.
    if (/@|(?:https?:|www\.)|(?:\d[\s().+-]*){7,}/i.test(s)) return '[redacted]';
    return s.slice(0,100);
  }
  function clean(params) {
    return Object.fromEntries(Object.entries(params).filter(([k,v]) => KEYS.has(k) && v !== undefined && v !== '').map(([k,v]) => [k, typeof v === 'number' ? (Number.isFinite(v) ? Math.round(v*100)/100 : 0) : ['destination_host','referrer_host'].includes(k) ? (/^[a-z0-9.-]+$/i.test(String(v)) ? String(v).slice(0,100) : '[redacted]') : ['page_path','destination_path'].includes(k) ? String(v).split(/[?#]/)[0].slice(0,100) : safeText(v)]));
  }
  function today(now = new Date()) {
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now).map(p=>[p.type,p.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  function countShows(shows, day = today()) { return new Set(shows.filter(s => /^\d{4}-\d{2}-\d{2}$/.test(s.end || s.date) && (s.end || s.date) >= day).map(s=>s.path)).size; }
  function artistSchedule(paths, shows, day = today()) {
    const byPath=new Map(shows.map(s=>[s.path,s]));
    return [...new Set(paths)].map(path=>byPath.get(path)).filter(s=>s && (s.end||s.date)>=day).sort((a,b)=>a.date.localeCompare(b.date));
  }
  function refreshArtistSchedule(doc,config,shows,day=today()) {
    const active=artistSchedule(config.showPaths||[],shows,day),paths=new Set(active.map(s=>s.path));
    const listing=doc.querySelector('.kc-rd-show-list');if(!listing)return active;
    listing.querySelectorAll('.kc-rd-show-row').forEach(row=>{row.hidden=!paths.has(row.getAttribute('href'));});
    doc.querySelectorAll('[data-event-card]').forEach(card=>{
      if(card.closest('.kc-rd-past-shows'))return;
      const path=card.querySelector('h3 a')?.getAttribute('href');if(path)card.hidden=!paths.has(path);
    });
    const total=doc.querySelector('.kc-rd-upcoming-total');if(total)total.textContent=`${active.length} upcoming`;
    const next=doc.querySelector('.kc-rd-next-show');
    if(next){
      next.hidden=!active.length;
      if(active.length && next.getAttribute('href')!==active[0].path){
        const show=active[0];next.setAttribute('href',show.path);
        const label=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',...(show.date.slice(0,4)!==day.slice(0,4)?{year:'numeric'}:{}),timeZone:'UTC'}).format(new Date(show.date+'T12:00:00Z')).toUpperCase();
        const time=show.when?.match(/ - (.+)$/)?.[1];
        for(const[selector,text]of [['.kc-rd-next-kicker','Next show · '+label],['.kc-rd-next-place',show.location],['.kc-rd-next-venue',[show.venue,time].filter(Boolean).join(' · ')],['.kc-rd-event-title',show.name]]){
          const node=next.querySelector(selector);if(node)node.textContent=text||'';
        }
      }
    }
    return active;
  }
  function read(storage,key,fallback) { try { return JSON.parse(storage.getItem(key)) || fallback; } catch (_) { return fallback; } }
  function write(storage,key,value) { try { storage.setItem(key,JSON.stringify(value)); } catch (_) { /* Privacy mode can disable storage. */ } }
  function tracker(config, env) {
    return function track(name, params = {}) {
      if (!EVENTS.has(name)) return;
      const fields = clean({page_type:config.pageType,page_path:env.path,viewport:env.width()<=720?'mobile':'desktop',...params});
      const entry = {event:name,time:new Date().toISOString(),...fields};
      if (config.mode === 'production' && env.host === 'kingdomcircuit.com' && typeof env.gtag === 'function') {
        env.gtag('event', name, {...fields,transport_type:'beacon'});
      }
      return entry;
    };
  }
  function formType(form) { return form.id==='artist-intake-form'?'artist_profile':form.matches('[data-kc-artist-form]')?'artist_suggestion':form.querySelector('[data-submission-kind]')?.value==='Correction'?'show_correction':'new_show'; }
  function attemptState() {
    const states=new WeakMap();
    return {
      start(form,type){ let s=states.get(form); if (!s) {s={type,started:true,pending:false};states.set(form,s);return s;} return null; },
      attempt(form,type){let s=states.get(form);if(s?.pending)return null;s={type,started:true,pending:true};states.set(form,s);return s;},
      finish(form,status){const s=states.get(form);if(!s?.pending || !['success','error'].includes(status))return null;s.pending=false;return {type:s.type,status};}
    };
  }
  function classifyLink({url,origin,base='/',statePaths={},inArtistArea=false,inEventArea=false,label=''}) {
    if(!['https:','http:'].includes(url.protocol))return null;
    const path=url.pathname,host=url.hostname.toLowerCase(),at=domain=>host===domain||host.endsWith('.'+domain);
    if(url.origin===origin){
      const params={destination_path:path};
      if(path.startsWith(base+'event/'))return {event:'event_select',params};
      if(path.startsWith(base+'artists/') && /^[^/]+\/$/.test(path.slice((base+'artists/').length)))return {event:'artist_select',params};
      if(Object.hasOwn(statePaths,path))return {event:'state_select',params:{...params,state:statePaths[path]}};
      if(path.startsWith(base+'shows/')||path===base+'festivals/'||path===base+'new-shows/')return {event:'collection_select',params};
      return null;
    }
    const params={destination_host:host};
    if(at('instagram.com')&&path.replace(/\/+$/,'').toLowerCase()==='/thekingdomcircuit')return {event:'instagram_referral',params:{platform:'instagram',...params}};
    if(at('facebook.com')&&path==='/profile.php'&&url.searchParams.get('id')==='61593510924754')return {event:'facebook_referral',params:{platform:'facebook',...params}};
    if(inEventArea&&/official details|tickets|register/i.test(label))return {event:'ticket_referral',params:{...params,referral_type:/register/i.test(label)?'registration':/tickets/i.test(label)?'ticket':'information'}};
    if(inArtistArea){
      const platform=at('instagram.com')?'instagram':at('spotify.com')?'spotify':at('youtube.com')||at('youtu.be')?'youtube':at('facebook.com')?'facebook':at('tiktok.com')?'tiktok':/official website/i.test(label)?'website':null;
      if(platform)return {event:'artist_social_click',params:{platform,...params}};
    }
    return null;
  }
  const api={STORE,JOURNEY,safeText,clean,today,countShows,artistSchedule,refreshArtistSchedule,tracker,attemptState,classifyLink};
  if (typeof module==='object' && module.exports) module.exports=api;
  if (!root.document) return;
  const d=root.document, configNode=d.getElementById('kc-fan-config'); if (!configNode || root.KCFanAnalytics) return;
  let config;try{config=JSON.parse(configNode.textContent);}catch(_){return;}
  let storage;try{storage=root.sessionStorage;}catch(_){storage={getItem(){return null},setItem(){}};}
  // Retire the temporary QA log. Only short-lived source attribution stays in this tab.
  try { storage.removeItem(STORE); } catch (_) {}
  const track=tracker(config,{storage,path:location.pathname,host:location.hostname,width:()=>root.innerWidth,gtag:root.gtag,notify:detail=>d.dispatchEvent(new CustomEvent('kc:analytics-recorded',{detail}))});
  root.KCFanAnalytics={track};
  const journey=()=>{const j=read(storage,JOURNEY,{});return Date.now()-j.time<30*60*1000?{source_artist:j.artist,source_action:j.action}:{};};
  const formStates=attemptState(), formSelector='[data-submission-form],#artist-intake-form,[data-kc-artist-form]';
  let catalog=null, panelSeen=false, lastFetch=0, count=0, fetchPending=false;
  function observePanel() {
    const panel=d.querySelector('[data-empty-discovery]');if(!panel || panel.hidden || panelSeen)return;
    if (!root.IntersectionObserver)return;
    observer.observe(panel);
  }
  const observer=root.IntersectionObserver?new IntersectionObserver(entries=>{
    for(const e of entries)if(e.isIntersecting && e.intersectionRatio>=.5 && !e.target.hidden && !panelSeen){panelSeen=true;track('empty_shows_impression',{artist_name:config.artist,show_count:count,placement:'artist_no_shows'});observer.disconnect();}
  },{threshold:.5}):null;
  function updateCatalog() {
    if(!catalog)return;
    count=countShows(catalog.shows);
    d.querySelectorAll('[data-live-show-count]').forEach(el=>{if(el.textContent!==String(count))el.textContent=count;});
    if(config.pageType!=='artist')return;
    const listing=d.querySelector('.kc-rd-show-list');if(!listing)return;
    const active=refreshArtistSchedule(d,config,catalog.shows).length>0;
    let panel=listing.querySelector('[data-empty-discovery]');
    if(!active && !panel){listing.append(d.getElementById('kc-empty-template').content.cloneNode(true));panel=listing.querySelector('[data-empty-discovery]');}
    if(panel)panel.hidden=active;
    if(!active){
      listing.querySelectorAll('.kc-rd-profile-empty,.kc-rd-show-row').forEach(e=>e.hidden=true);
      d.querySelectorAll('.kc-rd-next--empty,.kc-rd-next-show').forEach(e=>e.hidden=true);
      const total=d.querySelector('.kc-rd-upcoming-total');if(total)total.textContent='0 upcoming';
      panel?.querySelectorAll('[data-live-show-count]').forEach(e=>e.textContent=count);
    }
    observePanel();
  }
  async function refreshCatalog() {
    if(fetchPending || Date.now()-lastFetch<300000)return;fetchPending=true;
    try{const r=await fetch(config.base+(config.catalogFile||'assets/fan-show-catalog.json'),{cache:'no-cache'});if(!r.ok)throw new Error();const data=await r.json();if(!Array.isArray(data.shows))throw new Error();catalog=data;lastFetch=Date.now();updateCatalog();}
    catch(_){track('site_error',{error_type:'catalog_unavailable'});observePanel();}finally{fetchPending=false;}
  }
  function placement(el){return el.closest('[data-empty-discovery]')?'artist_no_shows':el.closest('.kc-fan-artist-results')?'artist_search_results':el.closest('.kc-discovery-artists')?'home_artist_shelf':el.closest('[aria-labelledby="kc-weekend-heading"]')?'home_this_week':el.closest('[aria-labelledby="kc-next-heading"]')?'home_next_week':el.closest('[data-artist-card]')?'artist_directory':el.closest('header')?'header':el.closest('footer')?'footer':config.pageType;}
  function artistFor(el){if(config.artist)return config.artist;const card=el.closest('[data-artist-card]');return card?.querySelector('h2,h3')?.textContent.trim()||'';}
  d.addEventListener('click',event=>{
    const a=event.target.closest?.('a[href]');if(!a)return;
    let url;try{url=new URL(a.href,location.href);}catch(_){return;}
    if(!['https:','http:'].includes(url.protocol))return;
    const shared={placement:placement(a),artist_name:artistFor(a)};
    if(a.dataset.emptyAction){
      track('empty_shows_click',{...shared,action:a.dataset.emptyAction,show_count:count});
      write(storage,JOURNEY,{artist:config.artist,action:a.dataset.emptyAction,time:Date.now()});
    }
    const eventArea=a.closest('[data-event-card],.event-detail,.kc-discovery-show');
    const result=classifyLink({url,origin:location.origin,base:config.base,statePaths:config.statePaths,
      inEventArea:!!eventArea,inArtistArea:config.pageType==='artist'||!!a.closest('[data-artist-card]'),
      label:(a.textContent||'')+' '+(a.getAttribute('aria-label')||'')});
    if(!result)return;
    const fields={...shared,...journey(),...result.params};
    if(result.event==='artist_select')fields.artist_name=a.querySelector('strong')?.textContent.trim()||a.closest('[data-artist-card]')?.querySelector('h2,h3')?.textContent.trim()||a.textContent.trim();
    if(['event_select','ticket_referral'].includes(result.event))fields.show_name=eventArea?.querySelector('h3')?.textContent.trim()||a.querySelector('.kc-rd-event-title')?.textContent.trim()||config.show||'';
    track(result.event,fields);
  },true);
  d.addEventListener('focusin',e=>{const f=e.target.closest?.(formSelector);if(f && formStates.start(f,formType(f)))track('form_start',{form_type:formType(f)});},true);
  d.addEventListener('submit',e=>{const f=e.target;if(!f.matches?.(formSelector))return;const type=formType(f);if(formStates.start(f,type))track('form_start',{form_type:type});if(formStates.attempt(f,type))track('form_attempt',{form_type:type});},true);
  d.addEventListener('kc:submission-result',e=>{const result=formStates.finish(e.target,e.detail?.status);if(result)track('form_'+result.status,{form_type:result.type,...(result.status==='error'?{error_type:'submission_failed'}:{})});});
  let invalidTimer;d.addEventListener('invalid',e=>{const f=e.target.closest?.(formSelector);if(!f)return;clearTimeout(invalidTimer);invalidTimer=setTimeout(()=>track('form_error',{form_type:formType(f),error_type:'validation'}),100);},true);
  let searchTimer,lastSearch='';
  function results(action='initial_results'){
    const f=d.querySelector('[data-event-filters]');if(!f)return;
    const query=f.querySelector('[data-search-filter]')?.value||'';
    const values={search_term:query,state:f.querySelector('[data-state-filter]')?.value||'',artist_filter:f.querySelector('[data-artist-filter]')?.value||'',show_type:f.querySelector('[data-type-filter]')?.value||'',dates:f.querySelector('select[aria-label="Dates"]')?.value||new URLSearchParams(location.search).get('dates')||'all'};
    const resultCount=[...d.querySelectorAll('[data-event-card]')].filter(e=>!e.hidden).length;
    const signature=JSON.stringify({...values,result_count:resultCount});if(signature===lastSearch)return;lastSearch=signature;
    track('search_results',{...values,action,result_count:resultCount});
  }
  function queueSearch(e){
    if(e && !e.target.closest?.('[data-event-filters],.kc-fan-active'))return;
    if(e?.type==='click'&&!e.target.closest?.('button,.kc-fan-active'))return;
    const action=!e?'history_navigation':e.target.matches?.('[data-search-filter]')?'search_change':'filter_change';
    clearTimeout(searchTimer);searchTimer=setTimeout(()=>results(action),500);
  }
  ['input','change','click'].forEach(name=>d.addEventListener(name,queueSearch,true));
  d.addEventListener('submit',e=>{if(!e.target.matches?.('[data-fan-finder]'))return;track('search_results',{placement:'home',action:'search_submit',search_term:e.target.elements.q?.value||'',state:e.target.elements.state?.value||'',dates:e.target.elements.dates?.value||''});},true);
  root.addEventListener('popstate',()=>queueSearch());
  let visibleAt=d.visibilityState==='visible'?performance.now():null,visibleMs=0,maxScroll=0,engagementSent=false;
  function pauseTime(){if(visibleAt!==null){visibleMs+=performance.now()-visibleAt;visibleAt=null;}}
  function engagement(){if(engagementSent)return;pauseTime();engagementSent=true;track('page_engagement',{artist_name:config.artist,show_name:config.show,visible_seconds:Math.round(visibleMs/1000),scroll_percent:maxScroll,...journey()});}
  root.addEventListener('scroll',()=>{const max=d.documentElement.scrollHeight-root.innerHeight;maxScroll=Math.max(maxScroll,max>0?Math.min(100,Math.round(root.scrollY/max*100)):100);},{passive:true});
  d.addEventListener('visibilitychange',()=>{if(d.visibilityState==='hidden'){engagement();}else{engagementSent=false;visibleMs=0;visibleAt=performance.now();updateCatalog();refreshCatalog();}});
  root.addEventListener('pagehide',engagement);root.addEventListener('pageshow',e=>{if(e.persisted){engagementSent=false;visibleAt=performance.now();updateCatalog();}});
  const perf={};
  if(root.PerformanceObserver)for(const type of ['largest-contentful-paint','layout-shift','event'])try{
    const po=new PerformanceObserver(list=>{for(const entry of list.getEntries()){
      if(type==='largest-contentful-paint')perf.lcp_ms=entry.startTime;
      if(type==='layout-shift'&&!entry.hadRecentInput)perf.layout_shift_sum=(perf.layout_shift_sum||0)+entry.value;
      if(type==='event'&&entry.interactionId)perf.max_interaction_ms=Math.max(perf.max_interaction_ms||0,entry.duration);
    }});po.observe({type,buffered:true,...(type==='event'?{durationThreshold:40}:{})});
  }catch(_){}
  function reportPerformance(){for(const[metric,value]of Object.entries(perf)){track('web_performance',{metric,value,[metric]:value});delete perf[metric];}}
  root.addEventListener('pagehide',reportPerformance);d.addEventListener('visibilitychange',()=>{if(d.visibilityState==='hidden')reportPerformance();});
  let errors=0;root.addEventListener('error',e=>{if(errors++>=5)return;track('site_error',{error_type:e.target?.tagName==='IMG'?'image_load':e.target?.tagName==='SCRIPT'?'script_load':'javascript'});},true);
  root.addEventListener('unhandledrejection',()=>{if(errors++<5)track('site_error',{error_type:'unhandled_promise'});});
  function init(){
    if(config.artist)track('artist_view',{artist_name:config.artist,...journey()});
    if(config.show)track('show_view',{show_name:config.show,...journey()});
    const params=new URLSearchParams(location.search);let host='';try{host=new URL(d.referrer).hostname;}catch(_){}
    if((host && host!==location.hostname)||params.has('utm_source'))track('traffic_arrival',{source:params.get('utm_source')||'',medium:params.get('utm_medium')||'',campaign:params.get('utm_campaign')||'',referrer_host:host});
    const el=d.querySelector('[data-live-show-count]');count=Number(el?.textContent)||0;
    observePanel();refreshCatalog();
    setTimeout(results,900);
    if(location.hash==='#browse-states'){
      const finder=d.getElementById('browse-states');const details=finder?.querySelector('details');if(details)details.open=true;
      if(finder){finder.tabIndex=-1;finder.focus({preventScroll:true});finder.scrollIntoView({block:'start'});}
    }
  }
  if(d.readyState==='loading')d.addEventListener('DOMContentLoaded',init,{once:true});else init();
  let renderedDay=today();
  setInterval(()=>{if(d.visibilityState==='visible'){
    if(today()!==renderedDay){renderedDay=today();root.location.reload();return;}
    updateCatalog();refreshCatalog();
  }},60000);
})(typeof window==='object'?window:globalThis);

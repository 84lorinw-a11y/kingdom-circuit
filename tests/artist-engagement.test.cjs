const test=require('node:test'),assert=require('node:assert/strict');
const {classifyLink}=require('../assets/fan-engagement.js');
function classify(href, extra={}) {
 return classifyLink({url:new URL(href,'https://kingdomcircuit.com'),origin:'https://kingdomcircuit.com',base:'/',statePaths:{'/shows/texas/':'Texas'},...extra});
}
test('Kingdom Circuit Facebook is never attributed to the artist whose page is open',()=>{
 assert.deepEqual(classify('https://www.facebook.com/profile.php?id=61593510924754',{inArtistArea:true}),{event:'facebook_referral',params:{platform:'facebook',destination_host:'www.facebook.com'}});
 assert.equal(classify('https://www.facebook.com/otherartist',{inArtistArea:true}).event,'artist_social_click');
 assert.equal(classify('https://notfacebook.com/otherartist',{inArtistArea:true}),null);
});
test('ticket, registration and informational referrals stay distinguishable without implying purchase',()=>{
 for(const[label,kind]of[['Tickets','ticket'],['Register','registration'],['Official details','information']]) {
  const r=classify('https://tickets.example/show',{inEventArea:true,label});
  assert.equal(r.event,'ticket_referral');assert.equal(r.params.referral_type,kind);
 }
 assert.equal(classify('https://instagram.com/event',{inEventArea:true,inArtistArea:true,label:'Official details'}).event,'ticket_referral');
});
test('artist selection is a destination action; state links are not weekend or month selections',()=>{
 assert.deepEqual(classify('/artists/hulvey/'),{event:'artist_select',params:{destination_path:'/artists/hulvey/'}});
 assert.equal(classify('/artists/'),null);
 assert.deepEqual(classify('/shows/texas/'),{event:'state_select',params:{destination_path:'/shows/texas/',state:'Texas'}});
 assert.equal(classify('/shows/this-weekend/').event,'collection_select');
 assert.equal(classify('/shows/this-month/').event,'collection_select');
 assert.equal(classify('/shows/texas/houston/').event,'collection_select');
 assert.equal(classify('/event/test/').event,'event_select');
 assert.equal(classify('javascript:alert(1)'),null);
 const r=classify('https://84lorinw-a11y.github.io/kingdom-circuit-test/artists/hulvey/',{origin:'https://84lorinw-a11y.github.io',base:'/kingdom-circuit-test/'});
 assert.equal(r.event,'artist_select');
});
const {STORE,safeText,clean,today,countShows,tracker,attemptState}=require('../assets/fan-engagement.js');
function storage(){const s=new Map();return{getItem:k=>s.get(k),setItem:(k,v)=>s.set(k,v)};}
test('count matches inclusive end dates, deduplicates events and crosses Pacific midnight',()=>{
 const shows=[{path:'/a',date:'2026-10-23'},{path:'/b',date:'2026-10-21',end:'2026-10-24'},{path:'/c',date:'2027-01-02'},{path:'/a',date:'2026-10-23'}];
 assert.equal(today(new Date('2026-10-24T06:59:59Z')),'2026-10-23');assert.equal(today(new Date('2026-10-24T07:00:00Z')),'2026-10-24');
 assert.equal(countShows(shows,'2026-10-23'),3);assert.equal(countShows(shows,'2026-10-24'),2);assert.equal(countShows(shows,'2026-10-25'),1);
 assert.equal(countShows([...shows,{path:'/new',date:'2026-11-01'}],'2026-10-25'),2);
});
test('test delivery is disabled on every host and keeps no local event log',()=>{
 let calls=0;const s=storage();
 for(const host of ['kingdomcircuit.com','localhost','84lorinw-a11y.github.io']) tracker({mode:'test',pageType:'artist'},{storage:s,path:'/kingdom-circuit-test/artists/mike/',host,width:()=>390,gtag:()=>calls++})('artist_view');
 assert.equal(calls,0);assert.equal(s.getItem(STORE),undefined);
});
test('production adapter requires both explicit production mode and production hostname',()=>{
 let calls=[];for(const[mode,host]of[['test','kingdomcircuit.com'],['production','localhost'],['production','84lorinw-a11y.github.io'],['production','kingdomcircuit.com']]){
 tracker({mode,pageType:'show'},{storage:storage(),path:'/event/a/',host,width:()=>1400,gtag:(...a)=>calls.push(a)})('ticket_referral',{show_name:'A',destination_host:'eventbrite.com'});
 }
 assert.equal(calls.length,1);assert.equal(calls[0][1],'ticket_referral');assert.equal(calls[0][2].transport_type,'beacon');
});
test('storage rejection cannot interrupt navigation or form completion',()=>{
 assert.doesNotThrow(()=>tracker({mode:'test'},{storage:{getItem(){throw Error()},setItem(){throw Error()}},path:'/',width:()=>400})('form_success',{form_type:'new_show'}));
});
test('submission requires an attempt and a server acknowledgment; duplicates suppressed, retries work',()=>{
 const f={},s=attemptState();assert.equal(s.finish(f,'success'),null);assert.ok(s.start(f,'show_correction'));assert.equal(s.start(f,'show_correction'),null);
 assert.ok(s.attempt(f,'show_correction'));assert.equal(s.attempt(f,'new_show'),null);assert.equal(s.finish(f,'sending'),null);
 assert.deepEqual(s.finish(f,'error'),{type:'show_correction',status:'error'});assert.equal(s.finish(f,'success'),null);
 assert.ok(s.attempt(f,'show_correction'));assert.deepEqual(s.finish(f,'success'),{type:'show_correction',status:'success'});assert.equal(s.finish(f,'success'),null);
});
test('contact details, query URLs and long input cannot enter analytics',()=>{
 for(const input of ['a@b.com','https://site/?token=private','(555) 123-4567','www.example.com'])assert.equal(safeText(input),'[redacted]');
 assert.equal(safeText('Hulvey'),'Hulvey');assert.equal(safeText('x'.repeat(300)).length,100);assert.deepEqual(clean({raw_error:'secret',result_count:0}),{result_count:0});
});

test('safe public hosts and dated event paths survive sanitization, query strings do not',()=>{
 assert.deepEqual(clean({destination_host:'www.miketeezymusic.com',page_path:'/event/show-2026-10-24/?email=secret'}),{destination_host:'www.miketeezymusic.com',page_path:'/event/show-2026-10-24/'});
});

test('the real delegated click handler sends one classified receipt with the destination artist and shelf show title',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),listeners={},calls=[];
 const config={mode:'production',base:'/',pageType:'artist',artist:'Mike Malagies',statePaths:{'/shows/texas/':'Texas'}};
 const d={readyState:'loading',visibilityState:'hidden',getElementById:()=>({textContent:JSON.stringify(config)}),querySelector:()=>null,addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn)};
 const window={document:d,sessionStorage:storage(),innerWidth:390,gtag:(...args)=>calls.push(args),addEventListener(){}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../assets/fan-engagement.js'),'utf8'),{window,document:d,location:new URL('https://kingdomcircuit.com/artists/mike-malagies/'),URL,URLSearchParams,setInterval(){},setTimeout(){},clearTimeout(){},performance:{now:()=>0}});
 function click(href,label,kind='plain'){
  const card={querySelector:()=>({textContent:'The HRVST'})};
  const a={href:new URL(href,'https://kingdomcircuit.com').href,textContent:label,dataset:{},getAttribute:()=>null,
   querySelector:s=>s==='strong'&&kind==='artist'?{textContent:'Hulvey'}:null,
   closest:s=>s==='a[href]'?a:s==='[data-event-card],.event-detail,.kc-discovery-show'&&kind==='show'?card:s==='[aria-labelledby="kc-weekend-heading"]'&&kind==='show'?{}:null};
  for(const fn of listeners.click)fn({type:'click',target:a});
 }
 click('https://www.facebook.com/profile.php?id=61593510924754','Facebook');
 click('/artists/hulvey/','Hulvey 5 upcoming shows','artist');
 click('/event/the-hrvst/','Poster','show');
 click('/shows/this-weekend/','This Weekend');
 click('https://eventbrite.com/details','Official details','show');
 assert.deepEqual(calls.map(c=>c[1]),['facebook_referral','artist_select','event_select','collection_select','ticket_referral']);
 assert.equal(calls[1][2].artist_name,'Hulvey');assert.equal(calls[2][2].show_name,'The HRVST');
 assert.equal(calls[2][2].placement,'home_this_week');assert.equal(calls[4][2].referral_type,'information');
});

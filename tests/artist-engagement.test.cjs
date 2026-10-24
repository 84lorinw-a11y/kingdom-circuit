const test=require('node:test'),assert=require('node:assert/strict');
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

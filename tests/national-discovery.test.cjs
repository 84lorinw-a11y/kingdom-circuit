const test = require('node:test');
const assert = require('node:assert/strict');
const {previewExpired} = require('../assets/national-discovery.js');
test('stale weekly previews are suppressed after Sunday, including year rollover', () => {
  assert.equal(previewExpired('2026-10-18','2026-10-18'),false);
  assert.equal(previewExpired('2026-10-18','2026-10-19'),true);
  assert.equal(previewExpired('2027-01-03','2027-01-04'),true);
  assert.equal(previewExpired(undefined,'2026-10-19'),false);
});
const {normalize, activeOn, matches} = require('../assets/national-discovery.js');
const card = {date:'2026-10-16', endDate:'2026-10-18', search:'Artist – Live in Dallas', artists:'artist|guest', state:'TX', type:'concert'};
const {weeklyWindow, weeklySelection, dateLabel, refreshWeeklyPreviews} = require('../assets/national-discovery.js');
test('Monday rollover selects the full requested weeks without expired shows, caps or duplicates', () => {
  const records = ['2026-10-18','2026-10-19','2026-10-25','2026-10-26','2026-11-01','2026-11-02'].map(date => ({date}));
  records.push({date:'2026-10-17',endDate:'2026-10-20'});
  const result = weeklySelection(records,'2026-10-19');
  assert.deepEqual(result.range,{start:'2026-10-19',end:'2026-10-25',nextStart:'2026-10-26',nextEnd:'2026-11-01'});
  assert.deepEqual(result.week.map(r=>r.date),['2026-10-17','2026-10-19','2026-10-25']);
  assert.deepEqual(result.next.map(r=>r.date),['2026-10-26','2026-11-01']);
  assert.equal(dateLabel(result.range.nextStart,result.range.nextEnd),'Oct 26 – Nov 1, 2026');
  assert.equal(weeklySelection(Array.from({length:45},()=>({date:'2026-10-24'})),'2026-10-19').week.length,45);
  assert.deepEqual(weeklySelection([{date:'2026-11-03'}],'2026-10-19').next,[]);
});
test('automatic windows advance every Monday, across DST and the year boundary', () => {
  for (const [today,start,end,nextStart,nextEnd] of [
    ['2026-10-25','2026-10-19','2026-10-25','2026-10-26','2026-11-01'],
    ['2026-10-26','2026-10-26','2026-11-01','2026-11-02','2026-11-08'],
    ['2026-11-02','2026-11-02','2026-11-08','2026-11-09','2026-11-15'],
    ['2026-12-31','2026-12-28','2027-01-03','2027-01-04','2027-01-10'],
    ['2027-01-04','2027-01-04','2027-01-10','2027-01-11','2027-01-17'],
  ]) assert.deepEqual(weeklyWindow(today),{start,end,nextStart,nextEnd});
  assert.equal(dateLabel('2026-12-28','2027-01-03'),'Dec 28, 2026 – Jan 3, 2027');
});
test('a stale Sunday page restores both shelves and updates headings, empty states and controls', () => {
  const home = {dataset:{previewAsOf:'2026-10-18'}};
  const records = ['2026-10-18','2026-10-19','2026-10-25','2026-10-26','2026-11-01'].map(date => ({date,html:`<article>${date}</article>`}));
  const makeShelf = () => {
    const eyebrow = {}, empty = {}, wrap = {hidden:true};
    const section = {dataset:{previewWeekEnd:'2026-10-18'},querySelector:s=>s==='.eyebrow'?eyebrow:empty};
    return {innerHTML:'old',scrollLeft:100,eyebrow,empty,wrap,section,events:[],
      closest:s=>s==='[data-fan-shelf]'?wrap:section,dispatchEvent(e){this.events.push(e.type);}};
  };
  const week=makeShelf(),next=makeShelf();
  const root={querySelector:s=>({'[data-national-home]':home,'#kc-weekly-shows':{textContent:JSON.stringify(records)},'#kc-week-shelf':week,'#kc-next-shelf':next})[s]};
  refreshWeeklyPreviews(root,'2026-10-19');
  assert.equal(week.innerHTML,'<article>2026-10-19</article><article>2026-10-25</article>');
  assert.equal(next.innerHTML,'<article>2026-10-26</article><article>2026-11-01</article>');
  assert.equal(week.eyebrow.textContent,'October 19–25, 2026 · Nationwide');
  assert.equal(next.eyebrow.textContent,'Oct 26 – Nov 1, 2026 · Nationwide');
  for(const s of [week,next]) {assert.equal(s.wrap.hidden,false);assert.equal(s.empty.hidden,true);assert.equal(s.scrollLeft,0);assert.deepEqual(s.events,['scroll']);}
  refreshWeeklyPreviews(root,'2026-10-19');
  assert.deepEqual(week.events,['scroll']);
  refreshWeeklyPreviews(root,'2026-10-26');
  assert.equal(week.innerHTML,'<article>2026-10-26</article><article>2026-11-01</article>');
  assert.equal(next.innerHTML,'');assert.equal(next.empty.hidden,false);assert.equal(next.wrap.hidden,false);
});
test('multi-day shows remain available through their final date', () => {
  assert.equal(activeOn(card,'2026-10-18'),true);
  assert.equal(activeOn(card,'2026-10-19'),false);
});
test('all weekend filters combine without changing the underlying data', () => {
  assert.equal(matches(card,{q:'DALLAS',artist:'guest',state:'TX',type:'concert'},'2026-10-16'),true);
  for (const filter of [{state:'FL'},{artist:'other'},{type:'festival'},{q:'Miami'}]) {
    assert.equal(matches(card,filter,'2026-10-16'),false);
  }
  assert.equal(matches(card,{},'2026-10-19'),false);
});
test('cleared filters show every non-expired record', () => {
  assert.equal(matches(card,{q:'',artist:'',state:'',type:''},'2026-10-18'),true);
});
test('search handles accents and whitespace', () => {
  assert.equal(normalize('  ÉGR  '),'egr');
});

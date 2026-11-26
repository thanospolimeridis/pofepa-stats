/* Run all routes against the real data plus domain edge cases, without a browser dependency. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../src/core.js'),Evidence=require('../src/evidence.js');
const rows=[{p1:'a',p2:'b',score:[3,2]},{p1:'b',p2:'a',score:[3,0]},{p1:'c',p2:'a',score:[1,3]}];
assert.deepEqual(C.stats(rows,'a'),{played:3,wins:2,losses:1,winRate:2/3,gamesWon:6,gamesLost:6,deciding:1,decidingWins:1});
assert.equal(C.stats([], 'a').winRate,null);
assert.equal(C.h2h(rows,'a','b').length,2);
assert.equal(C.h2h(rows,'a','a').length,0);
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','πολυμερίδης'));
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','polymeridis'));
assert.equal(C.escape('<script>'), '&lt;script&gt;');
const roundFixtures=[{id:'a',round:' 2η Αγωνιστική '},{id:'b',round:'1η Αγωνιστική'},{id:'c',round:'2η   Αγωνιστική'},{id:'d',round:'Τελικός'},{id:'e',round:''},{id:'f',round:'1η Αγωνιστική (δεύτερη φάση)'}];
assert.deepEqual(C.fixtureRounds(roundFixtures).map(g=>[g.label,g.rows.map(f=>f.id)]),[
  ['2η Αγωνιστική',['a','c']],['1η Αγωνιστική',['b']],['Τελικός',['d']],['',['e']],['1η Αγωνιστική (δεύτερη φάση)',['f']]
],'Group non-adjacent round records without sorting source stages or merging different phases');
const db=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/bootstrap.json.gz')));
const manifest=JSON.parse(fs.readFileSync('dist/index.html','utf8').match(/<script type="application\/json" id="site-data">(.*?)<\/script>/s)[1]);
db.version='test';db.ranking_index='https://www.pofepa.gr/';
const event=db.events.find(e=>e.kind==='singles'), fixtureEvent=db.events.find(e=>e.kind==='fixtures');
const routes=['home','rankings','rankings?region=north&class=BET&age=40-49','rankings?region=south&class=ANE&age=70%2B','rankings?class=WOMEN','rankings?class=GENERAL','rankings?region=nonsense','players','players?q=polymeridis','players?q=nevermatch123','player/p-859','player/p-859?region=north','player/missing','matches','matches?view=teams&status=reported','matches?view=teams&status=scheduled','events','event/'+event.id,'event/'+fixtureEvent.id,'teams','team/'+db.clubs[0].id,'h2h','h2h?p1=p-859&p2=p-7','h2h?p1=p-859&p2=p-859','about','bad-route'];
routes.push('player/p-1912','player/p-2926','player/p-313','player/p-1692');
routes.push('events?region=crete&season=2025-2026','events?region=central-macedonia&season=2026-2027','events?season=all&kind=all','events?kind=singles');
routes.push('event/e-517d2fa8e574a147','event/e-517d2fa8e574a147?page=1','event/e-517d2fa8e574a147?page=99');
const fixtures=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/fixtures.json.gz')));
(async()=>{
for(const language of ['el','en']) for(const route of routes){
  const app={innerHTML:'',addEventListener(){}},skip={addEventListener(){}},requests=[];
  const context={Pofepa:C,PofepaEvidence:Evidence,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>skip},location:{hash:'#'+route},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=>language},URLSearchParams,Intl,console,setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(fs.readFileSync('dist/'+path.split('?')[0]))};
  const fetchArchive=context.fetch;context.fetch=async path=>{requests.push(path.split('?')[0]);return fetchArchive(path);};
  vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
  await context.window.pofepaReady;
  assert(app.innerHTML.includes('<main'),route+' main is missing');
  assert(!app.innerHTML.includes('undefined'),route+' leaks undefined');
  assert(!app.innerHTML.includes('Unable to load'),route+' failed to load its archive');
  assert(!app.innerHTML.includes('NaN'),route+' leaks NaN');
  const eventId=route.startsWith('event/')?route.split('?')[0].split('/')[1]:null;
  const isFixtureEvent=db.events.find(e=>e.id===eventId)?.kind==='fixtures';
  const fixtureRoute=route.startsWith('team/')||route.startsWith('matches?view=teams')||isFixtureEvent;
  assert.equal(requests.includes('data/fixtures.json.gz'),fixtureRoute,route+' fixture download scope');
  assert.equal(requests.includes('data/about.json.gz'),route==='about',route+' source-report download scope');
  if(isFixtureEvent){
    const groups=C.fixtureRounds(fixtures.filter(f=>f.event===eventId));
    const requested=Number(new URLSearchParams(route.split('?')[1]).get('page'))||0;
    const page=Math.min(requested,Math.max(0,Math.ceil(groups.length/4)-1));
    const visible=groups.slice(page*4,page*4+4);
    assert.equal((app.innerHTML.match(/class="fixture-round"/g)||[]).length,visible.length,'One section per complete round');
    const tbody=[...app.innerHTML.matchAll(/<tbody>([\s\S]*?)<\/tbody>/g)];
    assert.deepEqual(tbody.map(t=>(t[1].match(/<tr>/g)||[]).length),visible.map(g=>g.rows.length),'Round pagination must not split or lose fixtures');
    for(const group of visible)assert(app.innerHTML.includes(C.escape(group.label)),'Published round/date label must be retained');
    assert(!app.innerHTML.includes('<th scope="col">'+(language==='el'?'Αγωνιστική':'Round')+'</th>'),'Round belongs in the section heading');
  }
  if(route.startsWith('player/p-859')){assert(!app.innerHTML.includes('data-filter="region"'));assert(!app.innerHTML.includes('data-filter="list"'));assert(app.innerHTML.includes('id="athlete-rankings"'));assert(!app.innerHTML.includes('data-page-key="rpage"'));assert(!app.innerHTML.includes('All rankings'));assert(!app.innerHTML.includes('Όλες οι κατατάξεις'));}
  if(route==='player/p-1692'){
    const charts=[...app.innerHTML.matchAll(/<svg class="chart"[\s\S]*?<\/svg>/g)];
    assert.equal(charts.length,1,'Athlete history must use one combined chart');
    const player=db.players.find(p=>p.id==='p-1692');
    const history=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/'+player.archive)))[player.id].history;
    const records=history.map(([id,row])=>({snapshot:db.snapshots.find(s=>s.id===id),points:row[2]})).filter(h=>h.snapshot.list==='ΓΕΝΙΚΟΣ'&&h.points!==null);
    assert(new Set(records.map(h=>h.snapshot.region)).size>1,'Fixture must cover multiple source regions');
    const unique=new Set(records.map(h=>JSON.stringify([h.snapshot.period,h.points])));
    assert.equal((charts[0][0].match(/<circle /g)||[]).length,unique.size,'Preserve distinct points and collapse only identical month/value pairs');
    assert(!app.innerHTML.includes('<h3>'),'Combined chart must have no regional or national subheadings');
  }
  if(route==='rankings?region=north&class=BET&age=40-49')assert(app.innerHTML.includes('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ'));
  if(route==='events'||route==='teams'){
    assert.equal((app.innerHTML.match(/class="competition-group"/g)||[]).length,9,'Current season must expose the nine original regional groups');
    assert(app.innerHTML.includes('id="competition-crete"'));
    assert(app.innerHTML.includes('id="competition-central-macedonia"'));
    assert(!app.innerHTML.includes('id="competition-unspecified"'));
  }
  if(route==='events?region=crete&season=2025-2026'){
    assert.equal((app.innerHTML.match(/class="competition-group"/g)||[]).length,1);
    assert(app.innerHTML.includes('id="competition-crete"'));
    assert(app.innerHTML.includes('Play off (final four)'),'Generic document title must inherit the source region');
    assert(!app.innerHTML.includes('Α1-Α2'),'Attica cup must not leak into Crete');
  }
}
console.log(`Passed domain checks and ${routes.length*2} route/language renders.`);

// A tab opened before a deployment can fetch a newer player shard with an
// event absent from its already-loaded index. It must offer a full reload.
const zlib=require('node:zlib'),stale=JSON.parse(zlib.gunzipSync(fs.readFileSync('dist/data/bootstrap.json.gz')));
const player=stale.players.find(p=>p.id==='p-1912');
const record=JSON.parse(zlib.gunzipSync(fs.readFileSync('dist/'+player.archive)))[player.id];
const newEvent=record.matches.find(m=>m.date==='2026-10-31').event;
stale.events=stale.events.filter(e=>e.id!==newEvent);
const handlers={},errors=[];let reloaded=false;
const app={innerHTML:'',addEventListener:(name,fn)=>{handlers[name]=fn;}};
const context={Pofepa:C,PofepaEvidence:Evidence,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>({addEventListener(){}})},location:{hash:'#player/p-1912',reload:()=>{reloaded=true;}},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=> 'en'},URLSearchParams,Intl,console:{error:error=>errors.push(error)},setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(path.split('?')[0]===manifest.bootstrap?zlib.gzipSync(JSON.stringify(stale)):fs.readFileSync('dist/'+path.split('?')[0]))};
vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
await context.window.pofepaReady;
assert.equal(errors.length,1,'Stale index should exercise the rendering failure');
assert(app.innerHTML.includes('id="reload"'),'Stale data must offer a full page reload');
assert(!app.innerHTML.includes('Loading archive'),'Rendering failure must not leave a loading message');
handlers.click({target:{closest:()=>({id:'reload',dataset:{}})}});
assert(reloaded,'Recovery must refresh the index as well as the player data');
console.log('Passed stale deployment recovery check.');

})().catch(error=>{console.error(error);process.exitCode=1;});

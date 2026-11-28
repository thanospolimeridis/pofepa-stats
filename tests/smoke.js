/* Run all routes against the real data plus domain edge cases, without a browser dependency. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../src/core.js'),Evidence=require('../src/evidence.js'),AthleteStats=require('../src/athlete-stats.js');
const rows=[{p1:'a',p2:'b',score:[3,2]},{p1:'b',p2:'a',score:[3,0]},{p1:'c',p2:'a',score:[1,3]}];
assert.deepEqual(C.stats(rows,'a'),{played:3,wins:2,losses:1,winRate:2/3,gamesWon:6,gamesLost:6,deciding:1,decidingWins:1});
assert.equal(C.stats([], 'a').winRate,null);
assert.equal(C.h2h(rows,'a','b').length,2);
assert.equal(C.h2h(rows,'a','a').length,0);
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','πολυμερίδης'));
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','polymeridis'));
{const names=['ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','ΠΑΠΑΔΟΠΟΥΛΟΣ ΓΕΩΡΓΙΟΣ','ΝΤΟΥΣΗΣ ΜΠΑΜΠΗΣ','Ελένη Ζαχαρίου','NGA ESSOE JOEL'];
  const queries=['','  ','πολυμ','polymeridis','Παπαδόπουλος γεωργ','papadopoulos georgios','dousis','ou','σ ζ','joel ελένη','αθανασιος γεωργ','xyz'];
  for(const q of queries)for(const a of names)for(const b of names)assert.equal(C.pairSearch(q)(a,b),C.search(a+' '+b,q),'pairSearch must equal search: '+[q,a,b].join(' | '));}
{const people=[{id:'a',name:'ΠΑΠΑΔΟΠΟΥΛΟΣ ΓΕΩΡΓΙΟΣ',registration:'12',team:'ΑΚΤΩΡ'},{id:'b',name:'ΓΕΩΡΓΙΟΥ ΠΑΠΑΣ',registration:'120',team:'ΑΡΗΣ'},{id:'c',name:'ΝΙΚΟΛΑΟΥ ΜΑΡΙΑ',registration:'',team:'ΑΚΤΩΡ'}];
  const played={a:5,b:1,c:9},suggest=(q,limit)=>C.playerSuggestions(people,q,{text:p=>[p.name,p.registration,p.team].join(' '),played:p=>played[p.id],limit});
  const ids=q=>suggest(q).results.map(p=>p.id);
  assert.deepEqual(ids('γεωργ'),['b','a'],'Names starting with the query come first');
  assert.deepEqual(ids('12'),['a','b'],'An exact registration comes first');
  assert.deepEqual(ids('papad'),['a'],'Latin input matches Greek names');
  assert.deepEqual(ids('Παπαδόπουλος'),['a'],'Accents are ignored');
  assert.deepEqual(ids('ακτωρ'),['c','a'],'Team matches rank by matches played');
  assert.deepEqual(ids('  '),[]);
  assert.deepEqual(suggest('α',1),{total:3,results:[people[2]]},'Limit keeps the total');}
assert.equal(C.escape('<script>'), '&lt;script&gt;');
const roundFixtures=[{id:'a',round:' 2η Αγωνιστική '},{id:'b',round:'1η Αγωνιστική'},{id:'c',round:'2η   Αγωνιστική'},{id:'d',round:'Τελικός'},{id:'e',round:''},{id:'f',round:'1η Αγωνιστική (δεύτερη φάση)'}];
assert.deepEqual(C.fixtureRounds(roundFixtures).map(g=>[g.label,g.rows.map(f=>f.id)]),[
  ['2η Αγωνιστική',['a','c']],['1η Αγωνιστική',['b']],['Τελικός',['d']],['',['e']],['1η Αγωνιστική (δεύτερη φάση)',['f']]
],'Group non-adjacent round records without sorting source stages or merging different phases');
const db=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/bootstrap.json.gz')));
const about=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/about.json.gz')));
const manifest=JSON.parse(fs.readFileSync('dist/index.html','utf8').match(/<script type="application\/json" id="site-data">(.*?)<\/script>/s)[1]);
db.version='test';db.ranking_index='https://www.pofepa.gr/';
const event=db.events.find(e=>e.kind==='singles'), fixtureEvent=db.events.find(e=>e.kind==='fixtures');
const routes=['home','rankings','rankings?region=north&class=BET&age=40-49','rankings?region=south&class=ANE&age=70%2B','rankings?class=WOMEN','rankings?class=GENERAL','rankings?region=nonsense','players','players?q=polymeridis','players?q=nevermatch123','player/p-859','player/p-859?region=north','player/missing','matches','matches?view=teams&status=reported','matches?view=teams&status=scheduled','events','event/'+event.id,'event/'+fixtureEvent.id,'teams','team/'+db.clubs[0].id,'h2h','h2h?p1=p-859&p2=p-7','h2h?p1=p-859&p2=p-859','about','bad-route'];
routes.push('players?category=BET%2040-49','players?category=ANE%2050-59','player/p-859?range=3m','player/p-859?season=2025-2026','player/p-859?season=missing','player/p-1912','player/p-2926','player/p-313','player/p-1692');
routes.push('events?region=crete&season=2025-2026','events?region=central-macedonia&season=2026-2027','events?season=all&kind=all','events?kind=singles');
routes.push('event/e-872537db429e91ee','event/e-076a3ed10707b3f2','event/e-c3a3dcdc39edcc8e','event/e-df9707fab1c9c47f','event/e-5d1c3230f89cd9aa','event/e-d7de6d7827232949','events?competition=cup');
routes.push('event/e-517d2fa8e574a147','event/e-517d2fa8e574a147?page=1','event/e-517d2fa8e574a147?page=99');
const otherSeasonEvent=db.events.find(e=>e.kind==='singles'&&e.season==='2024-2025');
routes.push('matches?season=2025-2026','matches?q=papadopoulos&season=2025-2026','matches?season=2025-2026&event='+otherSeasonEvent.id,'matches?view=teams&season=2025-2026','nonexistent','event/missing');
const fullMatches=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/matches.json.gz')));
const eventSeason=new Map(db.events.map(e=>[e.id,e.season]));
const fixtures=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/fixtures.json.gz')));
const rendered=new Map();
(async()=>{
for(const language of ['el','en']) for(const route of routes){
  const app={innerHTML:'',addEventListener(){}},skip={addEventListener(){}},requests=[];
  const context={Pofepa:C,PofepaEvidence:Evidence,PofepaAthleteStats:AthleteStats,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>skip},location:{hash:'#'+route},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=>language},URLSearchParams,Intl,console,setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(fs.readFileSync('dist/'+path.split('?')[0]))};
  const fetchArchive=context.fetch;context.fetch=async path=>{requests.push(path.split('?')[0]);return fetchArchive(path);};
  vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
  await context.window.pofepaReady;
  rendered.set(language+':'+route,app.innerHTML);
  assert(app.innerHTML.includes('<main'),route+' main is missing');
  assert(!app.innerHTML.includes('undefined'),route+' leaks undefined');
  assert(!app.innerHTML.includes('Unable to load'),route+' failed to load its archive');
  assert(!app.innerHTML.includes('NaN'),route+' leaks NaN');
  const eventId=route.startsWith('event/')?route.split('?')[0].split('/')[1]:null;
  const isFixtureEvent=db.events.find(e=>e.id===eventId)?.kind==='fixtures';
  const fixtureRoute=route.startsWith('team/')||route.startsWith('matches?view=teams')||isFixtureEvent;
  assert.equal(requests.includes('data/fixtures.json.gz'),fixtureRoute,route+' fixture download scope');
  assert.equal(requests.includes('data/about.json.gz'),route==='about',route+' source-report download scope');
  const cup=db.events.find(e=>e.id===eventId&&e.competition_type==='cup');
  const drawRequests=requests.filter(p=>p.startsWith('data/cup-draws/'));
  assert.deepEqual(drawRequests,cup?.draw_archive?[cup.draw_archive]:[],route+' only downloads its own draw');
  if(cup){
    assert(!app.innerHTML.includes('class="fixture-round"'),'Cups must not use league rounds');
    if(cup.draw_archive){const draw=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/'+cup.draw_archive)));assert.equal((app.innerHTML.match(/class="draw-image"/g)||[]).length,draw.pages.length,'Every original draw page is shown');assert(app.innerHTML.includes('data-draw-zoom'));}
    else{const model=C.cupBracket(fixtures.filter(f=>f.event===eventId));assert.equal((app.innerHTML.match(/class="knockout-match"/g)||[]).length,model.rounds.reduce((n,r)=>n+r.matches.length,0),'Keep every published knockout fixture');}
  }
  if(isFixtureEvent&&!cup){
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
  if(route==='events?competition=cup'){assert(app.innerHTML.includes('data-competition-type="cup"'));assert(!app.innerHTML.includes('data-competition-type="league"'));}
  if(route.startsWith('player/p-859')){assert(!app.innerHTML.includes('data-filter="region"'));assert(!app.innerHTML.includes('data-filter="list"'));assert(app.innerHTML.includes('id="athlete-rankings"'));assert(!app.innerHTML.includes('data-page-key="rpage"'));assert(!app.innerHTML.includes('All rankings'));assert(!app.innerHTML.includes('Όλες οι κατατάξεις'));}
  if(route==='player/p-1692'){
    const charts=[...app.innerHTML.matchAll(/<svg class="chart athlete-ranking-chart"[\s\S]*?<\/svg>/g)];
    assert.equal(charts.length,1,'Athlete history must use one combined chart');
    const player=db.players.find(p=>p.id==='p-1692');
    const history=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/'+player.archive)))[player.id].history;
    const records=history.map(([id,row])=>({snapshot:db.snapshots.find(s=>s.id===id),points:row[2]})).filter(h=>h.snapshot.list==='ΓΕΝΙΚΟΣ'&&h.points!==null);
    assert(new Set(records.map(h=>h.snapshot.region)).size>1,'Fixture must cover multiple source regions');
    const unique=new Set(records.map(h=>JSON.stringify([h.snapshot.period,h.points])));
    assert.equal((charts[0][0].match(/<circle /g)||[]).length,unique.size,'Preserve distinct points and collapse only identical month/value pairs');
    assert(!charts[0][0].includes('<h3>'),'Combined chart must have no regional or national subheadings');
    assert.equal((charts[0][0].match(/tabindex=/g)||[]).length,1,'The chart is a single tab stop');
    assert(/^<svg [^>]*tabindex="0"[^>]*aria-describedby="ranking-readout"/.test(charts[0][0]),'The chart itself takes focus and describes the readout');
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
  const title=context.document.title,notFoundTitle=language==='el'?'Η σελίδα δεν βρέθηκε':'Page not found';
  const showsNotFound=app.innerHTML.includes('<h1>'+notFoundTitle+'</h1>');
  if(['player/missing','nonexistent','event/missing'].includes(route))assert(showsNotFound,route+' must render the not-found page');
  assert.equal(title.startsWith(notFoundTitle),showsNotFound,route+' title must match the page shown, got '+title);
  if(route==='about')assert(title.startsWith(language==='el'?'Κάλυψη & πηγές':'Coverage & sources'),'About title');
  const nav=app.innerHTML.match(/<nav class="nav"[\s\S]*?<\/nav>/)[0];
  assert(!nav.includes('id="lang"')&&app.innerHTML.includes('</nav><button class="lang" id="lang"'),'Language toggle must sit outside the scrolling nav');
  if(route==='about'){
    const monthText=p=>new Intl.DateTimeFormat(language==='el'?'el-GR':'en-GB',{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(p+'-01T12:00:00Z'));
    const periods=about.coverage.ranking_periods;
    assert(app.innerHTML.includes(monthText(periods[0]))&&app.innerHTML.includes(monthText(periods.at(-1))),'Coverage dates come from the ranking periods');
    assert(!app.innerHTML.includes('${'),'No uninterpolated template text');
    const html=app.innerHTML,size=25;
    assert(html.indexOf('<h1>')<html.indexOf('id="about-sheet-list"'),'Explanations precede the match-sheet audit');
    assert(html.indexOf('id="about-sheet-list"')<html.indexOf('id="about-sources"'),'Source inventory comes last');
    assert.equal((html.match(/<td class="source-cell">/g)||[]).length,Math.min(size,about.sources.length),'Source inventory is paginated');
    assert(html.includes('data-page-key="sheetpage"')&&html.includes('data-page-key="sourcepage"'),'Long audit lists have pagers');
  }
  if(route==='home'){
    const season=db.events.filter(e=>e.kind==='singles'&&e.region==='national').map(e=>e.season).sort().at(-1).replace('-','–');
    assert(app.innerHTML.includes(language==='el'?'Αγωνιστική περίοδος '+season:season+' season'),'Home competitions follow the newest season in the data');
    const names=Object.fromEntries((db.competition_regions||[]).map(r=>[r.id,language==='el'?r.el:r.en]));
    for(const m of db.recent_matches){
      const region=db.events.find(e=>e.id===m.event)?.competition_region;
      if(region&&region!=='unspecified'&&region!=='nationwide')assert(app.innerHTML.includes('<span class="meta">'+C.escape(names[region])+'</span>'),'Match rows show where the competition is played');
    }
  }
  if(route.startsWith('h2h')){
    assert(!app.innerHTML.includes('<datalist'),'Head to head must not ship a datalist of every profile');
    assert.equal((app.innerHTML.match(/role="combobox"/g)||[]).length,2,'Two player pickers');
    const chosen=[...app.innerHTML.matchAll(/<input type="hidden" name="(p[12])" value="([^"]*)">/g)].map(m=>m[1]+'='+m[2]);
    const params=new URLSearchParams(route.split('?')[1]||'');
    assert.deepEqual(chosen,['p1','p2'].map(k=>k+'='+(db.players.some(p=>p.id===params.get(k))?params.get(k):'')),'Pickers carry the chosen player ids');
  }
  if(route.startsWith('matches')){
    const singles=!route.includes('view=teams');
    assert.equal(requests.includes('data/match-list.json.gz'),singles,route+' compact match-list download scope');
    assert(!requests.includes('data/matches.json.gz'),route+' must not download full match records');
    assert(app.innerHTML.includes('id="filter-season"')&&app.innerHTML.includes('<optgroup label="'),route+' needs a season filter and season-grouped competitions');
  }
  if(route==='matches?q=papadopoulos&season=2025-2026'){
    const expected=fullMatches.filter(m=>eventSeason.get(m.event)==='2025-2026'&&C.search(m.names.join(' '),'papadopoulos')).length;
    assert(expected>0&&app.innerHTML.includes('role="status">'+new Intl.NumberFormat(language==='el'?'el-GR':'en-GB').format(expected)+' '),'Compact list search and season filter must match the full records');
  }
  if(route==='matches?season=2025-2026&event='+otherSeasonEvent.id){
    assert(!app.innerHTML.includes('value="'+otherSeasonEvent.id+'"'),'Competitions from other seasons are not offered');
    assert(app.innerHTML.includes('<optgroup label="2025-2026">')&&!app.innerHTML.includes('<optgroup label="2024-2025">'));
    assert(!app.innerHTML.includes(language==='el'?'Δεν βρέθηκαν εγγραφές':'No records match'),'A competition outside the chosen season is ignored, not applied');
  }
}
for(const language of ['el','en']){
  const profile=route=>rendered.get(language+':player/p-859'+route);
  const metrics=html=>html.match(/<div class="athlete-results">[\s\S]*?<\/div><section/)[0];
  const points=html=>(html.match(/data-rank-point=/g)||[]).length;
  assert.equal(metrics(profile('')),metrics(profile('?range=3m')),'Chart range must not filter match statistics');
  assert(points(profile('?range=3m'))<points(profile('')),'Short range must shorten the ranking chart');
  assert.equal(points(profile('')),points(profile('?season=2025-2026')),'Match season must not shorten ranking history');
  assert.notEqual(metrics(profile('')),metrics(profile('?season=2025-2026')),'Season must update match statistics');
  assert(profile('').indexOf('id="athlete-rankings"')<profile('').indexOf('id="athlete-matches"'),'Keep ranking chart before matches');
  // Home layout: totals in the hero, then the latest-ranking banner, a compact ranking and linked competitions.
  const home=rendered.get(language+':home'),at=text=>home.indexOf(text),count=(html,pattern)=>(html.match(pattern)||[]).length;
  assert(at('class="stats-band"')>0&&at('class="stats-band"')<at('<main'),'Home statistics sit in the hero');
  assert(at('<main')<at('class="latest-ranking"')&&at('class="latest-ranking"')<at('class="grid-two"'),'The latest-ranking banner opens the page content');
  const homeRanking=home.match(/<section class="panel home-card home-ranking">[\s\S]*?<\/section>/)[0];
  assert.equal(count(homeRanking,/<th /g),4,'The home ranking names its category once, above the table');
  assert.equal(count(homeRanking,/class="rank-chip"/g),6,'Home ranking positions are chips');
  assert.equal(count(home,/<a class="event-row" href="#event\//g),4,'Each home competition is one linked row');
  const rankings=rendered.get(language+':rankings');
  assert(rankings.includes('<span class="badge neutral">')&&!rankings.includes('class="rank-chip"'),'Full ranking tables keep the category column and plain positions');
  // Match rows carry each player's games beside the name; score bars scale to the most frequent score.
  assert(count(home,/<td class="match-players">/g)>0,'Home lists recent matches');
  for(const html of [home,profile('')])assert.equal(count(html,/class="set-score"/g),2*count(html,/<td class="match-players">/g),'Every player in a match row carries their games');
  const widths=[...profile('').matchAll(/<span class="score-bar (?:won|lost)" aria-hidden="true"><i style="width:(\d+)%">/g)].map(m=>Number(m[1]));
  assert(widths.length>0&&Math.max(...widths)===100&&widths.every(w=>w>=0&&w<=100),'Score bars scale to the most frequent score');
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
const context={Pofepa:C,PofepaEvidence:Evidence,PofepaAthleteStats:AthleteStats,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>({addEventListener(){}})},location:{hash:'#player/p-1912',reload:()=>{reloaded=true;}},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=> 'en'},URLSearchParams,Intl,console:{error:error=>errors.push(error)},setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(path.split('?')[0]===manifest.bootstrap?zlib.gzipSync(JSON.stringify(stale)):fs.readFileSync('dist/'+path.split('?')[0]))};
vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
await context.window.pofepaReady;
assert.equal(errors.length,1,'Stale index should exercise the rendering failure');
assert(app.innerHTML.includes('id="reload"'),'Stale data must offer a full page reload');
assert(!app.innerHTML.includes('Loading archive'),'Rendering failure must not leave a loading message');
handlers.click({target:{closest:()=>({id:'reload',dataset:{}})}});
assert(reloaded,'Recovery must refresh the index as well as the player data');
console.log('Passed stale deployment recovery check.');

})().catch(error=>{console.error(error);process.exitCode=1;});

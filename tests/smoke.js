/* Run all routes against the real data plus domain edge cases, without a browser dependency. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../src/core.js');
const rows=[{p1:'a',p2:'b',score:[3,2]},{p1:'b',p2:'a',score:[3,0]},{p1:'c',p2:'a',score:[1,3]}];
assert.deepEqual(C.stats(rows,'a'),{played:3,wins:2,losses:1,winRate:2/3,gamesWon:6,gamesLost:6,deciding:1,decidingWins:1});
assert.equal(C.stats([], 'a').winRate,null);
assert.equal(C.h2h(rows,'a','b').length,2);
assert.equal(C.h2h(rows,'a','a').length,0);
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','πολυμερίδης'));
assert(C.search('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ','polymeridis'));
assert.equal(C.escape('<script>'), '&lt;script&gt;');
const db=JSON.parse(require('node:zlib').gunzipSync(fs.readFileSync('dist/data/bootstrap.json.gz')));
const manifest=JSON.parse(fs.readFileSync('dist/index.html','utf8').match(/<script type="application\/json" id="site-data">(.*?)<\/script>/s)[1]);
db.version='test';db.ranking_index='https://www.pofepa.gr/';
const event=db.events.find(e=>e.kind==='singles'), fixtureEvent=db.events.find(e=>e.kind==='fixtures');
const routes=['home','rankings','rankings?region=north&class=BET&age=40-49','rankings?region=south&class=ANE&age=70%2B','rankings?class=WOMEN','rankings?class=GENERAL','rankings?region=nonsense','players','players?q=polymeridis','players?q=nevermatch123','player/p-859','player/p-859?region=north','player/missing','matches','matches?view=teams&status=reported','matches?view=teams&status=scheduled','events','event/'+event.id,'event/'+fixtureEvent.id,'teams','team/'+db.clubs[0].id,'h2h','h2h?p1=p-859&p2=p-7','h2h?p1=p-859&p2=p-859','about','bad-route'];
routes.push('player/p-1912','player/p-2926','player/p-313');
(async()=>{
for(const language of ['el','en']) for(const route of routes){
  const app={innerHTML:'',addEventListener(){}},skip={addEventListener(){}};
  const context={Pofepa:C,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>skip},location:{hash:'#'+route},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=>language},URLSearchParams,Intl,console,setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(fs.readFileSync('dist/'+path.split('?')[0]))};
  vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
  await context.window.pofepaReady;
  assert(app.innerHTML.includes('<main'),route+' main is missing');
  assert(!app.innerHTML.includes('undefined'),route+' leaks undefined');
  assert(!app.innerHTML.includes('Unable to load'),route+' failed to load its archive');
  assert(!app.innerHTML.includes('NaN'),route+' leaks NaN');
  if(route.startsWith('player/p-859')){assert(!app.innerHTML.includes('data-filter="region"'));assert(!app.innerHTML.includes('data-filter="list"'));assert(app.innerHTML.includes('data-page-key="rpage"'));}
  if(route==='rankings?region=north&class=BET&age=40-49')assert(app.innerHTML.includes('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ'));
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
const context={Pofepa:C,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(manifest)}:app,documentElement:{},querySelector:()=>({addEventListener(){}})},location:{hash:'#player/p-1912',reload:()=>{reloaded=true;}},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=> 'en'},URLSearchParams,Intl,console:{error:error=>errors.push(error)},setTimeout,clearTimeout,Blob,Response,DecompressionStream,Uint8Array,atob,fetch:async path=>new Response(path.split('?')[0]===manifest.bootstrap?zlib.gzipSync(JSON.stringify(stale)):fs.readFileSync('dist/'+path.split('?')[0]))};
vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
await context.window.pofepaReady;
assert.equal(errors.length,1,'Stale index should exercise the rendering failure');
assert(app.innerHTML.includes('id="reload"'),'Stale data must offer a full page reload');
assert(!app.innerHTML.includes('Loading archive'),'Rendering failure must not leave a loading message');
handlers.click({target:{closest:()=>({id:'reload',dataset:{}})}});
assert(reloaded,'Recovery must refresh the index as well as the player data');
console.log('Passed stale deployment recovery check.');

})().catch(error=>{console.error(error);process.exitCode=1;});

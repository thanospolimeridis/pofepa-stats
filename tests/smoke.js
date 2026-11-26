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
const db=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
db.version='test';db.ranking_index='https://www.pofepa.gr/';
const event=db.events.find(e=>e.kind==='singles'), fixtureEvent=db.events.find(e=>e.kind==='fixtures');
const routes=['home','rankings','rankings?region=north&class=BET&age=40-49','rankings?region=south&class=ANE&age=70%2B','rankings?class=WOMEN','rankings?class=GENERAL','rankings?region=nonsense','players','players?q=polymeridis','players?q=nevermatch123','player/p-859','player/p-859?region=north','player/missing','matches','matches?view=teams&status=reported','matches?view=teams&status=scheduled','events','event/'+event.id,'event/'+fixtureEvent.id,'teams','team/'+db.clubs[0].id,'h2h','h2h?p1=p-859&p2=p-7','h2h?p1=p-859&p2=p-859','about','bad-route'];
for(const language of ['el','en']) for(const route of routes){
  const app={innerHTML:'',addEventListener(){}},skip={addEventListener(){}};
  const context={Pofepa:C,document:{getElementById:id=>id==='site-data'?{textContent:JSON.stringify(db)}:app,documentElement:{},querySelector:()=>skip},location:{hash:'#'+route},window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:()=>language},URLSearchParams,Intl,console,setTimeout,clearTimeout};
  vm.runInNewContext(fs.readFileSync('src/app.js','utf8'),context,{timeout:10000});
  assert(app.innerHTML.includes('<main'),route+' main is missing');
  assert(!app.innerHTML.includes('undefined'),route+' leaks undefined');
  assert(!app.innerHTML.includes('NaN'),route+' leaks NaN');
  if(route==='rankings?region=north&class=BET&age=40-49')assert(app.innerHTML.includes('ΠΟΛΥΜΕΡΙΔΗΣ ΑΘΑΝΑΣΙΟΣ'));
}
console.log(`Passed domain checks and ${routes.length*2} route/language renders.`);

/* Route hydration/retry regression tests against actual app and built shards.
 * Run after build: node tests/hydration.js. No browser or network is used.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');
const root = path.resolve(__dirname,'..');
const Pofepa = require('../src/core.js');
const PofepaEvidence = require('../src/evidence.js');
const code = fs.readFileSync(path.join(root,'src/app.js'),'utf8');
const builtHtml = fs.readFileSync(path.join(root,'dist/index.html'),'utf8');
const manifest = JSON.parse(builtHtml.match(/<script type="application\/json" id="site-data">(.*?)<\/script>/s)[1]);
const bytes = new Map();
function readArchive(name) {
  if (!bytes.has(name)) bytes.set(name,fs.readFileSync(path.join(root,'dist',name)));
  return bytes.get(name);
}
const bootstrap = JSON.parse(zlib.gunzipSync(readArchive(manifest.bootstrap)));
assert.equal(bootstrap.bootstrap_schema,2,'Hydration tests require the new bootstrap build');
assert(!Object.hasOwn(bootstrap,'fixtures'),'Fixtures must be deferred from bootstrap');
assert(bootstrap.archives.fixtures && bootstrap.archives.about);
assert(!bootstrap.coverage.match_sheets?.reviews,'Detailed review records must be deferred');
const about = JSON.parse(zlib.gunzipSync(readArchive(bootstrap.archives.about)));
readArchive(bootstrap.archives.fixtures);
const full = JSON.parse(zlib.gunzipSync(readArchive('data/catalog.json.gz')));

function harness(payload,initialRoute,fetcher) {
  const handlers = {},windowHandlers = {},errors = [];
  let html = '',observer;
  const app = {
    addEventListener:(type,callback) => {handlers[type]=callback;},
    get innerHTML(){return html;},
    set innerHTML(value){
      html=value;
      if(observer && (value.includes('<footer') || /id="(?:retry|reload)"/.test(value))) {
        const done=observer;observer=undefined;done(value);
      }
    }
  };
  const location = {hash:'#'+initialRoute};
  const context = {
    Pofepa,PofepaEvidence,Blob,Response,DecompressionStream,Uint8Array,atob,URLSearchParams,Intl,
    document:{getElementById:id => id==='site-data'?{textContent:JSON.stringify(payload)}:app,
      documentElement:{},querySelector:() => ({addEventListener(){}})},
    location,window:{addEventListener:(type,callback) => {windowHandlers[type]=callback;},scrollTo(){}},
    localStorage:{getItem:() => 'en'},console:{error:error => errors.push(error)},
    setTimeout,clearTimeout,fetch:fetcher
  };
  vm.runInNewContext(code,context,{timeout:10000});
  async function renderedAfter(action) {
    let timer;
    const rendered = new Promise(resolve => {observer=resolve;});
    const timeout = new Promise((_,reject) => {timer=setTimeout(() => reject(new Error('Route render did not finish')),10000);});
    try {action();return await Promise.race([rendered,timeout]);}
    finally {clearTimeout(timer);observer=undefined;}
  }
  return {
    app,errors,ready:context.window.pofepaReady,
    retry:() => {
      assert(app.innerHTML.includes('id="retry"'),'Failed request must offer Retry');
      assert(!app.innerHTML.includes('id="reload"'),'Request failure must support retry without a full reload');
      return renderedAfter(() => handlers.click({target:{closest:() => ({id:'retry',dataset:{}})}}));
    },
    navigate:route => renderedAfter(() => {location.hash='#'+route;windowHandlers.hashchange();})
  };
}

async function retryAndCache(route,archive,verifyHydrated) {
  const calls = [];
  let attempts=0;
  const app = harness(manifest,route,async (request,options) => {
    calls.push(request);
    const [name,query] = request.split('?');
    assert.equal(new URLSearchParams(query).get('data'),manifest.revision,'Shard requests must use current revision');
    assert.equal(options.cache,'no-cache');
    if(name===archive && ++attempts===1)return new Response('Temporarily unavailable',{status:503});
    assert(bytes.has(name),`Unexpected route dependency ${name}`);
    return new Response(bytes.get(name));
  });
  await app.ready;
  assert.equal(attempts,1);
  assert.equal(app.errors.length,1,'The failed request should surface exactly one handled error');
  assert(app.app.innerHTML.includes('Data') || app.app.innerHTML.includes('data'));
  await app.retry();
  assert.equal(attempts,2,'Retry must issue a second request after evicting the failed promise');
  assert(!app.app.innerHTML.includes('id="retry"'));
  assert(!app.app.innerHTML.includes('Loading archive'));
  verifyHydrated(app.app.innerHTML);
  await app.navigate('players');
  await app.navigate(route);
  assert.equal(attempts,2,'Successful route revisit must reuse hydrated/cached shard');
  assert.equal(calls.filter(request => request.split('?')[0]===manifest.bootstrap).length,1);
  assert.equal(app.errors.length,1,'Recovery and route revisit must not introduce rendering errors');
  verifyHydrated(app.app.innerHTML);
}

(async () => {
  await retryAndCache('matches?view=teams',bootstrap.archives.fixtures,html => {
    assert(html.includes('Home team') && html.includes('Away team'),'Fixture table must hydrate after retry');
    assert(html.includes('<tbody><tr>'),'Recovered fixture table must contain actual rows');
  });
  await retryAndCache('about',bootstrap.archives.about,html => {
    assert(html.includes('Imported sources'));
    assert(html.includes(about.sources[0].sha256),'About hydration must restore full source metadata');
    assert(html.includes('Match sheets · import progress'),'About hydration must restore detailed coverage');
  });

  // Compact real records retain the complete offline data contract. Keep the
  // dataset small so this check exercises rendering, not archive-scale stats.
  const athlete=full.players.find(p => p.id==='p-859');
  assert(athlete);
  const matches=full.matches.filter(m => m.p1===athlete.id||m.p2===athlete.id).slice(0,8);
  assert(matches.length);
  const participants=new Set(matches.flatMap(m => [m.p1,m.p2]));
  const offline={...full,players:full.players.filter(p => participants.has(p.id)),matches,
    fixtures:full.fixtures.slice(0,3),
    snapshots:full.snapshots.map(s => ({...s,rows:s.rows.filter(row => participants.has(row[0]))})).filter(s => s.rows.length)};
  delete offline.lazy;delete offline.archives;delete offline.bootstrap_schema;
  const compressed={compressed:zlib.gzipSync(JSON.stringify(offline)).toString('base64')};
  let networkCalls=0;
  const app=harness(compressed,'player/'+athlete.id,() => {networkCalls++;throw new Error('Offline payload must not fetch shards');});
  await app.ready;
  assert.equal(app.errors.length,0,app.errors.map(String).join('\n'));
  assert(app.app.innerHTML.includes(Pofepa.escape(athlete.name)));
  assert(app.app.innerHTML.includes('id="athlete-matches"'));
  assert(app.app.innerHTML.includes('id="athlete-rankings"'));
  await app.navigate('teams');
  assert(app.app.innerHTML.includes('<tbody><tr>'),'Offline teams route must render its fixture-backed records');
  await app.navigate('about');
  assert(app.app.innerHTML.includes(full.sources[0].sha256),'Offline about route must retain full sources');
  assert.equal(app.errors.length,0,app.errors.map(String).join('\n'));
  assert.equal(networkCalls,0,'Offline athlete, teams and about routes must make no network requests');
  console.log('Passed fixtures/about failure-retry-cache hydration and compressed offline athlete/teams/about rendering.');
})().catch(error => {console.error(error);process.exitCode=1;});

/* Validate the built lazy-data contract; run after scripts/build.py. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync,gzipSync}=require('node:zlib'),{createHash}=require('node:crypto');
const dist=path.resolve(process.argv[2]||'dist');
const bytes=name=>fs.readFileSync(path.join(dist,name));
const archive=name=>JSON.parse(gunzipSync(bytes(name)));
const embedded=name=>JSON.parse(bytes(name).toString().match(/<script type="application\/json" id="site-data">(.*?)<\/script>/s)[1]);
const manifest=embedded('index.html'),bootstrapBytes=gunzipSync(bytes(manifest.bootstrap));
const bootstrap=JSON.parse(bootstrapBytes),full=archive('data/catalog.json.gz');
assert.equal(bootstrap.bootstrap_schema,2);
assert.deepEqual(bootstrap.archives,{fixtures:'data/fixtures.json.gz',about:'data/about.json.gz'});
assert.equal(manifest.revision,createHash('sha256').update(bootstrapBytes).digest('hex').slice(0,16),'revision must cover the bootstrap schema/content');
assert(!Object.hasOwn(bootstrap,'match_rankings'),'match comparisons must be deferred');
assert(!Object.hasOwn(bootstrap,'fixtures'),'fixtures must be deferred');
assert(!Object.hasOwn(bootstrap,'cup_draws'),'cup drawings must be deferred');
for(const event of bootstrap.events.filter(e=>e.draw_archive))assert.deepEqual(archive(event.draw_archive),full.cup_draws[event.id],'hosted and offline cup drawings must match');
assert(!Object.hasOwn(bootstrap,'issues'),'audit issues must be deferred');
assert.deepEqual(archive(bootstrap.archives.fixtures),full.fixtures,'fixture details and correction audit must remain intact');
assert.deepEqual(archive(bootstrap.archives.about),{sources:full.sources,coverage:full.coverage},'full source and coverage audit must be available');
assert.deepEqual(bootstrap.sources,full.sources.map(({id,url})=>({id,url})),'all source links must be available before about hydration');
assert.deepEqual(JSON.parse(bytes('coverage.json')),full.coverage);
assert.deepEqual(JSON.parse(bytes('provenance.json')),{dataset_sha256:full.dataset_sha256,sources:full.sources});
assert.deepEqual(JSON.parse(gunzipSync(Buffer.from(embedded('offline.html').compressed,'base64'))),full,'offline archive must retain the full catalog');
assert.deepEqual(archive('data/matches.json.gz'),full.matches,'full match export must remain intact');
{
  // The compact Matches-page list must restore everything the list filters and renders.
  const C=require('../src/core.js'),expanded=C.expandMatchList(archive('data/match-list.json.gz'));
  const ref=e=>({source:e.source,row:e.row});
  assert.equal(expanded.length,full.matches.length);
  full.matches.forEach((m,i)=>{
    const x=expanded[i];
    assert.deepEqual([x.date,x.event,x.p1,x.p2,x.score,x.names,x.region,x.regions,x.source,x.row],[m.date,m.event,m.p1,m.p2,m.score,m.names,m.region,m.regions,m.source,m.row],m.id);
    assert.deepEqual(x.evidence||[ref(x)],(m.evidence||[m]).map(ref),m.id+' evidence');
    assert.deepEqual(x.document_evidence||[],(m.document_evidence||[]).map(ref),m.id+' document evidence');
    assert.deepEqual(x.sheet_corrections,m.sheet_corrections,m.id+' corrections');
  });
}
assert.deepEqual(bootstrap.matches,full.matches.slice(0,6));
assert.deepEqual(bootstrap.coverage.ranking_periods,full.coverage.ranking_periods);
for(const [key,value] of Object.entries(bootstrap.coverage)){
  assert(key==='ranking_periods'||key==='match_sheets'||value===null||typeof value!=='object','unexpected detailed coverage in bootstrap: '+key);
  if(key!=='match_sheets')assert.deepEqual(value,full.coverage[key]);
}
for(const key of ['reviews','issues','unavailable_sources'])assert(!Object.hasOwn(bootstrap.coverage.match_sheets||{},key),'match-sheet detail must be deferred: '+key);
for(const pid of ['p-859','p-1692']){
  const player=bootstrap.players.find(p=>p.id===pid),record=archive(player.archive)[pid];
  assert.deepEqual(record.rank_comparisons,Object.fromEntries(record.matches.filter(m=>full.match_rankings[m.id]).map(m=>[m.id,full.match_rankings[m.id]])),'profile must retain the same ranking evidence as offline');
}
const latest=full.coverage.ranking_periods.at(-1);
for(const list of ['ΓΕΝΙΚΟΣ','BET 40-49']){
  const original=full.snapshots.find(s=>s.region==='national'&&s.period===latest&&s.list===list);
  assert.deepEqual(bootstrap.snapshots.find(s=>s.id===original.id).rows,original.rows,'home ranking and latest team roster must stay inline');
}
const legacy={...bootstrap,fixtures:full.fixtures,sources:full.sources,coverage:full.coverage};
delete legacy.archives;delete legacy.bootstrap_schema;
const priorBytes=gzipSync(JSON.stringify(legacy),{level:9}).length,currentBytes=bytes(manifest.bootstrap).length;
assert(currentBytes<priorBytes*.65,'bootstrap should save at least35% against its pre-split equivalent');
console.log(`Bootstrap contract passed: ${currentBytes.toLocaleString()} bytes, ${Math.round((1-currentBytes/priorBytes)*100)}% smaller; full audit, fixtures and offline archive preserved.`);

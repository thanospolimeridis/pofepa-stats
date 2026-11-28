/* Profile aggregation invariants: node tests/athlete-stats.js */
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {summarize}=require('../src/athlete-stats.js');

const events=[{id:'new',season:'2025-2026'},{id:'cup',season:'2025-2026'},{id:'old',season:'2024-2025'}];
const match=(id,p1,p2,score,date,event)=>({id,p1,p2,score,date,event});
const rows=[
  match('a','athlete','other-b',[3,0],'2025-10-01','new'),
  match('b','other-b','athlete',[3,2],'2025-10-02','new'),
  match('c','other-c','athlete',[1,3],'2025-10-03','cup'),
  match('d','athlete','other-c',[0,3],'2025-10-04','cup'),
  match('e','other-d','athlete',[2,3],'2024-10-04','old'),
  match('f','athlete','other-d',[1,3],'2024-10-05','old'),
  match('unrelated','someone','else',[3,0],'2025-11-01','new'),
];
const ranks={
  a:{snapshot:'general:2025-09',ranks:[20,10]},  // beat a higher-ranked opponent
  b:{snapshot:'general:2025-09',ranks:[30,20]},  // lost, viewed from the second side
  c:{snapshot:'general:2025-09',ranks:[10,10]},  // equal official position
  d:{snapshot:'general:2025-09',ranks:[10,null]},
  e:{snapshot:'general:2024-09',ranks:[40,30]},  // beat a lower-ranked opponent
};
const saved=JSON.stringify({rows,events,ranks});
const summary=summarize(rows,'athlete',events,ranks);
assert.deepEqual(summary.totals,{played:6,wins:3,losses:3,winRate:.5,gamesWon:12,gamesLost:12,deciding:2,decidingWins:1});
assert.deepEqual(summary.scoreLines.map(r=>[r.mine,r.theirs,r.count]),[[3,0,1],[3,1,1],[3,2,1],[2,3,1],[1,3,1],[0,3,1]]);
assert.deepEqual(summary.opponents.map(o=>[o.id,o.played,o.wins,o.losses,o.winRate]),[
  ['other-b',2,1,1,.5],['other-c',2,1,1,.5],['other-d',2,1,1,.5],
]);
assert.deepEqual(summary.bySeason.map(s=>[s.season,s.events,s.played,s.wins,s.losses,s.winRate]),[
  ['2025-2026',2,4,2,2,.5],['2024-2025',1,2,1,1,.5],
]);
assert.deepEqual(summary.byEvent.map(e=>[e.id,e.last,e.played,e.wins,e.losses,e.winRate]),[
  ['cup','2025-10-04',2,1,1,.5],['new','2025-10-02',2,1,1,.5],['old','2024-10-05',2,1,1,.5],
]);
assert.deepEqual(summary.vsRanking,{higher:[1,0],lower:[1,1],level:[1,0],unknown:[0,2]});
assert.deepEqual(summary.bestWins.map(w=>[w.match.id,w.opponent,w.rank,w.snapshot]),[
  ['c','other-c',10,'general:2025-09'],['a','other-b',10,'general:2025-09'],['e','other-d',40,'general:2024-09'],
]);
assert.equal(summary.bestWins[0].match,rows[2],'Evidence retains the original match');
assert.equal(JSON.stringify({rows,events,ranks}),saved,'No input mutation');
assert.deepEqual(summarize([...rows].reverse(),'athlete',new Map(events.map(e=>[e.id,e])),new Map(Object.entries(ranks))),summary,'Input ordering and index shape cannot alter results');
assert.deepEqual(summarize(rows,'athlete',Object.fromEntries(events.map(e=>[e.id,e])),ranks),summary);

// Every result appears once in each independent partition.
for(const total of [summary.scoreLines.reduce((n,r)=>n+r.count,0),summary.opponents.reduce((n,r)=>n+r.played,0),summary.bySeason.reduce((n,r)=>n+r.played,0),summary.byEvent.reduce((n,r)=>n+r.played,0),Object.values(summary.vsRanking).flat().reduce((a,b)=>a+b,0)])assert.equal(total,summary.totals.played);
const season=summarize(rows.filter(m=>m.event==='old'),'athlete',events,ranks);
assert.equal(season.totals.played,2);assert.equal(season.totals.deciding,1);
assert.deepEqual(season.bestWins.map(w=>w.match.id),['e']);
assert.deepEqual(season.opponents.map(o=>o.id),['other-d']);

// Rankings must be paired, source-bound positive positions. An absent or
// malformed comparison is unknown, never a current-rank fallback.
for(const comparison of [undefined,{}, {snapshot:'old',ranks:[10]}, {snapshot:'old',ranks:[0,1]}, {snapshot:'old',ranks:[10,'2']},{ranks:[10,2]}]) {
  const result=summarize([rows[0]],'athlete',events,{a:comparison});
  assert.deepEqual(result.vsRanking.unknown,[1,0]);assert.deepEqual(result.bestWins,[]);
}
const otherSide=summarize([rows[2]],'other-c',events,ranks);
assert.deepEqual(otherSide.scoreLines,[{mine:1,theirs:3,count:1}]);
assert.deepEqual(otherSide.vsRanking.level,[0,1]);
assert.deepEqual(otherSide.bestWins,[]);

const victories=Array.from({length:8},(_,i)=>match('v'+i,'athlete','opponent-'+i,[3,0],'2025-10-01','new'));
const victoryRanks=Object.fromEntries(victories.map(m=>[m.id,{snapshot:'general:2025-09',ranks:[20,1]}]));
assert.deepEqual(summarize([...victories].reverse(),'athlete',events,victoryRanks).bestWins.map(w=>w.match.id),['v0','v1','v2','v3','v4'],'Best wins are capped with deterministic ties');

const empty=summarize([],'athlete');
assert.deepEqual(empty,{totals:{played:0,wins:0,losses:0,winRate:null,gamesWon:0,gamesLost:0,deciding:0,decidingWins:0},scoreLines:[],opponents:[],bySeason:[],byEvent:[],vsRanking:{higher:[0,0],lower:[0,0],level:[0,0],unknown:[0,0]},bestWins:[]});
assert.deepEqual(summarize(rows,'absent'),empty);
assert.equal(summarize([rows[0]],'athlete').bySeason[0].season,'—');
const browser={};vm.runInNewContext(fs.readFileSync(require.resolve('../src/athlete-stats.js'),'utf8'),browser,require('./lib/source.js')('athlete-stats.js'));
assert.equal(typeof browser.PofepaAthleteStats.summarize,'function');
console.log('Passed athlete score, opponent, season, event and source-ranking summaries.');

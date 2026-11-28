/* Source-ordered knockout model: node tests/cup-bracket.js */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const zlib=require('node:zlib');
const {cupBracket}=require('../src/core.js');
const fixture=(id,round,home,away,score=[4,0],extra={})=>({id,event:'cup',round,home,away,clubs:[home,away],score,status:score?'reported':'scheduled',...extra});

// Winners, not row adjacency, determine the connectors. Input order stays intact.
const opening=[fixture('q1','Προημιτελικά','A','B'),fixture('q2','Προημιτελικά','C','D'),fixture('q3','Προημιτελικά','E','F'),fixture('q4','Προημιτελικά','G','H')];
const semis=[fixture('s1','Ημιτελικά','G','A',[1,4]),fixture('s2','Ημιτελικά','E','C',[4,2])];
const bronze=fixture('bronze','Μικρός τελικός','G','C');
const final=fixture('final','Τελικός','E','A',[1,4]);
let model=cupBracket([...opening,...semis,bronze,final]);
assert.deepEqual(model.rounds.map(r=>r.label),['Προημιτελικά','Ημιτελικά','Τελικός']);
assert.deepEqual(model.rounds[1].matches.map(m=>m.feeders),[['q4','q1'],['q3','q2']]);
assert.deepEqual(model.rounds[2].matches[0].feeders,['s2','s1']);
assert.equal(model.champion,'A');
assert.equal(model.placement[0].rows[0],bronze);

// No result, a tie, invalid score, or a scheduled result cannot advance a team.
for(const bad of [
  {score:null,status:'scheduled'}, {score:[4,4]}, {score:[-1,4]},
  {score:['4','1']}, {score:[4,1],status:'scheduled'}, {clubs:['A','A']}
]) {
  model=cupBracket([fixture('first','Semi-final','A','B',[4,0],bad),fixture('last','Final','A','C')]);
  assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);
}
assert.equal(cupBracket([fixture('f','Τελικός','A','B',null)]).champion,null);
assert.equal(cupBracket([fixture('s','Ημιτελικά','A','B')]).champion,null);
assert.equal(cupBracket([fixture('p','Μικρός τελικός','A','B')]).champion,null);
assert.equal(cupBracket([fixture('f1','Final','A','B'),fixture('f2','Final','C','D')]).champion,null);
assert.equal(cupBracket([fixture('f','Final Four','A','B')]).champion,null);

// An explicit source bye advances its only real team; no fixture/score is added.
const bye=fixture('bye',"Α' Φάση",'A','ΧΧΧ',null,{schedule_note:'ΒΥΕ'});
const byeInput=[bye,fixture('next','Τελικός','A','B')];
const before=JSON.stringify(byeInput);
model=cupBracket(byeInput);
assert.equal(model.rounds[0].matches[0].bye,true);
assert.equal(model.rounds[0].matches[0].winner,'A');
assert.deepEqual(model.rounds[1].matches[0].feeders,['bye',null]);
assert.equal(model.rounds.flatMap(r=>r.matches).length,byeInput.length);
assert.equal(bye.score,null);
assert.equal(JSON.stringify(byeInput),before);
model=cupBracket([{...bye,schedule_note:''},byeInput[1]]);
assert.equal(model.rounds[0].matches[0].bye,false);
assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);

// Repeated identities on either end are ambiguous, and events never cross-link.
model=cupBracket([fixture('a','First','A','B'),fixture('b','First','A','C'),fixture('c','Final','A','D')]);
assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);
model=cupBracket([fixture('a','First','A','B'),fixture('b','Second','A','C'),fixture('c','Second','A','D')]);
assert(model.rounds[1].matches.every(m=>m.feeders.every(f=>f===null)));
model=cupBracket([fixture('a','First','A','B'),fixture('b','Final','A','C',[4,0],{event:'another'})]);
assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);

// Exact source names work when club IDs are absent, without fuzzy name matching.
model=cupBracket([fixture('a','First','Club A','Club B',[4,0],{clubs:undefined}),fixture('b','Final','Club A','Club C',[4,0],{clubs:undefined})]);
assert.deepEqual(model.rounds[1].matches[0].feeders,['a',null]);
model=cupBracket([fixture('a','First','Club A','Club B',[4,0],{clubs:undefined}),fixture('b','Final','Club AA','Club C',[4,0],{clubs:undefined})]);
assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);

// Group results and placings are not elimination feeders. A group between
// knockout stages breaks the chain rather than implying direct advancement.
model=cupBracket([fixture('a','First','A','B'),fixture('g',"Α' όμιλος",'A','C'),fixture('b','Final','A','D')]);
assert.equal(model.groups.length,1);
assert.deepEqual(model.rounds[1].matches[0].feeders,[null,null]);
assert.equal(cupBracket([fixture('g','ΟΜΙΛΟΣ ΠΟΥΛ','A','B')]).rounds.length,0);

// All nine historical HTML cups and the single North Aegean cup-final sheet.
const data=require('./lib/catalog.js')();
const ids=['e-0d88862fea9fcb51','e-df9707fab1c9c47f','e-bfd8ebf8bd3bddab','e-5d1c3230f89cd9aa','e-fcf3bcb08ba5838b','e-d1617a2e858d3586','e-ad84a67db7ab2ac1','e-a6dcea0ba29a77cc','e-ec08bc9719630027','e-d7de6d7827232949'];
for(const id of ids) {
  const rows=data.fixtures.filter(f=>f.event===id),saved=JSON.stringify(rows);
  model=cupBracket(rows);
  const included=[...model.rounds.flatMap(r=>r.matches.map(m=>m.fixture)),...model.groups.flatMap(g=>g.rows),...model.placement.flatMap(g=>g.rows)];
  assert.deepEqual(included.map(f=>f.id).sort(),rows.map(f=>f.id).sort(),`Lost or invented source fixture in ${id}`);
  for(let r=1;r<model.rounds.length;r++) for(const match of model.rounds[r].matches) for(let side=0;side<2;side++) if(match.feeders[side]) {
    const feeder=model.rounds[r-1].matches.find(m=>m.fixture.id===match.feeders[side]);
    assert(feeder,`Feeder must be in the preceding source stage: ${id}`);
    assert.equal(feeder.winner,match.fixture.clubs[side],`Only the published winner can advance: ${id}`);
  }
  assert.equal(JSON.stringify(rows),saved);
  if(id==='e-5d1c3230f89cd9aa') {
    assert.equal(model.rounds.length,0);assert.equal(model.groups.length,1);assert.equal(model.champion,null);
  } else assert(model.champion,`Published final winner not recognized: ${id}`);
}
const restored=cupBracket(data.fixtures.filter(f=>f.event==='e-df9707fab1c9c47f'));
assert.equal(restored.rounds[0].label,"Α' Προκριματική Φάση");
assert.equal(restored.rounds[0].matches.length,8,'The recovered first round must precede the quarterfinals');
const oldAttica=cupBracket(data.fixtures.filter(f=>f.event==='e-0d88862fea9fcb51'));
assert.equal(oldAttica.rounds.flatMap(r=>r.matches).filter(m=>m.bye).length,6);
const western=cupBracket(data.fixtures.filter(f=>f.event==='e-bfd8ebf8bd3bddab'));
assert.equal(western.groups.length,2);assert.equal(western.placement.length,1);
const island=cupBracket(data.fixtures.filter(f=>f.event==='e-d7de6d7827232949'));
assert.equal(island.rounds.length,1);assert.equal(island.champion,'c-e0f7fa438ab4a2a7');
console.log('Passed source cup stages, exact winner advancement, byes, groups, placings and ten archived cup cases.');

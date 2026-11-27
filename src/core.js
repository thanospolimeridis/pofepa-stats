/* Pure domain functions shared by the offline website and Node regression tests. */
(function(root) {
  'use strict';
  const fold = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ς/g, 'σ');
  const romanize = value => fold(value).replace(/ου/g,'ou').replace(/αι/g,'ai').replace(/ει/g,'ei').replace(/οι/g,'oi').replace(/γγ/g,'ng').replace(/μπ/g,'b').replace(/ντ/g,'d').replace(/[αβγδεζηθικλμνξοπρστυφχψω]/g,c=>({α:'a',β:'v',γ:'g',δ:'d',ε:'e',ζ:'z',η:'i',θ:'th',ι:'i',κ:'k',λ:'l',μ:'m',ν:'n',ξ:'x',ο:'o',π:'p',ρ:'r',σ:'s',τ:'t',υ:'y',φ:'f',χ:'ch',ψ:'ps',ω:'o'}[c]));
  const search = (value, query) => fold(query).split(/\s+/).every(q => fold(value).includes(q) || romanize(value).includes(q));
  // search(a + ' ' + b, query) for two-name records (players or teams), with
  // folded forms cached per distinct name so a keystroke does not re-normalise
  // every row. Equivalent because query tokens never contain the separating space.
  function pairSearch(query, cache = new Map()) {
    const tokens = fold(query).split(/\s+/);
    if (tokens.every(token => !token)) return () => true;
    const forms = name => {
      let value = cache.get(name);
      if (!value) { value = [fold(name), romanize(name)]; cache.set(name, value); }
      return value;
    };
    const has = (name, token) => { const [folded, roman] = forms(name); return folded.includes(token) || roman.includes(token); };
    return (a, b) => tokens.every(token => has(a, token) || has(b, token));
  }
  // Reverse of build.py match_list(): restores the fields the Matches page
  // filters and renders. Single primary citations stay implicit (source/row).
  function expandMatchList(list) {
    const pairs = refs => {
      const out = [];
      for (let i = 0; i < (refs || []).length; i += 2) out.push({source: list.sources[refs[i]], row: refs[i + 1]});
      return out;
    };
    return list.rows.map((values, index) => {
      const [date, event, p1, p2, a, b, n1, n2, place, evidenceRefs, documentRefs] = values;
      const [region, regions] = list.regions[place], evidence = pairs(evidenceRefs);
      const match = {date, event: list.events[event], p1, p2, score: [a, b], names: [list.names[n1], list.names[n2]],
        region, source: evidence[0].source, row: evidence[0].row};
      if (regions) match.regions = regions;
      if (evidence.length > 1) match.evidence = evidence;
      if (documentRefs) match.document_evidence = pairs(documentRefs);
      if (list.corrections?.[index]) match.sheet_corrections = list.corrections[index];
      return match;
    });
  }
  function stats(matches, id) {
    const rows = matches.filter(m => m.p1 === id || m.p2 === id);
    let wins=0, gamesWon=0, gamesLost=0, deciding=0, decidingWins=0;
    for(const m of rows) {
      const [a,b] = m.p1 === id ? m.score : [...m.score].reverse();
      wins += a>b; gamesWon += a; gamesLost += b;
      if(a+b===5) { deciding++; decidingWins += a>b; }
    }
    return {played:rows.length, wins, losses:rows.length-wins, winRate:rows.length ? wins/rows.length : null, gamesWon, gamesLost, deciding, decidingWins};
  }
  const h2h = (matches,a,b) => a && b && a!==b ? matches.filter(m => (m.p1===a && m.p2===b)||(m.p1===b && m.p2===a)) : [];
  function fixtureRounds(fixtures) {
    const groups = new Map();
    for (const fixture of fixtures) {
      const label = String(fixture.round || '').trim().replace(/\s+/g, ' ');
      if (!groups.has(label)) groups.set(label, {label, rows:[]});
      groups.get(label).rows.push(fixture);
    }
    return [...groups.values()];
  }
  function cupBracket(fixtures) {
    // One competition, in published source order. A feeder is an existing
    // fixture ID, never a fabricated match or an inference from row position.
    // Groups and placement matches retain their source rows outside the draw.
    // Explicit bye slots stay in the draw with bye=true and their original
    // null score; they advance a named team without becoming a played match.
    const rounds=[], groups=[], placement=[];
    const vacant=name => /^(?:[xχ]{2,}|bye|βυε|βyε|ανευ αγωνοσ)$/i.test(fold(String(name||'').trim()));
    const team=(f,i) => {
      const name=String((i===0?f.home:f.away)||'').trim().replace(/\s+/g,' ');
      return !name || vacant(name) ? null : f.clubs?.[i] || 'name:'+name;
    };
    const advance=f => {
      const keys=[team(f,0),team(f,1)];
      const bye=/^(?:bye|βυε|βyε|ανευ αγωνοσ)$/i.test(fold(String(f.schedule_note||'').trim())) && keys.filter(Boolean).length===1;
      let side=bye ? (keys[0]?0:1) : null;
      if (!bye && f.status==='reported' && keys[0] && keys[1] && keys[0]!==keys[1] &&
          Array.isArray(f.score) && f.score.length===2 && f.score.every(n=>Number.isInteger(n)&&n>=0) && f.score[0]!==f.score[1]) side=f.score[0]>f.score[1]?0:1;
      return {key:side===null?null:keys[side],winner:side===null?null:f.clubs?.[side]||null,bye};
    };
    const isFinal=label=>/^(?:τελικοσ(?:\s|$)|final(?:\s|$))/.test(fold(label)) && !/final four/.test(fold(label));
    let previous=null;
    for (const group of fixtureRounds(fixtures)) {
      const label=fold(group.label);
      if (/ομιλ|πουλ|\bpool\b|\bgroup\b/.test(label)) { groups.push(group); previous=null; continue; }
      if (/μικρο.*τελικ|καταταξ|θεσεισ|\bthird\b|\b3rd\b|\bconsolation\b|\bplacement\b/.test(label)) { placement.push(group); continue; }
      const matches=group.rows.map(fixture=>{
        const {winner,bye}=advance(fixture);
        return {fixture,feeders:[null,null],winner,bye};
      });
      // Match both ends uniquely. A repeated team or a tied/unreported result
      // leaves an unconnected slot rather than guessing the advancement.
      if (previous) for (const match of matches) for (let side=0;side<2;side++) {
        const key=team(match.fixture,side);
        if (!key || group.rows.reduce((n,f)=>n+[0,1].filter(i=>team(f,i)===key).length,0)!==1) continue;
        const candidates=previous.matches.filter(m=>m.fixture.event===match.fixture.event && advance(m.fixture).key===key);
        if (candidates.length===1 && candidates[0].fixture.id!==match.fixture.id) match.feeders[side]=candidates[0].fixture.id;
      }
      const round={label:group.label,matches};
      rounds.push(round); previous=round;
    }
    const finals=rounds.filter(r=>isFinal(r.label)).flatMap(r=>r.matches);
    return {rounds,groups,placement,champion:finals.length===1?finals[0].winner:null};
  }
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api={fold,romanize,search,pairSearch,expandMatchList,stats,h2h,fixtureRounds,cupBracket,escape};
  if(typeof module!=='undefined' && module.exports) module.exports=api;
  else root.Pofepa=api;
})(globalThis);

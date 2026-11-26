/* Pure domain functions shared by the offline website and Node regression tests. */
(function(root) {
  'use strict';
  const fold = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ς/g, 'σ');
  const romanize = value => fold(value).replace(/ου/g,'ou').replace(/αι/g,'ai').replace(/ει/g,'ei').replace(/οι/g,'oi').replace(/γγ/g,'ng').replace(/μπ/g,'b').replace(/ντ/g,'d').replace(/[αβγδεζηθικλμνξοπρστυφχψω]/g,c=>({α:'a',β:'v',γ:'g',δ:'d',ε:'e',ζ:'z',η:'i',θ:'th',ι:'i',κ:'k',λ:'l',μ:'m',ν:'n',ξ:'x',ο:'o',π:'p',ρ:'r',σ:'s',τ:'t',υ:'y',φ:'f',χ:'ch',ψ:'ps',ω:'o'}[c]));
  const search = (value, query) => fold(query).split(/\s+/).every(q => fold(value).includes(q) || romanize(value).includes(q));
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
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api={fold,romanize,search,stats,h2h,fixtureRounds,escape};
  if(typeof module!=='undefined' && module.exports) module.exports=api;
  else root.Pofepa=api;
})(globalThis);

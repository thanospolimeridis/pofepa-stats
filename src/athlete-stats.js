/* Pure profile summaries over the already validated, completed singles archive. */
(function(root) {
  'use strict';

  const compare = (a,b) => String(a).localeCompare(String(b),'en');
  const emptyRecord = () => ({played:0,wins:0,losses:0,winRate:null});
  function addResult(record,won) {
    record.played++;
    record.wins += Number(won);
    record.losses += Number(!won);
  }
  function finish(record) {
    return {...record,winRate:record.played?record.wins/record.played:null};
  }

  /**
   * events accepts an event array, Map, or ID-keyed object. rankComparisons
   * accepts a Map or ID-keyed object containing source-bound comparisons:
   * {snapshot: snapshotID, ranks: [p1Rank,p2Rank]}. No current ranking is read.
   *
   * scoreLines contain {mine,theirs,count}; bestWins retain the original match
   * object as `match`, but neither that object nor any input collection changes.
   * Caller-selected season/event subsets define the scope of every summary.
   */
  function summarize(rows,pid,events=[],rankComparisons={}) {
    const eventIndex=Array.isArray(events)?new Map(events.map(e=>[e.id,e])):events;
    const lookup=(index,id)=>typeof index?.get==='function'?index.get(id):index?.[id];
    const totals={...emptyRecord(),gamesWon:0,gamesLost:0,deciding:0,decidingWins:0};
    const lines=new Map(),opponents=new Map(),seasons=new Map(),competitions=new Map();
    const vsRanking={higher:[0,0],lower:[0,0],level:[0,0],unknown:[0,0]},bestWins=[];
    for(const match of rows) {
      if(match.p1!==pid&&match.p2!==pid)continue;
      const first=match.p1===pid,side=first?0:1;
      const mine=match.score[side],theirs=match.score[1-side],won=mine>theirs;
      const opponent=first?match.p2:match.p1;
      addResult(totals,won);
      totals.gamesWon+=mine;totals.gamesLost+=theirs;
      if(mine+theirs===5) {totals.deciding++;totals.decidingWins+=Number(won);}

      const scoreKey=mine+'-'+theirs,line=lines.get(scoreKey)||{mine,theirs,count:0};
      line.count++;lines.set(scoreKey,line);
      const other=opponents.get(opponent)||{id:opponent,...emptyRecord()};
      addResult(other,won);opponents.set(opponent,other);

      const season=lookup(eventIndex,match.event)?.season||'—';
      const seasonRow=seasons.get(season)||{season,eventIds:new Set(),...emptyRecord()};
      seasonRow.eventIds.add(match.event);addResult(seasonRow,won);seasons.set(season,seasonRow);
      const eventRow=competitions.get(match.event)||{id:match.event,last:match.date,...emptyRecord()};
      if(match.date>eventRow.last)eventRow.last=match.date;
      addResult(eventRow,won);competitions.set(match.event,eventRow);

      const comparison=lookup(rankComparisons,match.id);
      const comparable=typeof comparison?.snapshot==='string'&&comparison.snapshot.length>0&&
        Array.isArray(comparison.ranks)&&comparison.ranks.length===2&&
        comparison.ranks.every(rank=>Number.isInteger(rank)&&rank>0);
      let category='unknown';
      if(comparable) {
        const ownRank=comparison.ranks[side],opponentRank=comparison.ranks[1-side];
        category=opponentRank<ownRank?'higher':opponentRank>ownRank?'lower':'level';
        if(won)bestWins.push({match,opponent,rank:opponentRank,snapshot:comparison.snapshot});
      }
      vsRanking[category][won?0:1]++;
    }
    return {
      totals:finish(totals),
      scoreLines:[...lines.values()].sort((a,b)=>Number(b.mine>b.theirs)-Number(a.mine>a.theirs)||
        (a.mine>a.theirs?a.theirs-b.theirs:b.mine-a.mine)),
      opponents:[...opponents.values()].map(finish).sort((a,b)=>b.played-a.played||compare(a.id,b.id)),
      bySeason:[...seasons.values()].map(({eventIds,...record})=>({...finish(record),events:eventIds.size}))
        .sort((a,b)=>compare(b.season,a.season)),
      byEvent:[...competitions.values()].map(finish).sort((a,b)=>compare(b.last,a.last)||compare(a.id,b.id)),
      vsRanking,
      bestWins:bestWins.sort((a,b)=>a.rank-b.rank||compare(b.match.date,a.match.date)||compare(a.match.id,b.match.id)).slice(0,5),
    };
  }
  const api={summarize};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.PofepaAthleteStats=api;
})(globalThis);

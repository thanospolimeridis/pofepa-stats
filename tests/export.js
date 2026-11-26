/* Exercise the app's real CSV button handler without a browser or download.
 * Run: node tests/export.js (reads committed catalog, independent of dist/).
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');
const root = path.resolve(__dirname,'..');
const Pofepa = require('../src/core.js');
const PofepaEvidence = require('../src/evidence.js');
const PofepaAthleteStats = require('../src/athlete-stats.js');
const catalog = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root,'data/catalog.json.gz'))));
const code = fs.readFileSync(path.join(root,'src/app.js'),'utf8');
const ids = ['m-fd7e881d92c54d6f','m-71e3ade7d7899d7b','m-fbabd63d13623401'];
const corrected = ids.map(id => {
  const match = catalog.matches.find(m => m.id === id);
  assert(match?.sheet_corrections?.length,`Missing committed correction fixture ${id}`);
  return structuredClone(match);
});
const otherSeason = {...structuredClone(corrected[1]),id:'m-export-other-season',date:'2024-11-10',event:'e-export-other-season'};
delete otherSeason.sheet_corrections;
delete otherSeason.document_evidence;
// Adversarial export-only data verifies the app's quoting and formula guard.
const quoted = structuredClone(corrected[2]);
quoted.id = 'm-export-quoting';
quoted.names = ['=1+1','Name "with quotes", comma\r\nand another line'];
quoted.sheet_corrections[0].correction.reason = 'A "quoted" reason, with comma\nand another line.';
const matches = [...corrected,quoted,otherSeason];
const playerIds = new Set(matches.flatMap(m => [m.p1,m.p2]));
const eventIds = new Set(corrected.map(m => m.event));
const sourceIds = new Set(matches.flatMap(m => [m.source,...(m.document_evidence||[]).map(e => e.source),
  ...(m.sheet_corrections||[]).flatMap(e => [e.correction.source,e.match.source])]));
const payload = {
  schema:1,version:'prototype',matches,fixtures:[],snapshots:[],
  players:catalog.players.filter(p => playerIds.has(p.id)),
  clubs:catalog.clubs,
  events:[...catalog.events.filter(e => eventIds.has(e.id)),{
    id:'e-export-other-season',name:'Excluded season fixture',season:'2024-2025',kind:'singles',sources:[otherSeason.source]
  }],
  sources:catalog.sources.filter(s => sourceIds.has(s.id)),
  coverage:{ranking_periods:catalog.coverage.ranking_periods,as_of:catalog.coverage.as_of}
};
const sources = new Map(payload.sources.map(s => [s.id,s.url]));
assert(corrected.every(m => payload.events.find(e => e.id === m.event).season === '2025-2026'));

// RFC-style parser: quoted commas, doubled quotes and embedded CR/LF remain
// part of a field. Splitting lines would miss the export regression we test.
function parseCsv(text) {
  assert.equal(text.charCodeAt(0),0xfeff,'CSV must start with UTF-8 BOM');
  const rows = [];
  let row = [],cell = '',quotedField = false;
  for (let i=1;i<text.length;i++) {
    const char = text[i];
    if (char === '"') {
      if (quotedField && text[i+1] === '"') { cell += '"';i++; }
      else quotedField = !quotedField;
    } else if (!quotedField && char === ',') { row.push(cell);cell=''; }
    else if (!quotedField && char === '\r' && text[i+1] === '\n') {
      row.push(cell);rows.push(row);row=[];cell='';i++;
    } else cell += char;
  }
  assert(!quotedField,'Unclosed CSV quote');
  row.push(cell);rows.push(row);
  const header = rows.shift();
  assert(rows.every(values => values.length === header.length),'CSV rows must preserve all columns');
  return {header,rows:rows.map(values => Object.fromEntries(header.map((name,index) => [name,values[index]])))};
}

async function clickExport(route,kind,lang='en') {
  const handlers = {},errors = [],timers = [],downloads = [],blobs = new Map(),revoked = [];
  const app = {innerHTML:'',addEventListener:(type,handler) => {handlers[type]=handler;}};
  const context = {
    Pofepa,PofepaEvidence,PofepaAthleteStats,Blob,URLSearchParams,Intl,
    document:{
      documentElement:{},
      getElementById:id => id === 'site-data' ? {textContent:JSON.stringify(payload)} : app,
      querySelector:() => ({addEventListener(){}}),
      createElement:tag => {
        assert.equal(tag,'a');
        return {href:'',download:'',click(){downloads.push({url:this.href,filename:this.download});}};
      }
    },
    URL:{createObjectURL:blob => {const url='blob:test-'+blobs.size;blobs.set(url,blob);return url;},revokeObjectURL:url => revoked.push(url)},
    location:{hash:'#'+route},window:{addEventListener(){},scrollTo(){}},
    localStorage:{getItem:() => lang},
    console:{error:error => errors.push(error)},
    setTimeout:callback => {timers.push(callback);return timers.length;},clearTimeout(){},
    fetch:() => {throw new Error('Non-lazy export test must not access the network');}
  };
  vm.runInNewContext(code,context,{timeout:10000});
  await context.window.pofepaReady;
  assert.equal(errors.length,0,errors.map(String).join('\n'));
  assert(app.innerHTML.includes('<main'),'Route did not render');
  const buttonHtml = app.innerHTML.match(new RegExp('<button\\b[^>]*data-export="'+kind+'"[^>]*>'))?.[0];
  assert(buttonHtml,`Rendered ${route} lacks its ${kind} CSV button`);
  const dataset = Object.fromEntries([...buttonHtml.matchAll(/data-([a-z]+)="([^"]*)"/g)].map(m => [m[1],m[2]]));
  handlers.click({target:{closest:selector => {if(selector==='[data-rank-point]')return null;assert.equal(selector,'button');return {dataset};}}});
  await Promise.resolve();
  assert.equal(downloads.length,1,'Click must trigger exactly one captured download');
  const download = downloads[0],blob = blobs.get(download.url);
  assert.equal(download.filename,'pofepa-matches.csv');
  assert.equal(blob.type,'text/csv;charset=utf-8');
  const bytes = Buffer.from(await blob.arrayBuffer());
  assert.deepEqual([...bytes.subarray(0,3)],[0xef,0xbb,0xbf]);
  const text = bytes.toString('utf8');
  assert(text.includes('\r\n'),'CSV record separator must be CRLF');
  timers.forEach(callback => callback());
  assert.deepEqual(revoked,[download.url],'The temporary object URL must be released');
  return {...parseCsv(text),text};
}

(async () => {
  const result = await clickExport('matches?season=2025-2026','matches');
  assert.equal(result.rows.length,4,'Season export must exclude other-season result');
  for (const field of ['document_sources','correction_flags','correction_original_state','correction_reasons']) assert(result.header.includes(field));
  for (const [index,match] of corrected.entries()) {
    const row = result.rows.find(r => r.player_1 === match.names[0] && r.player_2 === match.names[1]);
    assert(row,`Missing corrected CSV match ${match.id}`);
    const entry = match.sheet_corrections[0],proof = entry.correction;
    assert.equal(row.date,match.date);
    assert.deepEqual([Number(row.games_1),Number(row.games_2)],match.score);
    assert.equal(row.correction_flags,['date','participants','score'][index]);
    assert.equal(row.source,sources.get(entry.match.source));
    assert.equal(Number(row.sheet_row),entry.match.row);
    const documents = JSON.parse(row.document_sources);
    assert(documents.some(ref => ref.source === proof.source && ref.url === sources.get(proof.source) && ref.row === proof.row && ref.sha256 === proof.sha256));
    const original = JSON.parse(row.correction_original_state)[0];
    for (const key of ['date','p1','p2','score']) assert.deepEqual(original[key],proof.before[key]);
    assert(original.sources.some(ref => ref.url === row.source && ref.row === entry.match.row));
    assert.deepEqual(JSON.parse(row.correction_reasons),[proof.reason]);
  }
  const quoteRow = result.rows.find(r => r.player_1 === "'=1+1");
  assert(quoteRow,'CSV must prefix formula-looking cells with an apostrophe');
  assert.equal(quoteRow.player_2,quoted.names[1],'Quoted multiline name must survive CSV round-trip');
  assert.deepEqual(JSON.parse(quoteRow.correction_reasons),[quoted.sheet_corrections[0].correction.reason]);
  assert(result.text.includes('""'),'CSV must double embedded quotes');

  const player = corrected[1].p1;
  const filteredPlayer = await clickExport('player/'+player+'?season=2025-2026','player','el');
  assert.equal(filteredPlayer.rows.length,1,'Athlete season export must exclude other seasons and other athletes');
  assert.equal(filteredPlayer.rows[0].player_1,corrected[1].names[0]);
  assert.equal(filteredPlayer.rows[0].correction_flags,'participants');
  const allPlayer = await clickExport('player/'+player,'player');
  assert.equal(allPlayer.rows.length,2,'Unfiltered athlete export must retain both seasons');
  const other = await clickExport('matches?season=2024-2025','matches');
  assert.equal(other.rows.length,1);
  assert.equal(other.rows[0].date,otherSeason.date);
  assert.equal(other.rows[0].correction_flags,'');
  console.log('Passed actual app CSV downloads: real corrections/provenance, BOM, quoting, formula guard and athlete/match season filters.');
})().catch(error => {console.error(error);process.exitCode=1;});

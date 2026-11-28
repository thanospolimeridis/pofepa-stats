/* Standalone provenance checks: node tests/evidence.js */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const vm = require('node:vm');
const Evidence = require('../src/evidence.js');
const {escape} = require('../src/core.js');
const root = path.resolve(__dirname,'..');
const data = require('./lib/catalog.js')();
const players = new Map(data.players.map(p => [p.id,p.name]));
const sources = new Map(data.sources.map(s => [s.id,s.url]));
const sourceUrl = id => sources.get(id) || '';
const options = {
  lang:'en', escape, playerName:id => players.get(id), datefmt:value => value,
  sourceLink:(id,row) => `<a href="${escape(sourceUrl(id))}">Source · ${escape(row)}</a>`
};

// These committed source-reviewed fixtures exercise all supported changes.
const cases = [
  ['m-fd7e881d92c54d6f','date'],
  ['m-71e3ade7d7899d7b','participants'],
  ['m-fbabd63d13623401','score']
];
for (const [id,flag] of cases) {
  const match = data.matches.find(m => m.id === id);
  assert(match?.sheet_corrections?.length, `Missing real correction fixture ${id}`);
  const original = JSON.stringify(match);
  const {correction,match:oldMatch} = match.sheet_corrections[0];
  const html = Evidence.render(match,options);
  assert(html.startsWith('<details class="correction-evidence">'));
  assert(html.includes('Original record') && html.includes('After review'));
  assert(html.includes(escape(correction.before.date)) && html.includes(escape(correction.after.date)));
  assert(html.includes(escape(oldMatch.names[0])) && html.includes(escape(match.names[0])));
  assert(html.includes(escape(correction.before.score.join('–'))));
  assert(html.includes(escape(correction.after.score.join('–'))));
  assert(html.includes(escape(correction.reason)) && html.includes(correction.sha256));
  assert(html.includes(escape(sourceUrl(oldMatch.source))));
  assert(html.includes(escape(sourceUrl(correction.source))));
  const greek = Evidence.render(match,{...options,lang:'el'});
  assert(greek.includes('Αρχική καταγραφή') && greek.includes('Μετά τον έλεγχο'));
  assert(greek.includes('Σημείωση ελέγχου · αρχικό κείμενο'));
  assert(greek.includes(escape(correction.reason)), 'English reason must remain its original text');
  const csv = Evidence.csvFields(match,{sourceUrl});
  assert.equal(csv.correction_flags,flag);
  const refs = JSON.parse(csv.document_sources);
  assert.equal(refs.filter(ref => ref.source === correction.source && ref.row === correction.row).length,1);
  assert.equal(refs[0].sha256,correction.sha256);
  assert.equal(refs[0].url,sourceUrl(correction.source));
  const state = JSON.parse(csv.correction_original_state)[0];
  for (const key of ['date','p1','p2','score']) assert.deepEqual(state[key],correction.before[key]);
  assert(state.sources.some(ref => ref.source === oldMatch.source && ref.row === oldMatch.row));
  assert.deepEqual(JSON.parse(csv.correction_reasons),[correction.reason]);
  assert.equal(JSON.stringify(match),original,'Rendering/export must not mutate the audit trail');
}

const malicious = '<img src=x onerror="alert(1)"> & \'unsafe\'';
const hostile = structuredClone(data.matches.find(m => m.id === cases[1][0]));
const entry = hostile.sheet_corrections[0];
entry.match.names = [malicious,malicious];
hostile.names = [malicious,malicious];
entry.correction.reason = '=formula,"quoted"\n' + malicious;
entry.correction.sha256 = malicious;
entry.correction.source = malicious;
entry.match.evidence = [{source:malicious,row:malicious}];
let html = Evidence.render(hostile,{lang:'el',playerName:() => malicious,datefmt:() => malicious});
assert(!html.includes('<img') && !html.includes('<script'));
assert(html.includes('&lt;img') && html.includes('&quot;') && html.includes('&#39;'));
assert(html.includes('&amp;'));
const raw = Evidence.csvFields(hostile,{sourceUrl:() => 'https://example.test/a?x="quote"&y=1'});
assert.equal(JSON.parse(raw.correction_reasons)[0],entry.correction.reason,'CSV values must retain exact raw reason text');
assert.equal(JSON.parse(raw.document_sources).at(-1).sha256,malicious);
assert.equal(JSON.parse(raw.correction_original_state)[0].names[0],malicious);
entry.correction.reason_el = 'Ελεγμένο κείμενο <ασφαλές>';
html = Evidence.render(hostile,{lang:'el'});
assert(html.includes('Ελεγμένο κείμενο &lt;ασφαλές&gt;'));
assert(!html.includes('=formula'));

// A reviewed document without a correction still belongs in CSV provenance.
const corroborated = {source:'workbook',row:9,document_evidence:[{source:'sheet',row:2,fixture:'fixture'}]};
assert.equal(Evidence.render(corroborated,options),'');
assert.deepEqual(JSON.parse(Evidence.csvFields(corroborated).document_sources),[{source:'sheet',url:'',row:2,fixture:'fixture'}]);
assert.equal(Evidence.csvFields(corroborated).correction_flags,'');
const imported = {source:'sheet',row:3,evidence:[{source:'sheet',row:3,fixture:'fixture',kind:'match_sheet'}]};
assert.equal(JSON.parse(Evidence.csvFields(imported).document_sources)[0].row,3);
assert.equal(Evidence.render({sheet_corrections:[null,{}]}),'');
assert.deepEqual(Evidence.csvFields({source:'workbook',row:5}),{
  document_sources:'',correction_flags:'',correction_original_state:'',correction_reasons:''
});
assert.equal(Evidence.render(null),'');

const browser = {};
vm.runInNewContext(fs.readFileSync(path.join(root,'src/evidence.js'),'utf8'),browser);
assert.equal(typeof browser.PofepaEvidence.render,'function');
assert.equal(typeof browser.PofepaEvidence.csvFields,'function');
console.log('Passed real correction fixtures, bilingual evidence, CSV provenance, escaping and browser export checks.');

/* Correction provenance shared by browser views and CSV exports.
 * playerName/datefmt return plain text. sourceLink is the app's trusted,
 * escaped HTML link renderer; all other dynamic display text is escaped here.
 */
(function(root) {
  'use strict';
  const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const corrections = match => (Array.isArray(match?.sheet_corrections) ? match.sheet_corrections : [])
    .filter(entry => entry?.correction?.before && entry.correction.after && (!entry.correction.action || entry.correction.action === 'correct'));
  const scoreText = score => Array.isArray(score) ? score.join('–') : '—';
  const citations = match => Array.isArray(match?.evidence) && match.evidence.length ? match.evidence : match?.source ? [{source:match.source,row:match.row}] : [];

  function render(match, options = {}) {
    const entries = corrections(match);
    if (!entries.length) return '';
    const E = options.escape || escapeText;
    const el = options.lang !== 'en';
    const L = (greek, english) => el ? greek : english;
    const playerName = options.playerName || (id => id);
    const sourceLink = options.sourceLink || ((id,row) => E(id) + (row == null ? '' : ' · ' + E(row)));
    function dateText(value) {
      try { return E(options.datefmt ? options.datefmt(value) : value || '—'); }
      catch { return E(value || '—'); }
    }
    function stateText(state, original) {
      const names = ['p1','p2'].map((key,index) => {
        const stored = original?.[key] === state[key] ? original.names?.[index] : null;
        return E(stored || playerName(state[key]) || state[key] || '—');
      });
      return `<span class="meta">${dateText(state.date)}</span><br>${names.join(' / ')}<br><strong>${E(scoreText(state.score))}</strong>`;
    }
    const body = entries.map(entry => {
      const proof = entry.correction;
      const originalLinks = [...new Map(citations(entry.match).map(ref => [JSON.stringify([ref.source,ref.row]),ref])).values()]
        .map(ref => sourceLink(ref.source,ref.row)).join(' · ');
      const translated = el && proof.reason_el;
      const reason = translated || proof.reason || '';
      return `<div class="correction-entry"><dl class="correction-comparison"><div><dt>${L('Αρχική καταγραφή','Original record')}</dt><dd>${stateText(proof.before,entry.match)}</dd></div><div><dt>${L('Μετά τον έλεγχο','After review')}</dt><dd>${stateText(proof.after,match)}</dd></div></dl>` +
        (originalLinks ? `<p>${L('Αρχική πηγή','Original source')}: ${originalLinks}</p>` : '') +
        `<p>${L('Φύλλο αγώνα','Match sheet')}: ${sourceLink(proof.source,proof.row)}</p>` +
        (reason ? `<p class="correction-reason"><strong>${translated ? L('Σημείωση ελέγχου','Review note') : L('Σημείωση ελέγχου · αρχικό κείμενο','Review note · original text')}</strong><br>${E(reason)}</p>` : '') +
        (proof.sha256 ? `<p class="meta correction-hash">SHA-256: <code>${E(proof.sha256)}</code></p>` : '') + '</div>';
    }).join('');
    return `<details class="correction-evidence"><summary>${L('Διόρθωση από φύλλο αγώνα','Match-sheet correction')}${entries.length > 1 ? ' (' + entries.length + ')' : ''}</summary>${body}</details>`;
  }

  // Values are plain strings, not CSV-quoted. Nested references use JSON so
  // URLs, punctuation, quotes and line breaks retain their exact meaning.
  function csvFields(match, {sourceUrl = () => ''} = {}) {
    const entries = corrections(match);
    const reference = ref => ({source:ref.source, url:sourceUrl(ref.source) || '',
      ...(ref.row == null ? {} : {row:ref.row}),
      ...(ref.fixture ? {fixture:ref.fixture} : {}),
      ...(ref.sha256 ? {sha256:ref.sha256} : {})});
    const documents = new Map();
    const refs = [...citations(match).filter(ref => ref.kind === 'match_sheet'),
      ...(Array.isArray(match?.document_evidence) ? match.document_evidence : []),
      ...entries.map(entry => entry.correction)];
    for (const ref of refs) {
      if (!ref?.source) continue;
      const key = JSON.stringify([ref.source,ref.row,ref.fixture]);
      documents.set(key, {...documents.get(key),...reference(ref)});
    }
    const flags = new Set();
    const originals = entries.map(entry => {
      const {before,after} = entry.correction;
      if (before.date !== after.date) flags.add('date');
      if (before.p1 !== after.p1 || before.p2 !== after.p2) flags.add('participants');
      if (JSON.stringify(before.score) !== JSON.stringify(after.score)) flags.add('score');
      return {date:before.date,p1:before.p1,p2:before.p2,score:before.score,
        ...(entry.match?.names ? {names:entry.match.names} : {}),
        sources:citations(entry.match).map(reference)};
    });
    return {
      document_sources:documents.size ? JSON.stringify([...documents.values()]) : '',
      correction_flags:[...flags].join(';'),
      correction_original_state:originals.length ? JSON.stringify(originals) : '',
      correction_reasons:entries.length ? JSON.stringify(entries.map(entry => entry.correction.reason || '')) : ''
    };
  }

  const api = {render,csvFields};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PofepaEvidence = api;
})(globalThis);

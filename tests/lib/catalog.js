/* Load the committed catalog from data/catalog/ (index + JSON Lines shards),
 * matching scripts/dataset.py load_catalog(). */
const fs = require('node:fs');
const path = require('node:path');

module.exports = function loadCatalog(directory = path.join(__dirname, '..', '..', 'data', 'catalog')) {
  const index = JSON.parse(fs.readFileSync(path.join(directory, 'index.json'), 'utf8'));
  if (index.format !== 1) throw new Error('Unsupported catalog format ' + index.format);
  const data = {};
  for (const entry of index.keys) {
    if (entry.type === 'list') {
      // Split on newlines only; JSON escapes them inside strings.
      data[entry.key] = entry.files.flatMap(name => fs.readFileSync(path.join(directory, name), 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)));
    } else if (entry.type === 'object') {
      data[entry.key] = JSON.parse(fs.readFileSync(path.join(directory, entry.file), 'utf8'));
    } else {
      data[entry.key] = entry.value;
    }
  }
  return data;
};

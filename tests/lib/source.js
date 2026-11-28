/* vm options that name a src/ file when a suite runs its text through node:vm.
 * Without a filename V8 calls the script "evalmachine.<anonymous>": stack traces
 * lose the file, and scripts/code_coverage.py cannot tell which lines of it ran. */
const path = require('node:path');
const {pathToFileURL} = require('node:url');

module.exports = (name, options = {}) =>
  ({...options, filename: pathToFileURL(path.join(__dirname, '..', '..', 'src', name)).href});

const fs = require('fs');
const BASE = 'Materi';
const tree = {};

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => !e.name.startsWith('.'))
    .sort((a, b) => a.name.localeCompare(b.name, 'en', { numeric: true }));
  tree[dir] = entries.map(e => {
    const p = dir + '/' + e.name;
    if (e.isDirectory()) { walk(p); return { name: e.name, path: p, type: 'dir', size: 0 }; }
    return { name: e.name, path: p, type: 'file', size: fs.statSync(p).size };
  });
}

if (!fs.existsSync(BASE)) { console.error('Folder Materi tidak ditemukan'); process.exit(1); }
walk(BASE);
fs.writeFileSync('materi-index.json', JSON.stringify({ version: 1, tree }, null, 1) + '\n');
console.log('Indeks dibuat:', Object.keys(tree).length, 'folder');

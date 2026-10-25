// Builds the extension into dist/: each script as one self-contained file (content scripts
// can't load modules), plus the manifest, popup, icons and fingerspelling letters.
// `--dev` also lets it talk to a SignMeUp server on localhost (left out of the store build).
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { build } from 'vite';

const out = 'dist';
rmSync(out, { recursive: true, force: true });
for (const name of ['background', 'page', 'content', 'popup']) {
  await build({
    configFile: false,
    logLevel: 'warn',
    build: {
      outDir: out,
      emptyOutDir: false,
      minify: false, // readable for store review
      lib: { entry: `src/${name}.ts`, formats: ['iife'], name: `signmeup_${name}`, fileName: () => `${name}.js` },
    },
  });
}
cpSync('public', out, { recursive: true });
mkdirSync(`${out}/letters`, { recursive: true });
cpSync('../static/img/fingerspelling', `${out}/letters`, { recursive: true });
if (process.argv.includes('--dev')) {
  const manifest = JSON.parse(readFileSync(`${out}/manifest.json`, 'utf8'));
  manifest.host_permissions.push('http://localhost/*');
  writeFileSync(`${out}/manifest.json`, JSON.stringify(manifest, null, 2));
}
console.log('Built the extension into extension/dist');

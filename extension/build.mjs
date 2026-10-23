// Builds the extension into dist/: each script as one self-contained file (content scripts
// can't load modules), plus the manifest, popup, icon and fingerspelling letters.
import { cpSync, mkdirSync, rmSync } from 'node:fs';
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
cpSync('../static/img/logo.png', `${out}/icon.png`);
console.log('Built the extension into extension/dist');

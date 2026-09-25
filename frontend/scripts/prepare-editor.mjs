import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const destination = path.join(root, 'public/vendor/smoosic');
await mkdir(destination, { recursive: true });
for (const [source, target] of [
  ['smoosic/build/smoosic.js', 'smoosic.js'],
  ['smoosic/build/jszip.js', 'jszip.js'],
  ['smoosic/release/styles', 'styles'],
  ['smoosic/LICENSE', 'LICENSE'],
  ['jquery/dist/jquery.min.js', 'jquery.min.js'],
  ['jquery/LICENSE.txt', 'jquery-LICENSE.txt'],
]) await cp(path.join(root, 'node_modules', source), path.join(destination, target), { recursive: true });
// Upstream's splash/error component uses this path relative to the frame page.
await mkdir(path.join(root, 'public/styles/images'), { recursive: true });
await cp(path.join(destination, 'styles/images/logo.png'), path.join(root, 'public/styles/images/logo.png'));
// These two upstream WOFF2 files are malformed. Use the existing local fonts.
const mediaPath = path.join(destination, 'styles/media.css');
let media = await readFile(mediaPath, 'utf8');
for (const [name, local] of [['SourceSansPro', 'sourcesans3'], ['SourceSerifPro', 'sourceserif4']]) {
  media = media.replace(new RegExp(`src: url\\('[^']*${name}-Regular\\.woff2'\\) format\\('woff2'\\),\\s*url\\('[^']*${name}-Regular\\.woff'\\) format\\('woff'\\);`), `src: url('/fonts/${local}.ttf') format('truetype');`);
}
await writeFile(mediaPath, media);

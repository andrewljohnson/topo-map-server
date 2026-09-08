import '../../../scripts/build-map-info.mjs';
import '../../../scripts/build-terrain.mjs';
import '../../../scripts/build-base-features.mjs';
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const read=name=>readFileSync(require.resolve('maplibre-gl/dist/'+name),'utf8');
const assets={maplibreJs:read('maplibre-gl-csp.js'),maplibreCss:read('maplibre-gl.css'),maplibreWorker:read('maplibre-gl-csp-worker.js')};
writeFileSync(new URL('../src/mapAssets.ts',import.meta.url),'// Generated local MapLibre assets. No CDN.\n'+Object.entries(assets).map(([name,data])=>`export const ${name} = ${JSON.stringify(data)};`).join('\n'));

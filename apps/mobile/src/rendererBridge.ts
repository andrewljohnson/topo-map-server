import {createStyle} from './style.mjs';
import type {Metadata} from './storage';

// Pass data across runtimes. Hermes function.toString() can contain [bytecode].
export function rendererInit(meta: Metadata) {
  return {type:'init', meta, style:createStyle(meta, 'topo://osm/{z}/{x}/{y}.pbf', meta.tilesets?.dem ? 'topocontour://{z}/{x}/{y}' : meta.tilesets?.contours ? 'topo://contours/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.amenities ? 'topo://amenities/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.boundaries ? 'topo://boundaries/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.waterways ? 'topo://waterways/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.landcover ? 'topo://landcover/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.trails ? 'topo://trails/{z}/{x}/{y}.pbf' : undefined, meta.tilesets?.recreation ? 'topo://recreation/{z}/{x}/{y}.pbf' : undefined)};
}
export function rendererScript(message: unknown) {
  return `(function(){try{if(window.receive)window.receive(${JSON.stringify(message)});}catch(error){window.ReactNativeWebView.postMessage(JSON.stringify({type:'fatal',message:String(error&&error.message||error),details:error&&error.stack||''}));}})();true;`;
}

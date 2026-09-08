import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
const literal=fs.readFileSync(new URL('../src/mapNotes.ts',import.meta.url),'utf8');const code=JSON.parse(literal.slice(literal.indexOf('=')+1).trim().replace(/;$/,''));
class Element{constructor(tag){this.tag=tag;this.children=[];this.style={};this.attrs={};this.value='';this.textContent='';this.offsetParent={}}appendChild(n){this.children.push(n)}replaceChildren(){this.children=[]}setAttribute(k,v){this.attrs[k]=v}addEventListener(){}remove(){}focus(){}blur(){}}
function setup(initialSaved=new Map()){const nodes=[],head=new Element('head'),container=new Element('div');container.clientWidth=430;container.clientHeight=860;let zoom=9;const saved=initialSaved,messages=[],events={};const context=vm.createContext({setTimeout,clearTimeout,window:{ReactNativeWebView:{postMessage:text=>messages.push(JSON.parse(text))}},document:{head,createElement:tag=>{const n=new Element(tag);nodes.push(n);return n}},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)}});vm.runInContext(code,context);
const map={getContainer:()=>container,getBounds:()=>({getWest:()=>179,getSouth:()=>20,getEast:()=>181,getNorth:()=>22}),getCenter:()=>({lng:180,lat:21}),getZoom:()=>zoom,getBearing:()=>35,getPitch:()=>45,unproject:([x,y])=>({lng:179+x/215,lat:22-y/430}),jumpTo:camera=>map.lastCamera=camera,on:(name,fn)=>events[name]=fn};context.installMapNotes(map,()=>({tilesets:{osm:{datasetId:'osm-v1'}}}));return{nodes,saved,messages,map,events,setZoom:z=>zoom=z,byLabel:name=>nodes.find(n=>n.attrs['aria-label']===name),byText:text=>nodes.find(n=>n.textContent===text)}}
test('copy freezes the full camera, preserves draft and recaptures only explicitly',async()=>{
 const t=setup(),open=t.byLabel('Note about this map view');open.onclick({stopPropagation(){}});const input=t.nodes.find(n=>n.tag==='textarea');input.value='A bathroom is missing\n<not HTML>';input.oninput();t.setZoom(15);
 const copy=t.byText('Copy note + bounds'),promise=copy.onclick();const request=t.messages.find(m=>m.type==='copyMapNote'),data=JSON.parse(request.text);assert.equal(data.note,input.value);assert.deepEqual(data.view.bounds,[179,20,181,22]);assert.equal(data.view.zoom,9);assert.equal(data.view.bearing,35);assert.equal(data.view.pitch,45);assert.equal(data.view.corners.length,4);assert.equal(data.view.datasets.osm,'osm-v1');t.map.__topoNoteCopyResult({id:request.id});await promise;
 t.byLabel('Close map note').onclick();open.onclick({stopPropagation(){}});assert.equal(input.value,data.note);assert.equal(JSON.parse(t.nodes.find(n=>n.tag==='pre').textContent).view.zoom,9);t.byText('Use current view').onclick();assert.equal(JSON.parse(t.nodes.find(n=>n.tag==='pre').textContent).view.zoom,15);assert.equal(JSON.parse([...t.saved.values()][0]).note,data.note);t.events.remove();
});
test('clipboard failure exposes selectable text rather than claiming success',async()=>{const t=setup();t.byLabel('Note about this map view').onclick({stopPropagation(){}});const pending=t.byText('Copy note + bounds').onclick(),request=t.messages.find(m=>m.type==='copyMapNote');t.map.__topoNoteCopyResult({id:request.id,error:'Unavailable'});await pending;assert.equal(t.nodes.find(n=>n.tag==='details').open,true);assert.ok(t.nodes.some(n=>n.textContent.includes('Copy unavailable')));t.events.remove()});

test('multiple notes persist across restart and reopen the captured camera',()=>{
 const t=setup();t.map.__topoRestoreNotes([]);t.byLabel('Note about this map view').onclick({stopPropagation(){}});
 const input=t.nodes.find(n=>n.tag==='textarea');input.value='First place';input.oninput();t.setZoom(14);t.byText('New note').onclick();input.value='Second place';input.oninput();
 const library=JSON.parse(t.saved.get('topo-map-notes-v1'));assert.equal(library.length,2);assert.equal(library[1].view.zoom,9);
 const next=setup(t.saved);next.byLabel('Note about this map view').onclick({stopPropagation(){}});next.byText('Saved notes').onclick();
 const entry=next.nodes.find(n=>n.className==='topo-note-entry'&&n.children[0].textContent==='First place');entry.onclick();
 assert.equal(next.nodes.find(n=>n.tag==='textarea').value,'First place');assert.equal(next.map.lastCamera.zoom,9);assert.equal(next.map.lastCamera.bearing,35);assert.equal(next.map.lastCamera.pitch,45);
 next.byText('Show on map').onclick();assert.equal(next.messages.at(-1).open,false);assert.equal(JSON.parse(next.saved.get('topo-map-notes-v1')).length,2);
});
test('late native restoration merges earlier notes without overwriting current edits',()=>{
 const t=setup();t.byLabel('Note about this map view').onclick({stopPropagation(){}});const input=t.nodes.find(n=>n.tag==='textarea');input.value='New while restoring';input.oninput();
 assert.equal(t.messages.filter(m=>m.type==='mapNotesLibrary').length,0);
 const older=JSON.parse(t.saved.get('topo-map-note-v1'));older.id='old';older.note='Stored on phone';t.map.__topoRestoreNotes([older]);
 const saved=t.messages.filter(m=>m.type==='mapNotesLibrary').at(-1);assert.equal(saved.notes.length,2);assert.ok(saved.notes.some(n=>n.note==='Stored on phone'));assert.ok(saved.notes.some(n=>n.note==='New while restoring'));
});

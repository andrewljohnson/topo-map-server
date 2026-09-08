/** A frozen, reproducible camera snapshot plus a local notebook; nothing is sent remotely. */
export function installMapNotes(map:any,metadata:()=>any=()=>({})){
 if(!map.getContainer)return;
 const native=()=> (window as any).ReactNativeWebView;
 const emit=(value:any)=>native()?.postMessage(JSON.stringify(value));
 const key='topo-map-note-v1';let draft:any=null,opened=false,copyId=0;
 const libraryKey='topo-map-notes-v1';let notes:any[]=[];let libraryReady=!native(),libraryDirty=false;const edited=new Set<string>();
 const pending=new Map<number,{resolve:()=>void,reject:(e:Error)=>void,timer:any}>();
 const round=(n:number)=>Number(n.toFixed(6));
 function capture(){
  const b=map.getBounds(),c=map.getCenter(),el=map.getContainer(),w=el.clientWidth,h=el.clientHeight,m=metadata();
  return {capturedAt:new Date().toISOString(),coordinateSystem:'WGS84 longitude, latitude',boundsOrder:'west, south, east, north',bounds:[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].map(round),center:[round(c.lng),round(c.lat)],zoom:round(map.getZoom()),bearing:round(map.getBearing()),pitch:round(map.getPitch()),viewport:{width:w,height:h},corners:[[0,0],[w,0],[w,h],[0,h]].map(p=>{const q=map.unproject(p);return [round(q.lng),round(q.lat)]}),cornerOrder:'top-left, top-right, bottom-right, bottom-left',datasets:Object.fromEntries(Object.entries(m.tilesets||{}).map(([name,s]:[string,any])=>[name,s.datasetId]))};
 }
 const valid=(d:any)=>d&&typeof d.note==='string'&&d.note.length<=10000&&d.view&&Array.isArray(d.view.bounds)&&d.view.bounds.length===4&&d.view.bounds.every(Number.isFinite)&&Array.isArray(d.view.center)&&d.view.center.length===2&&d.view.center.every(Number.isFinite)&&Number.isFinite(d.view.zoom)&&Number.isFinite(d.view.bearing)&&Number.isFinite(d.view.pitch);
 const normalize=(d:any)=>({...d,id:typeof d.id==='string'?d.id:'note-'+d.view.capturedAt,updatedAt:d.updatedAt||d.view.capturedAt});
 const merge=(items:any[])=>{const merged=new Map(notes.map(n=>[n.id,n]));for(const item of items){if(!valid(item)||!item.note.trim())continue;const n=normalize(item),old=merged.get(n.id);if(edited.has(n.id))continue;if(!old||n.updatedAt>old.updatedAt)merged.set(n.id,n)}notes=[...merged.values()].sort((a,b)=>String(b.updatedAt).localeCompare(String(a.updatedAt)))};
 const save=()=>{if(draft){draft=normalize(draft);edited.add(draft.id);draft.updatedAt=new Date().toISOString();notes=notes.filter(n=>n.id!==draft.id);if(draft.note.trim())notes.unshift({...draft})}try{localStorage.setItem(key,JSON.stringify(draft));localStorage.setItem(libraryKey,JSON.stringify(notes))}catch{if(!native())status.textContent='Could not save notes on this device. Copy your note to keep it.'}if(native()){libraryDirty=true;if(libraryReady){emit({type:'mapNoteDraft',draft});emit({type:'mapNotesLibrary',notes})}}};
 try{const stored=JSON.parse(localStorage.getItem(libraryKey)||'[]');if(Array.isArray(stored))merge(stored);const old=JSON.parse(localStorage.getItem(key)||'null');if(valid(old)){draft=normalize(old);merge([draft])}}catch{}
 const style=document.createElement('style');style.textContent=`
 .topo-note-control{position:absolute;z-index:5;right:calc(var(--safe-right,env(safe-area-inset-right,0px)) + 16px);top:calc(var(--safe-top,env(safe-area-inset-top,0px)) + 16px);width:44px;height:44px;border:0;border-radius:12px;background:#fafbf5;color:#287259;box-shadow:0 2px 10px #14304425;display:grid;place-items:center;cursor:pointer}
 .topo-note-control svg{width:23px;height:23px}
 .topo-note-overlay{position:absolute;inset:0;z-index:40;background:#18342638;display:flex;align-items:flex-end;justify-content:center;font:14px/1.4 Arial,sans-serif;color:#234234;box-sizing:border-box;padding-left:var(--safe-left,env(safe-area-inset-left,0px));padding-right:var(--safe-right,env(safe-area-inset-right,0px))}
 .topo-note-overlay[hidden]{display:none}
 .topo-note-sheet{box-sizing:border-box;width:100%;max-width:540px;max-height:calc(100% - var(--safe-top,env(safe-area-inset-top,0px)) - 12px);overflow:auto;background:#fafbf5;border-radius:20px 20px 0 0;padding:12px 20px calc(16px + var(--safe-bottom,env(safe-area-inset-bottom,0px)));overscroll-behavior:contain}
 .topo-note-sheet header{display:flex;justify-content:space-between;align-items:center}.topo-note-sheet h2{font-size:18px;margin:0}
 .topo-note-sheet button{font:inherit;min-height:44px;border:0;border-radius:10px;padding:8px 12px;cursor:pointer;background:#e4ece0;color:#234234}
 .topo-note-sheet .topo-note-close{font-size:26px;background:transparent;width:44px;padding:0}
 .topo-note-sheet label{display:block;margin:8px 0}.topo-note-sheet textarea{box-sizing:border-box;width:100%;min-height:100px;height:22vh;max-height:180px;resize:vertical;padding:12px;border:1px solid #bccdb7;border-radius:10px;font:16px/1.5 Arial,sans-serif;background:#fff;color:#234234}
 .topo-note-view{font-size:12px;color:#5a705f;overflow-wrap:anywhere;margin:10px 0}.topo-note-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
 .topo-note-sheet .topo-note-copy{background:#287259;color:white;flex:1}.topo-note-sheet pre{white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;font:12px/1.4 monospace;max-height:160px;overflow:auto}
 .topo-note-tabs{display:flex;gap:8px;margin:12px 0}.topo-note-tabs button{flex:1}.topo-note-list{display:flex;flex-direction:column;gap:10px;margin:12px 0;max-height:48vh;overflow:auto}.topo-note-list[hidden],.topo-note-editor[hidden]{display:none}
 .topo-note-entry{text-align:left;align-items:stretch;width:100%;display:flex;flex-direction:column;gap:5px}.topo-note-entry strong{white-space:pre-wrap;overflow-wrap:anywhere;font-weight:500;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.topo-note-entry small{font-size:12px;color:#5a705f}
 .topo-note-status{font-size:12px;margin:8px 0 0;min-height:17px}.topo-note-sheet :focus-visible,.topo-note-control:focus-visible{outline:2px solid #287259;outline-offset:2px}
 `;document.head.appendChild(style);
 const el=<K extends keyof HTMLElementTagNameMap>(tag:K)=>document.createElement(tag);
 const append=(parent:Node,...children:Node[])=>{for(const child of children)parent.appendChild(child)};
 const button=el('button') as HTMLButtonElement;button.type='button';button.className='topo-note-control';button.setAttribute('aria-label','Note about this map view');button.title='Note about this map view';button.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M13 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-8M9 15l1-4L19 2l3 3-9 9-4 1Z"/></svg>';
 const overlay=el('div');overlay.className='topo-note-overlay';overlay.hidden=true;
 const sheet=el('section');sheet.className='topo-note-sheet';sheet.setAttribute('role','dialog');sheet.setAttribute('aria-modal','true');sheet.setAttribute('aria-label','Map view note');
 const header=el('header'),title=el('h2'),close=el('button') as HTMLButtonElement;title.textContent='Map view note';close.type='button';close.className='topo-note-close';close.textContent='×';close.setAttribute('aria-label','Close map note');append(header,title,close);
 const label=el('label');label.textContent='What should I look at?';const input=el('textarea') as HTMLTextAreaElement;input.id='topo-map-note-text';label.htmlFor=input.id;input.maxLength=10000;input.placeholder='Describe the label, symbol, missing detail, or other issue…';
 const view=el('p');view.className='topo-note-view';
 const actions=el('div');actions.className='topo-note-actions';const recapture=el('button') as HTMLButtonElement;recapture.type='button';recapture.textContent='Use current view';const copy=el('button') as HTMLButtonElement;copy.type='button';copy.className='topo-note-copy';copy.textContent='Copy note + bounds';append(actions,recapture,copy);
 const status=el('p');status.className='topo-note-status';status.setAttribute('role','status');
 const details=el('details'),summary=el('summary'),preview=el('pre');summary.textContent='View details / select text';preview.tabIndex=0;append(details,summary,preview);const tabs=el('div');tabs.className='topo-note-tabs';const newNote=el('button'),savedNotes=el('button');newNote.type=savedNotes.type='button';newNote.textContent='New note';savedNotes.textContent='Saved notes';append(tabs,newNote,savedNotes);
 const editor=el('div');editor.className='topo-note-editor';const list=el('div');list.className='topo-note-list';list.hidden=true;list.setAttribute('aria-label','Saved map notes');
 const showMap=el('button');showMap.type='button';showMap.textContent='Show on map';append(actions,showMap);
 append(editor,label,input,view,actions,details);append(sheet,header,tabs,list,editor,status);append(overlay,sheet);append(map.getContainer(),button,overlay);
 for(const name of ['mousedown','touchstart','pointerdown','wheel'])overlay.addEventListener(name,e=>e.stopPropagation());
 const viewport=window.visualViewport;const fit=()=>{if(viewport){overlay.style.height=viewport.height+'px';overlay.style.top=viewport.offsetTop+'px';overlay.style.bottom='auto'}};viewport?.addEventListener('resize',fit);viewport?.addEventListener('scroll',fit);fit();
 const text=()=>JSON.stringify({note:draft.note,view:draft.view},null,2);
 function refresh(){if(!draft)return;input.value=draft.note;const v=draft.view;view.textContent='Captured view · zoom '+Number(v.zoom).toFixed(2)+' · '+v.bounds.join(', ')+' (W, S, E, N). View stays fixed while you write.';preview.textContent=text()}
 function centerNote(){if(draft&&valid(draft))map.jumpTo({center:draft.view.center,zoom:draft.view.zoom,bearing:draft.view.bearing,pitch:draft.view.pitch})}
 function showEditor(){list.hidden=true;editor.hidden=false;title.textContent='Map view note';refresh()}
 function showList(){editor.hidden=true;list.hidden=false;title.textContent='Saved map notes';list.replaceChildren();if(!notes.length){const empty=el('p');empty.textContent='Your notes will appear here as you write them.';append(list,empty)}for(const note of notes){const entry=el('button'),text=el('strong'),date=el('small');entry.type='button';entry.className='topo-note-entry';text.textContent=note.note;date.textContent=new Date(note.view.capturedAt).toLocaleString()+' · zoom '+Number(note.view.zoom).toFixed(2);append(entry,text,date);entry.onclick=()=>{draft={...note};centerNote();showEditor();save();status.textContent='Note opened. Map returned to its saved view.'};append(list,entry)}status.textContent=notes.length+' saved '+(notes.length===1?'note':'notes')+' on this device.'}
 newNote.onclick=()=>{draft={id:'note-'+Date.now()+'-'+Math.random().toString(36).slice(2,8),note:'',view:capture()};save();showEditor();status.textContent='New note — saved automatically as you write.';input.focus()};
 savedNotes.onclick=showList;showMap.onclick=()=>{centerNote();toggle(false)};
 function toggle(show:boolean){opened=show;overlay.hidden=!show;button.setAttribute('aria-expanded',String(show));if(show){if(!draft){draft={note:'',view:capture()};save()}showEditor();status.textContent='Saved automatically on this device. Open Saved notes to return later.';close.focus()}else{input.blur();button.focus()}emit({type:'noteDrawer',open:show})}
 button.onclick=e=>{e.stopPropagation();toggle(true)};close.onclick=()=>toggle(false);overlay.onclick=e=>{e.stopPropagation();if(e.target===overlay)toggle(false)};
 sheet.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();toggle(false)}if(e.key==='Tab'){const nodes=[...sheet.querySelectorAll<HTMLElement>('button,textarea,summary,pre')].filter(n=>n.offsetParent!==null);const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}});
 input.oninput=()=>{draft.note=input.value;preview.textContent=text();status.textContent='Draft saved on this device.';save()};
 recapture.onclick=()=>{draft.view=capture();refresh();save();status.textContent='Bounds updated to the current map view.'};
 map.__topoRestoreNote=(value:any)=>{if(valid(value)){merge([value]);if(!draft){draft=normalize(value);if(opened)refresh()}}};
 map.__topoRestoreNotes=(items:any)=>{if(Array.isArray(items)){merge(items);libraryReady=true;if(libraryDirty){emit({type:'mapNoteDraft',draft});emit({type:'mapNotesLibrary',notes})}if(opened&&!list.hidden)showList()}};
 map.__topoNotesStorageError=()=>{status.textContent='Could not save notes on this device. Copy your note to keep it.'};
 map.__topoNoteCopyResult=(m:any)=>{const p=pending.get(m.id);if(!p)return;clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(m.error)):p.resolve()};
 copy.onclick=async()=>{copy.disabled=true;try{const content=text();if(native()){await new Promise<void>((resolve,reject)=>{const id=++copyId;const timer=setTimeout(()=>{pending.delete(id);reject(Error('Copy timed out'))},10000);pending.set(id,{resolve,reject,timer});emit({type:'copyMapNote',id,text:content})})}else{await navigator.clipboard.writeText(content)}status.textContent='Copied note and map view. Paste it into your message.'}catch{details.open=true;status.textContent='Copy unavailable. Select the text below and copy it.'}finally{copy.disabled=false}};
 map.on('remove',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Map closed'))}pending.clear();viewport?.removeEventListener('resize',fit);viewport?.removeEventListener('scroll',fit);button.remove();overlay.remove();style.remove()});
}

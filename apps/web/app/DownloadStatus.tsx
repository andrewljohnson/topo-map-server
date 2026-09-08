"use client";
import {useEffect,useRef,useState} from 'react';
import {Map} from 'lucide-react';
export function DownloadStatus(){
 const [open,setOpen]=useState(false);
 const root=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(!open)return;const dismiss=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false)};document.addEventListener('pointerdown',dismiss);return()=>document.removeEventListener('pointerdown',dismiss)},[open]);
 return <div ref={root} className="downloads" onKeyDown={e=>{if(e.key==='Escape')setOpen(false)}}>
  <button className="downloads-toggle" aria-label="Map downloads" aria-expanded={open} aria-controls="download-details" onClick={()=>setOpen(!open)}><Map size={24}/></button>
  {open&&<section id="download-details" className="download-details" aria-label="Map downloads"><p>Use the mobile app to download maps to your phone for offline use.</p></section>}
 </div>
}

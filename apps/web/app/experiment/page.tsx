'use client';
import {useEffect,useRef,useState} from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';
import {createStyle} from '../vectorStyle';
import {installDeviceTerrain} from '../terrainRuntime';
import {terrainWorkerSource} from '../terrainWorkerSource';
import {installShieldImages} from '../shieldImages';
import {installPoiImages} from '../poiImages';
import {installAmenityImages} from '../amenityImages';
import {installTrailBadges} from '../trailBadges';
import {installPoiMatching} from '../poiMatching';
import {installFeatureInfo} from '../featureInfo';
import {installMapInfo} from '../mapInfo';
import {combineStyle,logicalMap} from './combined';
export default function TahoeExperiment(){
 const root=useRef<HTMLDivElement>(null),mapRef=useRef<any>(null);
 const [region,setRegion]=useState('tahoe');
 const [status,setStatus]=useState('Loading sample…'),[error,setError]=useState(''),[metrics,setMetrics]=useState('');
 useEffect(()=>{let map:any,terrain:any,protocols:any,disposed=false;const controller=new AbortController();
 (async()=>{try{
  const selected=new URLSearchParams(location.search).get('region')||'tahoe';
  const allowed=['tahoe','tahoe-10x','sierra-100x','sf-10x','smokies-10x','desert-10x','western-1000x'];
  const sample=allowed.includes(selected)?selected:'tahoe';setRegion(sample);
  const api=`${location.protocol}//${location.hostname}:3012`+(sample==='tahoe'?'':'/regions/'+sample);
  const response=await fetch(api+'/metadata',{signal:controller.signal});if(!response.ok)throw Error('Sample build is not ready yet.');const meta:any=await response.json();
  const gl=await import('maplibre-gl');if(disposed)return;protocols=gl;
  const vector=api+meta.tileUrl;
  const style=createStyle(meta,vector,'topocontour://{z}/{x}/{y}',vector,vector,vector,vector,vector,vector);
  const demFiles=new Set<string>(),baseFiles=new Set<string>();let baseBytes=0,demBytes=0;
  terrain=installDeviceTerrain(gl,style,meta.tilesets.dem,async(key,c)=>{const r=await fetch(api+'/dem/'+key+'.png',{signal:c.signal});if(!r.ok)throw Error('Missing DEM '+key);const data=await r.arrayBuffer();demFiles.add(key);demBytes+=data.byteLength;return data;},terrainWorkerSource);

  gl.addProtocol('tahoobase',async(p,c)=>{const key=p.url.split('://')[1];const r=await fetch(api+'/base/'+key+'.pbf',{signal:c.signal});if(!r.ok)throw Error('Missing sample tile');const data=await r.arrayBuffer();baseFiles.add(key);baseBytes+=data.byteLength;return {data};});
  style.sources.osm.tiles=['tahoobase://{z}/{x}/{y}'];
  map=new gl.Map({container:root.current!,style,center:meta.center,zoom:meta.initialZoom,minZoom:meta.minZoom??12,maxZoom:18,maxBounds:meta.bounds,attributionControl:false});mapRef.current=map;
  (window as any).__topoMap=map;(window as any).__tahoeSample={metadata:meta,stats:()=>({baseFiles:baseFiles.size,demFiles:demFiles.size,baseBytes,demBytes,terrain:terrain?.stats})};
  terrain?.attach(map);installShieldImages(map);installPoiImages(map);installAmenityImages(map);installTrailBadges(map);
  const logical=logicalMap(map);installPoiMatching(logical);installFeatureInfo(logical,gl.Popup);installMapInfo(logical);
  map.addControl(new gl.NavigationControl({showCompass:true,visualizePitch:true}),'bottom-left');
  map.addControl(new gl.ScaleControl({unit:'imperial'}),'bottom-left');
  let first=true;map.on('idle',()=>{setMetrics(`Zoom ${map.getZoom().toFixed(1)} · ${baseFiles.size} base / ${demFiles.size} DEM files · ${((baseBytes+demBytes)/1e6).toFixed(1)} MB decoded transfer`);if(first){first=false;setStatus('Ready');}});
  map.on('error',(e:any)=>{console.info('Tahoe sample',e.error?.message);});
 }catch(e){if(!disposed)setError(String(e));}})();
 return ()=>{disposed=true;controller.abort();map?.remove();terrain?.dispose();protocols?.removeProtocol('tahoobase');};
 },[]);
 const title=region.startsWith('sf')?'San Francisco':region.startsWith('smokies')?'Smokies':region.startsWith('desert')?'Mojave':region.startsWith('western')?'Western scale sample':'Tahoe';
 const presets=region.startsWith('sf')?[['San Francisco',-122.4194,37.7749],['Golden Gate',-122.4783,37.8199],['Marin',-122.521,37.857]]:region==='tahoe'||region==='tahoe-10x'||region==='sierra-100x'?[['Fallen Leaf',-120.061,38.907],['Campground',-120.050311,38.92626],['South shore',-120.005,38.95]]:[];
 return <main style={{position:'fixed',inset:0}}><div ref={root} style={{position:'absolute',inset:0}}/>
 <aside style={{position:'absolute',left:'max(14px,env(safe-area-inset-left))',top:'max(14px,env(safe-area-inset-top))',background:'#fffffff2',padding:'12px 16px',borderRadius:12,boxShadow:'0 2px 14px #1233',maxWidth:310,color:'#234234',fontFamily:'Arial,sans-serif'}}>
 <strong style={{fontSize:16}}>{title} · zoom-12 experiment</strong><div style={{fontSize:13,marginTop:5}}>{error||status}</div>
 <nav style={{display:'flex',gap:12,fontSize:13,marginTop:8}}><a href='/experiment'>Fallen Leaf</a><a href='/experiment?region=tahoe-10x'>Lake Tahoe</a><a href='/experiment?region=sf-10x'>San Francisco</a></nav>
 <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>{presets.map(([label,lng,lat])=><button key={label} onClick={()=>mapRef.current?.flyTo({center:[lng,lat],zoom:14})} style={{border:'1px solid #a5b9ae',borderRadius:7,padding:'7px 10px',background:'white',fontSize:14}}>{label}</button>)}</div>
 <div style={{display:'flex',gap:8,marginTop:8}}>{[12,14,16,18].map(z=><button key={z} onClick={()=>mapRef.current?.zoomTo(z)} style={{border:'1px solid #a5b9ae',borderRadius:5,background:'white',padding:5}}>Zoom {z}</button>)}</div><small style={{display:'block',marginTop:8}}>{metrics}</small></aside></main>;
}

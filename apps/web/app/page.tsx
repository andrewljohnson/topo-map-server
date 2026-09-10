"use client";
import {installMapDiagnostics,profileMapGraphics} from './mapDiagnostics';
import {installLakeOrientation} from './lakeOrientation';
import {logicalMap} from './combinedMap';
import {installDeviceTerrain} from './terrainRuntime';
import {terrainWorkerSource} from './terrainWorkerSource';
import { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import 'maplibre-gl/dist/maplibre-gl.css';
import {DownloadStatus} from './DownloadStatus';
import {parseAreaData,AreaData} from './areas';
import {createStyle} from './vectorStyle';
import {tileTemplateUrl} from './tileUrls';
import {installShieldImages} from './shieldImages';
import {installPoiImages} from './poiImages';
import {installMapNotes} from './mapNotes';
import {installAmenityImages} from './amenityImages';
import {installTrailBadges} from './trailBadges';
import {installPoiMatching} from './poiMatching';
import {installFeatureInfo} from './featureInfo';
import {installMapInfo} from './mapInfo';

type Metadata = { combined?:boolean;overviewMaxZoom?:number; publicAccess?:boolean; name: string; bounds: [number,number,number,number]; center: [number,number]; initialZoom?:number; minZoom: number; maxZoom: number; tileUrl: string; tilesets?: {dem?: {tileUrl:string;bounds?:number[];attribution?:string};contours?: {tileUrl:string};amenities?: {tileUrl:string};boundaries?: {tileUrl:string};waterways?: {tileUrl:string};landcover?:{tileUrl:string};trails?:{tileUrl:string};recreation?:{tileUrl:string}} };
export default function Home() {
  const root = useRef<HTMLDivElement>(null);
  const map = useRef<import('maplibre-gl').Map | null>(null);
  const areas = useRef<AreaData|null>(null);
  const updateAreas=(data:AreaData)=>{areas.current=data;(map.current?.getSource('areas') as import('maplibre-gl').GeoJSONSource|undefined)?.setData(data)};
  const [error, setError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [publicAccess,setPublicAccess]=useState<boolean|null>(null);
  const [retry, setRetry] = useState(0);
  const [accessOpen,setAccessOpen]=useState(false),[accessKey,setAccessKey]=useState('');

  useEffect(() => {
    let disposed = false;
    let resizeObserver: ResizeObserver | undefined;
    const controller = new AbortController();
    const diagnosticsStart=performance.now(),bootstrap:any[]=[];
    const stamp=(stage:string)=>bootstrap.push({stage,ms:Math.round(performance.now()-diagnosticsStart)});
    (async () => {
      try {
        setError(''); setLoaded(false);
        const api = import.meta.env.VITE_TILE_API_URL || (import.meta.env.PROD ? location.origin : `${location.protocol}//${location.hostname}:3001`);
        const token=sessionStorage.getItem('topo-access-key')||'';
        const headers:Record<string,string>=token?{Authorization:'Bearer '+token}:{};
        const release=new URLSearchParams(location.search).get('release');
        const metadataPath=release&&/^[a-z0-9-]{1,80}$/.test(release)?`/releases/${release}/metadata`:'/metadata';
        const response = await fetch(`${api}${metadataPath}`, {headers,signal: controller.signal});
        if(response.status===401){setPublicAccess(false);setAccessOpen(true);throw new Error('Enter your map access key to connect.');}
        if(response.status===429)throw new Error('Map allowance reached. Check the server usage limits.');

        if (!response.ok) throw new Error('Tile service is unavailable.');
        const info: Metadata = await response.json();stamp('metadata');
        setPublicAccess(info.publicAccess===true);
        const L = await import('maplibre-gl');stamp('map-library');
        if (disposed || !root.current) return;
        const mapStyle=createStyle(info, tileTemplateUrl(info.tileUrl,api), info.tilesets?.dem ? 'topocontour://{z}/{x}/{y}' : info.tilesets?.contours ? tileTemplateUrl(info.tilesets.contours.tileUrl,api) : undefined, info.tilesets?.amenities ? tileTemplateUrl(info.tilesets.amenities.tileUrl,api) : undefined, info.tilesets?.boundaries ? tileTemplateUrl(info.tilesets.boundaries.tileUrl,api) : undefined, info.tilesets?.waterways ? tileTemplateUrl(info.tilesets.waterways.tileUrl,api) : undefined, info.tilesets?.landcover ? tileTemplateUrl(info.tilesets.landcover.tileUrl,api) : undefined, info.tilesets?.trails ? tileTemplateUrl(info.tilesets.trails.tileUrl,api) : undefined, info.tilesets?.recreation ? tileTemplateUrl(info.tilesets.recreation.tileUrl,api) : undefined);
        stamp('style-created');
        const terrain=installDeviceTerrain(L,mapStyle,info.tilesets?.dem,async(key,c)=>{const [z,x,y]=key.split('/');const template=tileTemplateUrl(info.tilesets!.dem!.tileUrl,api);const response=await fetch(template.replace('{z}',z).replace('{x}',x).replace('{y}',y),{headers,signal:c.signal});if(!response.ok)throw Error('DEM '+response.status);return response.arrayBuffer()},terrainWorkerSource);
        stamp('terrain-installed');
        const diagnostics=import.meta.env.VITE_MAP_DIAGNOSTICS==='1'&&(['diagnostics','proof'].some(key=>new URLSearchParams(location.search).has(key)));
        const graphics=diagnostics?profileMapGraphics():null;
        const instance = new L.Map({collectResourceTiming:diagnostics,hash:true,container:root.current, transformRequest:(url)=>({url,headers:url.startsWith(api+'/')?headers:{}}), style:mapStyle, center:info.center,zoom:info.initialZoom??3,minZoom:info.minZoom,maxZoom:18,renderWorldCopies:true,attributionControl:false});
        map.current = instance;stamp('map-constructor');
        if(diagnostics)installMapDiagnostics(instance,diagnosticsStart,bootstrap,graphics);
        if(import.meta.env.DEV)(window as any).__topoMap=instance;
        if(terrain){terrain.attach(instance);(instance as any).__topoTerrainStats=terrain.stats;instance.on('remove',terrain.dispose);}
        // Handle stylesheet load order and container changes without relying on a window resize.
        resizeObserver = new ResizeObserver(() => instance.resize());
        resizeObserver.observe(root.current);
        instance.on('load',()=>{if(areas.current)updateAreas(areas.current);});
        if(!info.combined)fetch(`${api}/areas.geojson`,{headers,signal:controller.signal}).then(r=>{if(!r.ok)throw Error('Areas unavailable');return r.json()}).then(data=>{if(!disposed){areas.current=parseAreaData(data);if(instance.isStyleLoaded())updateAreas(areas.current)}}).catch(()=>{});
        installShieldImages(instance);stamp('shield-icons');
        installPoiImages(instance);stamp('poi-icons');
        installAmenityImages(instance);stamp('amenity-icons');
        const logical=info.combined?logicalMap(instance):instance;
        installMapInfo(logical);stamp('legend');
        installLakeOrientation(instance);
        installMapNotes(instance,()=>info);stamp('notes');
        installTrailBadges(instance);stamp('route-badges');
        installPoiMatching(logical);stamp('poi-matching');
        installFeatureInfo(logical,L.Popup);stamp('feature-info');
        instance.addControl(new L.NavigationControl({showCompass:true,visualizePitch:true}), 'bottom-left');
        const geolocate = new L.GeolocateControl({
          positionOptions:{enableHighAccuracy:true,maximumAge:30000,timeout:15000},
          trackUserLocation:true,showUserLocation:true,showAccuracyCircle:true,
          fitBoundsOptions:{maxZoom:16}
        });
        // No automatic trigger: browser permission and centering follow a user click.
        instance.addControl(geolocate, 'bottom-left');
        geolocate.on('geolocate',()=>{if(!disposed)setLocationError('');});
        geolocate.on('error',(event)=>{
          if(disposed)return;
          setLocationError(event.code===1
            ? 'Location access was denied. Allow location for this site, then tap locate again.'
            : 'Your location is unavailable. Check location services, then tap locate again.');
        });
        instance.addControl(new L.ScaleControl({unit:'metric'}), 'bottom-left');
        instance.on('sourcedata',(event)=>{if(!disposed && event.sourceId==='osm' && event.isSourceLoaded){setLoaded(true);}});
        instance.on('error',(event)=>{
          // Known publication holes are intentional outside the detailed region.
          // The broad base remains browsable; this is not a failed map session.
          if(String(event.error?.message||'').includes('DEM outside published coverage'))return;
          if(!disposed)setError('Some map data could not load. Check the tile service and retry.');
        });
      } catch(e) {if(!disposed)setError(e instanceof Error ? e.message : 'Unable to load the map.');}
    })();
    return () => {disposed=true;controller.abort();resizeObserver?.disconnect();map.current?.remove();map.current=null;};
  },[retry]);
  return <main className="explorer">
    <div ref={root} className="map" aria-label="Interactive OpenStreetMap map" />
    <div className="map-tools"><DownloadStatus/>{publicAccess===false&&<button className="downloads-toggle" aria-label="Map access key" onClick={()=>setAccessOpen(true)}>⚿</button>}</div>
    {accessOpen&&<div style={{position:'absolute',inset:0,background:'#17392a55',display:'grid',placeItems:'center',zIndex:20}}><form aria-label="Map access" onSubmit={e=>{e.preventDefault();sessionStorage.setItem('topo-access-key',accessKey.trim());setAccessKey('');setAccessOpen(false);setRetry(x=>x+1)}} style={{background:'#fafbf5',padding:24,borderRadius:16,width:'min(90vw,360px)',boxSizing:'border-box'}}><h2>Map access</h2><p>Paste your private map key. It stays in this browser tab for this session.</p><input aria-label="Map access key" type="password" autoComplete="off" value={accessKey} onChange={e=>setAccessKey(e.target.value)} required style={{width:'100%',boxSizing:'border-box',padding:12}}/><div style={{display:'flex',gap:12,marginTop:16}}><button type="submit">Connect</button><button type="button" onClick={()=>setAccessOpen(false)}>Close</button><button type="button" onClick={()=>{sessionStorage.removeItem('topo-access-key');setAccessOpen(false);setRetry(x=>x+1)}}>Sign out</button></div></form></div>}
    {error || locationError ? <div className="notice" role="alert"><span>{error || locationError}</span>{error ? <button onClick={()=>setRetry(x=>x+1)}><RefreshCw size={16}/>Retry</button> : <button onClick={()=>setLocationError('')}>Dismiss</button>}</div> : !loaded ? <div className="notice" role="status">Loading map tiles…</div> : null}
  </main>
}

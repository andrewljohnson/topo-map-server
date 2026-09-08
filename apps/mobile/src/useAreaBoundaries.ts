import {useEffect,useRef} from 'react';
import * as FS from 'expo-file-system/legacy';
import {parseAreaData,AreaData} from './areas';
// Boundary geometry remains map content, independent of area browsing controls.
export function useAreaBoundaries(api:string,onData:(data:AreaData)=>void){
 const callback=useRef(onData);callback.current=onData;
 useEffect(()=>{let stopped=false;const controller=new AbortController();const cacheFile=FS.documentDirectory+'area-boundaries.json';
  const timeout=setTimeout(()=>controller.abort(),15000);
  (async()=>{try{const cached=JSON.parse(await FS.readAsStringAsync(cacheFile));if(cached.api===api&&!stopped)callback.current(parseAreaData(cached.data))}catch{}
   try{const r=await fetch(api+'/areas.geojson',{signal:controller.signal});if(!r.ok)throw Error('Boundary data unavailable');const data=parseAreaData(await r.json());if(stopped)return;callback.current(data);await FS.writeAsStringAsync(cacheFile,JSON.stringify({api,data}))}catch{}finally{clearTimeout(timeout)}
  })();return()=>{stopped=true;clearTimeout(timeout);controller.abort()};
 },[api]);
}

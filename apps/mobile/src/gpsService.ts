/** One recorder is shared by the UI and headless background-location task. */
import {File,Paths} from 'expo-file-system';
import type {LocationObject} from 'expo-location';
import {GPSRecording} from './gpsRecording';
let recording:GPSRecording|null=null,initializing:Promise<void>|null=null;
const listeners=new Set<()=>void>();
export function subscribeGPS(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener)}}
export function currentRecording(){if(!recording){const file=new File(Paths.document,'gps-track.jsonl');recording=new GPSRecording({read:async()=>file.exists?file.text():'',append:text=>{if(!file.exists)file.create();file.write('\n'+text,{append:true})},reset:()=>{if(!file.exists)file.create();file.write('')}},()=>listeners.forEach(listener=>listener()))}return recording}
export async function initializeRecording(){const r=currentRecording();if(!initializing)initializing=r.recalculate();await initializing;await r.whenReady();return r}
export function recordLocation(p:LocationObject){const c=p.coords,finite=(v:number|null)=>Number.isFinite(v)?v:null;currentRecording().add({x:c.longitude,y:c.latitude,z:finite(c.altitude),time:p.timestamp,accuracy:finite(c.accuracy),altitudeAccuracy:finite(c.altitudeAccuracy),speed:finite(c.speed),heading:finite(c.heading),mocked:p.mocked===true})}

import * as TaskManager from 'expo-task-manager';
import * as Location from 'expo-location';
import Constants from 'expo-constants';
import {currentRecording,initializeRecording,recordLocation} from './gpsService';
export const BACKGROUND_GPS_TASK='topo-map-background-gps-v1';
let enabled:boolean|null=null;let message='';const listeners=new Set<()=>void>();
const notify=()=>listeners.forEach(listener=>listener());
export const backgroundRecordingEnabled=()=>enabled===true;
export const backgroundRecordingMessage=()=>message;
export function subscribeBackground(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener)}}
const explicitlyDisabled=()=>enabled===false;
const expoGo=()=>Constants.executionEnvironment==='storeClient';
export async function refreshBackgroundRecording(){try{enabled=!expoGo()&&await TaskManager.isAvailableAsync()&&await Location.hasStartedLocationUpdatesAsync(BACKGROUND_GPS_TASK);message=expoGo()?'Background GPS requires a development build; Expo Go supports foreground recording only.':''}catch{enabled=false;message='Unable to check background recording.'}notify()}
// Must be defined at module scope, before React mounts, for headless launches.
TaskManager.defineTask<{locations:Location.LocationObject[]}>(BACKGROUND_GPS_TASK,async({data,error})=>{
 if(error){message='Background GPS: '+error.message;notify();return}
 if(explicitlyDisabled()||!data?.locations?.length)return;
 if(!await Location.hasStartedLocationUpdatesAsync(BACKGROUND_GPS_TASK))return;
 const recording=await initializeRecording();if(explicitlyDisabled())return;enabled=true;message='';
 for(const point of [...data.locations].sort((a,b)=>a.timestamp-b.timestamp))recordLocation(point);
 // Flush even a short OS-delivered batch before the headless task is suspended.
 recording.flush();notify();
});
export async function setBackgroundRecording(value:boolean){
 if(!value){enabled=false;notify();try{if(await Location.hasStartedLocationUpdatesAsync(BACKGROUND_GPS_TASK))await Location.stopLocationUpdatesAsync(BACKGROUND_GPS_TASK);currentRecording().breakSegment();message=''}catch(e){await refreshBackgroundRecording();message='Could not stop background GPS. Try again.';throw e}finally{notify()}return}
 try{
  if(expoGo()||!await TaskManager.isAvailableAsync())throw Error('Background GPS requires a development build; Expo Go supports foreground recording only.');
  if(!(await Location.requestForegroundPermissionsAsync()).granted)throw Error('Allow foreground location access first.');
  if(!(await Location.requestBackgroundPermissionsAsync()).granted)throw Error('Allow Always / Allow all the time location access to record in the background.');
  if(!await Location.hasServicesEnabledAsync())throw Error('Turn on Location Services to enable background recording.');
  await initializeRecording();
  await Location.startLocationUpdatesAsync(BACKGROUND_GPS_TASK,{accuracy:Location.Accuracy.High,timeInterval:2000,distanceInterval:0,deferredUpdatesInterval:10000,deferredUpdatesDistance:0,pausesUpdatesAutomatically:false,activityType:Location.ActivityType.Fitness,showsBackgroundLocationIndicator:true,foregroundService:{notificationTitle:'Topo Maps is recording your route',notificationBody:'GPS recording continues with the screen locked. Turn it off in recording stats.',notificationColor:'#287259',killServiceOnDestroy:true}});
  enabled=true;message='';
 }catch(e){message=e instanceof Error?e.message:String(e);throw e}finally{notify()}
}

import {useEffect,useRef,useState} from 'react';
import {AppState} from 'react-native';
import * as Location from 'expo-location';
export type UserLocation={longitude:number;latitude:number;accuracy:number;center:boolean};
export function useUserLocation(onUpdate:(location:UserLocation)=>void,onPoint?:(point:Location.LocationObject)=>void){
 const callback=useRef(onUpdate),pointCallback=useRef(onPoint);callback.current=onUpdate;pointCallback.current=onPoint;
 const subscription=useRef<Location.LocationSubscription|null>(null),mounted=useRef(true),generation=useRef(0);
 const [tracking,setTracking]=useState(false),[locating,setLocating]=useState(false),[error,setError]=useState('');
 const update=(position:Location.LocationObject,center:boolean)=>{if(!mounted.current||AppState.currentState!=='active')return;setError('');callback.current({longitude:position.coords.longitude,latitude:position.coords.latitude,accuracy:Math.max(0,position.coords.accuracy||0),center});pointCallback.current?.(position)};
 const stop=()=>{if(mounted.current)setTracking(false);generation.current++;subscription.current?.remove();subscription.current=null};
 async function watch(requestPermission=false){
  const token=++generation.current;
  try{
   let permission=await Location.getForegroundPermissionsAsync();
   if(!permission.granted&&requestPermission)permission=await Location.requestForegroundPermissionsAsync();
   if(!mounted.current||token!==generation.current||AppState.currentState!=='active')return;
   if(!permission.granted)throw Error('Allow foreground location access to record GPS points.');
   if(!await Location.hasServicesEnabledAsync())throw Error('Turn on Location Services to record GPS points.');
   if(token!==generation.current||AppState.currentState!=='active')return;
   subscription.current?.remove();subscription.current=null;
   const sub=await Location.watchPositionAsync({accuracy:Location.Accuracy.High,distanceInterval:0,timeInterval:2000},position=>{if(token===generation.current)update(position,false)},()=>{if(mounted.current&&token===generation.current)setError('GPS updates are unavailable. Tap locate to retry.')});
   if(mounted.current&&token===generation.current&&AppState.currentState==='active'){subscription.current=sub;setTracking(true)}else sub.remove();
  }catch(e){if(mounted.current&&token===generation.current)setError(e instanceof Error?e.message:String(e))}
 }
 useEffect(()=>{mounted.current=true;if(AppState.currentState==='active')void watch(true);const listener=AppState.addEventListener('change',state=>{stop();if(state==='active')void watch()});return()=>{mounted.current=false;stop();listener.remove()}},[]);
 async function locate(){
  if(locating)return;setLocating(true);setError('');let timeout:ReturnType<typeof setTimeout>|undefined;
  try{
   await watch(true);
   const permission=await Location.getForegroundPermissionsAsync();if(!permission.granted)return;
   const position=await Promise.race([Location.getCurrentPositionAsync({accuracy:Location.Accuracy.High}),new Promise<never>((_,reject)=>{timeout=setTimeout(()=>reject(Error('Location is taking too long. Try again with a clear view of the sky.')),20000)})]);
   update(position,true);
  }catch(e){if(mounted.current)setError(e instanceof Error?e.message:String(e))}
  finally{clearTimeout(timeout);if(mounted.current)setLocating(false)}
 }
 return {locate,locating,tracking,error,clearError:()=>setError('')};
}

import {useEffect,useState} from 'react';
import {AppState} from 'react-native';
import type {LocationObject} from 'expo-location';
import {currentRecording,initializeRecording,recordLocation,subscribeGPS} from './gpsService';
import {backgroundRecordingEnabled,backgroundRecordingMessage,refreshBackgroundRecording,setBackgroundRecording,subscribeBackground} from './backgroundLocation';
export function useGPSRecording(){
 const [,render]=useState(0),[backgroundBusy,setBackgroundBusy]=useState(false),recording=currentRecording();
 useEffect(()=>{const unsubscribe=subscribeGPS(()=>render(n=>n+1)),unbackground=subscribeBackground(()=>render(n=>n+1));void initializeRecording();void refreshBackgroundRecording();const sub=AppState.addEventListener('change',state=>{if(backgroundRecordingEnabled())recording.flush();else recording.breakSegment();if(state==='active')void refreshBackgroundRecording()});return()=>{unsubscribe();unbackground();sub.remove();recording.flush()}},[]);
 const record=(p:LocationObject)=>{if(AppState.currentState==='active'&&(!backgroundRecordingEnabled()||!!backgroundRecordingMessage()))recordLocation(p)};
 const toggleBackground=async(value:boolean)=>{if(backgroundBusy)return;setBackgroundBusy(true);try{await setBackgroundRecording(value)}catch{/* The service exposes the actionable permission/build error in the panel. */}finally{setBackgroundBusy(false)}};
 return {recording,record,backgroundEnabled:backgroundRecordingEnabled(),backgroundMessage:backgroundRecordingMessage(),backgroundBusy,toggleBackground};
}

import {TileRecovery} from './src/tileRecovery.mjs';
import * as Clipboard from 'expo-clipboard';
import * as FS from 'expo-file-system/legacy';
import React,{useEffect,useRef,useState} from 'react';
import {ActivityIndicator,AppState,Alert,Linking,Pressable,StatusBar,StyleSheet,Text,View} from 'react-native';
import {SafeAreaProvider,initialWindowMetrics,useSafeAreaInsets} from 'react-native-safe-area-context';
import {WebView,WebViewMessageEvent} from 'react-native-webview';
import {useGPSRecording} from './src/useGPSRecording';
import {RecordingStats} from './src/RecordingStats';
import {mapHtml} from './src/map';
import {DownloadStatus} from './src/DownloadStatus';
import {useAreaBoundaries} from './src/useAreaBoundaries';
import type {AreaData} from './src/areas';
import {TileStore,resetDevelopmentMapCache} from './src/storage';
import {rendererInit,rendererScript} from './src/rendererBridge';
import {useUserLocation,UserLocation} from './src/useUserLocation';
declare const process:{env:{EXPO_PUBLIC_TILE_SERVER?:string}};
const api=(process.env.EXPO_PUBLIC_TILE_SERVER||'https://topo-map.andrewljohnson.workers.dev').replace(/\/$/,'');
const html=mapHtml();
export default function App(){return <SafeAreaProvider initialMetrics={initialWindowMetrics}><MapApp/></SafeAreaProvider>}
function MapApp(){
 const insets=useSafeAreaInsets();
 const {recording,record,backgroundEnabled,backgroundMessage,backgroundBusy,toggleBackground}=useGPSRecording();const [statsOpen,setStatsOpen]=useState(false);
 const web=useRef<WebView>(null),ready=useRef(false),lastLocation=useRef<UserLocation|null>(null),areas=useRef<AreaData|null>(null);
 const tileRecovery=useRef(new TileRecovery());
 const viewportRequests=useRef(new Map<string,{alive:boolean}>());
 const [,render]=useState(0),[mode,setMode]=useState(false),[downloadsOpen,setDownloadsOpen]=useState(false),[gridVisible,setGridVisible]=useState(false),[isReady,setIsReady]=useState(false),[infoOpen,setInfoOpen]=useState(false),[noteOpen,setNoteOpen]=useState(false),[error,setError]=useState(''),[loading,setLoading]=useState(true),[rendererFailed,setRendererFailed]=useState(false),[rendererKey,setRendererKey]=useState(0);
 const noteWrites=useRef(Promise.resolve()),noteRestored=useRef(false);
 const storeRef=useRef<TileStore|null>(null);if(!storeRef.current)storeRef.current=new TileStore(api,()=>render(n=>n+1));const store=storeRef.current;
 const send=(m:unknown)=>web.current?.injectJavaScript(rendererScript(m));
 useAreaBoundaries(api,data=>{areas.current=data;if(ready.current)send({type:'areas',data})},Boolean(store.meta&&!store.meta.combined));
 const location=useUserLocation(point=>{lastLocation.current={...point,center:false};if(ready.current)send({type:'location',...point})},record);
 const sync=()=>{if(ready.current){send({type:'safeArea',insets});if(store.meta){send(rendererInit(store.meta));if(!noteRestored.current){noteRestored.current=true;Promise.all(['map-note-draft.json','map-notes.json'].map(name=>FS.readAsStringAsync(FS.documentDirectory+name).then(text=>JSON.parse(text)).catch(()=>null))).then(([draft,notes])=>{send({type:'restoreMapNote',draft});send({type:'restoreMapNotes',notes:Array.isArray(notes)?notes:[]})});}send({type:'state',mode,regions:store.regions})}}};
 useEffect(()=>{const recoveryTimer=setInterval(()=>{if(AppState.currentState!=='active'||!ready.current)return;const keys=tileRecovery.current.due();if(keys.length)send({type:'retryTiles',keys})},5000);store.setForeground(AppState.currentState==='active');const subscription=AppState.addEventListener('change',state=>store.setForeground(state==='active'));return ()=>{clearInterval(recoveryTimer);subscription.remove()}},[]);
 useEffect(()=>{(async()=>{if(__DEV__)await resetDevelopmentMapCache();await store.init()})().catch(e=>setError(`Cannot reach the map server at ${api}. ${String(e)}`)).finally(()=>setLoading(false))},[]);
 useEffect(sync,[mode,store.meta,JSON.stringify(store.regions),insets.top,insets.right,insets.bottom,insets.left]);
 const onMessage=async(event:WebViewMessageEvent)=>{try{
  const m=JSON.parse(event.nativeEvent.data);
  if(m.type==='ready'){setInfoOpen(false);setNoteOpen(false);noteRestored.current=false;for(const owner of viewportRequests.current.values())owner.alive=false;viewportRequests.current.clear();store.cancelUnused();ready.current=true;setIsReady(true);setRendererFailed(false);setError(current=>current.startsWith('Map renderer:')?'':current);sync();if(areas.current)send({type:'areas',data:areas.current});if(lastLocation.current)send({type:'location',...lastLocation.current})}
  else if(m.type==='tile'){const owner={alive:true};viewportRequests.current.set(m.id,owner);try{const src=await store.source(m.key,()=>owner.alive);if(owner.alive){tileRecovery.current.success(m.key);send({type:'tile',id:m.id,src});}}catch{if(owner.alive){tileRecovery.current.fail(m.key);send({type:'tile',id:m.id,error:'Tile unavailable offline or server unreachable'});}}finally{if(viewportRequests.current.get(m.id)===owner)viewportRequests.current.delete(m.id)}}
  else if(m.type==='tileCancel'){const owner=viewportRequests.current.get(m.id);if(owner){owner.alive=false;viewportRequests.current.delete(m.id);store.cancelUnused()}}
  else if(m.type==='fatal'){if(__DEV__)console.info('Map renderer diagnostic:',m.message,m.details||'');setRendererFailed(true);setError('Map renderer: '+m.message)}
  else if(m.type==='copyMapNote'){try{if(!await Clipboard.setStringAsync(m.text))throw Error('Clipboard unavailable');send({type:'mapNoteCopyResult',id:m.id})}catch{send({type:'mapNoteCopyResult',id:m.id,error:'Clipboard unavailable'})}}
  else if(m.type==='mapNoteDraft'){const text=JSON.stringify(m.draft);noteWrites.current=noteWrites.current.catch(()=>{}).then(()=>FS.writeAsStringAsync(FS.documentDirectory+'map-note-draft.json',text)).catch(()=>{});}
  else if(m.type==='mapNotesLibrary'){const text=JSON.stringify(m.notes);noteWrites.current=noteWrites.current.catch(()=>{}).then(()=>FS.writeAsStringAsync(FS.documentDirectory+'map-notes.json',text)).catch(()=>send({type:'mapNotesStorageError'}));}
  else if(m.type==='noteDrawer'){setNoteOpen(m.open===true);if(m.open)setDownloadsOpen(false)}
  else if(m.type==='infoDrawer'){setInfoOpen(m.open===true);if(m.open)setDownloadsOpen(false)}
  else if(m.type==='gridStatus')setGridVisible(m.visible);
  else if(m.type==='mapTap')setDownloadsOpen(false);
  else if(m.type==='cell')await store.toggle(m.id);
 }catch(e){setError(String(e))}};
 const clear=()=>Alert.alert('Clear downloaded maps?','This removes all cached tiles from this device.',[{text:'Keep maps',style:'cancel'},{text:'Clear',style:'destructive',onPress:()=>store.clear().then(()=>send({type:'refresh'})).catch(e=>Alert.alert('Downloads active',e.message))}]);
 const retry=()=>{setError('');if(rendererFailed){ready.current=false;setIsReady(false);setRendererKey(n=>n+1)}else{setLoading(true);store.init().then(()=>send({type:'refresh'})).catch(e=>setError(String(e))).finally(()=>setLoading(false))}};
 return <View style={styles.root}>
  <StatusBar barStyle="dark-content"/>
  <WebView key={rendererKey} ref={web} source={{html}} contentInsetAdjustmentBehavior="never" originWhitelist={['*']} javaScriptEnabled onMessage={onMessage} style={styles.map} onShouldStartLoadWithRequest={r=>{if(r.url.startsWith('https://')){Linking.openURL(r.url);return false}return true}}/>
  <View pointerEvents="box-none" style={[styles.overlay,{display:infoOpen||noteOpen?'none':'flex',top:insets.top,left:insets.left,right:insets.right}]}>
   <DownloadStatus open={downloadsOpen} setOpen={setDownloadsOpen} regions={store.regions} selecting={mode} gridVisible={gridVisible} onSelectingChange={setMode} onClear={clear} onToggleRegion={id=>store.toggle(id)}/>
   {loading&&<View style={styles.notice}><ActivityIndicator color="#1e6655"/><Text style={styles.noticeText}>Connecting to maps…</Text></View>}
   {!!location.error&&<Pressable accessibilityRole="button" accessibilityLabel="Dismiss location message" style={styles.notice} onPress={location.clearError}><Text style={styles.noticeText}>{location.error}{'\n'}Tap to dismiss.</Text></Pressable>}
  </View>
  {!infoOpen&&!noteOpen&&<Pressable accessibilityRole="button" accessibilityLabel="Center map on my location" accessibilityState={{busy:location.locating,disabled:location.locating||!isReady}} disabled={location.locating||!isReady} onPress={location.locate} style={[styles.locate,{left:insets.left+16,bottom:insets.bottom+16}]}>{location.locating?<ActivityIndicator color="#2778bd"/>:<View style={styles.crosshair}><View style={styles.centerDot}/></View>}</Pressable>}
  {!infoOpen&&!noteOpen&&<Pressable accessibilityRole="button" accessibilityLabel="View recording stats" onPress={()=>setStatsOpen(true)} style={[styles.locate,{right:insets.right+16,bottom:insets.bottom+60}]}><View style={{flexDirection:'row',alignItems:'flex-end',gap:3,height:22}}>{[10,20,15].map((height,i)=><View key={i} style={{width:4,height,backgroundColor:'#287259',borderRadius:1}}/>)}</View></Pressable>}
  <RecordingStats backgroundEnabled={backgroundEnabled} backgroundBusy={backgroundBusy} backgroundMessage={backgroundMessage} onBackgroundChange={toggleBackground} gpsStatus={location.error||(backgroundEnabled?'Foreground + background GPS recording':location.tracking?'Recording while this app is in the foreground':'Waiting for foreground GPS…')} open={statsOpen} onClose={()=>setStatsOpen(false)} recording={recording}/>
 </View>
}
const styles=StyleSheet.create({root:{flex:1,backgroundColor:'#e7ece3'},map:{flex:1},overlay:{position:'absolute',top:0,left:0,right:0,bottom:0},notice:{marginHorizontal:16,marginTop:8,padding:14,gap:8,borderRadius:14,backgroundColor:'#fff8e7'},noticeText:{fontSize:13,color:'#665d47',lineHeight:19},locate:{position:'absolute',width:44,height:44,borderRadius:12,backgroundColor:'#fafbf5',justifyContent:'center',alignItems:'center',shadowColor:'#17392a',shadowOpacity:.15,shadowRadius:8,elevation:4},crosshair:{width:21,height:21,borderRadius:11,borderWidth:1.8,borderColor:'#287259',justifyContent:'center',alignItems:'center'},centerDot:{height:7,width:7,borderRadius:4,backgroundColor:'#287259'}});

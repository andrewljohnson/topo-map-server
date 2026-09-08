import React,{useEffect,useRef} from 'react';
import {Animated,Easing,Alert,Pressable,ScrollView,StyleSheet,Text,View,useWindowDimensions} from 'react-native';
import type {Regions} from './storage';
const formatBytes=(bytes:number)=>bytes>=1e9?`${(bytes/1e9).toFixed(2)} GB`:`${(bytes/1e6).toFixed(2)} MB`;
const count=(n=0)=>n.toLocaleString();
const percent=(done=0,total=0)=>total?Math.min(100,Math.round(done/total*100)):0;
function area(id:string){const [x,y]=id.split('/').map(Number),n=4096;const lon=(x+.5)/n*360-180,lat=Math.atan(Math.sinh(Math.PI*(1-2*(y+.5)/n)))*180/Math.PI;return `Area near ${Math.abs(lat).toFixed(2)}°${lat<0?'S':'N'}, ${Math.abs(lon).toFixed(2)}°${lon<0?'W':'E'}`}
export function DownloadStatus({open,setOpen,regions,selecting,gridVisible,onSelectingChange,onClear,onToggleRegion}:{open:boolean;setOpen:(value:boolean)=>void;regions:Regions;selecting:boolean;gridVisible:boolean;onSelectingChange:(value:boolean)=>void;onClear:()=>void;onToggleRegion:(id:string)=>Promise<void>}){
 const {height}=useWindowDimensions();
 const entries=Object.entries(regions),pending=entries.filter(([,r])=>r.status!=='complete');
 const downloading=entries.some(([,r])=>r.status==='downloading');
 const shimmer=useRef(new Animated.Value(0)).current;
 useEffect(()=>{if(!downloading){shimmer.setValue(0);return}const animation=Animated.loop(Animated.sequence([Animated.timing(shimmer,{toValue:1,duration:1100,easing:Easing.linear,useNativeDriver:true}),Animated.delay(250)]));animation.start();return()=>animation.stop()},[downloading,shimmer]);
 return <View pointerEvents="box-none" style={s.wrap}>
  <Pressable accessibilityRole="button" accessibilityLabel={downloading?'Map downloads, downloading to this device':'Map downloads'} accessibilityState={{expanded:open,busy:downloading}} onPress={()=>{if(open)onSelectingChange(false);setOpen(!open)}} style={[s.button,open&&s.buttonOpen]}>
   <View accessible={false} style={s.mapIcon}>{[0,1,2].map(i=><View key={i} style={[s.mapFold,{transform:[{skewY:i===1?'22deg':'-22deg'}]}]}>{downloading&&<Animated.View style={[s.shimmer,{transform:[{translateX:shimmer.interpolate({inputRange:[0,1],outputRange:[-12-i*8,36-i*8]})}]}]}/>}</View>)}</View>
  </Pressable>
  {open&&<ScrollView style={[s.panel,{maxHeight:Math.min(420,height*.5)}]} contentContainerStyle={s.content}>
   <Pressable accessibilityRole="button" style={s.selectButton} onPress={()=>onSelectingChange(!selecting)}><Text style={s.selectText}>{selecting?'✓ Done choosing areas':'＋ Choose areas to download'}</Text></Pressable>
   <Text style={[s.detail,{marginTop:8,marginBottom:16}]}>{selecting?(gridVisible?'Tap grid squares to download. Tap again to remove them from the queue.':'Zoom in to show the download grid.'):'Save maps and elevation for offline use.'}</Text>
   <Text style={s.heading}>On this device · {entries.filter(([,r])=>r.status==='complete').length} saved</Text>
   {!pending.length&&<Text style={s.detail}>No maps downloading{entries.length?` · ${entries.length} saved`:''}.</Text>}
   {entries.map(([id,r])=><View key={id} style={s.row}><Text style={s.title}>{area(id)}</Text><Text style={s.detail}>{r.status==='error'?'Needs retry':r.status==='queued'?'Queued':r.status==='complete'?'Saved':'Downloading'} · {count(r.done)} / {count(r.total)} tiles</Text><Text style={s.detail}>{r.bytes===undefined?'Measuring size…':`${formatBytes(r.bytes)} ${r.status==='complete'?'saved':'downloaded so far'}`}</Text><View style={s.track}><View style={[s.fill,{width:`${percent(r.done,r.total)}%`}]} /></View>{r.error&&<Text style={s.error}>{r.error}</Text>}<Pressable accessibilityRole="button" onPress={()=>onToggleRegion(id).catch(e=>Alert.alert('Download',String(e)))} style={s.action}><Text style={s.actionText}>{r.status==='error'?'Retry download':r.status==='complete'?'Remove area':'Remove from queue'}</Text></Pressable></View>)}
   {!!entries.length&&<Pressable accessibilityRole="button" onPress={onClear} style={s.action}><Text style={s.actionText}>Clear saved maps</Text></Pressable>}
  </ScrollView>}
 </View>
}
const s=StyleSheet.create({wrap:{marginHorizontal:16,marginTop:16,marginBottom:0,alignItems:'flex-start'},button:{width:44,height:44,borderRadius:12,alignItems:'center',justifyContent:'center',backgroundColor:'#fafbf5',shadowColor:'#17392a',shadowOpacity:.15,shadowRadius:8,elevation:4},buttonOpen:{backgroundColor:'#dfecdf'},mapIcon:{width:24,height:24,flexDirection:'row',alignItems:'center'},mapFold:{width:8,height:19,backgroundColor:'#287259',borderWidth:1,borderColor:'#fafbf5',overflow:'hidden'},shimmer:{position:'absolute',left:0,top:-4,bottom:-4,width:7,backgroundColor:'#eaffad',shadowColor:'#fff',shadowOpacity:1,shadowRadius:3},panel:{marginTop:12,maxHeight:420,width:'100%',borderRadius:20,backgroundColor:'#fafbf5',elevation:5},content:{padding:16},selectButton:{minHeight:44,paddingHorizontal:14,justifyContent:'center',alignItems:'center',borderRadius:12,backgroundColor:'#287259'},selectText:{fontSize:14,fontWeight:'600',color:'#fff'},action:{minHeight:44,justifyContent:'center'},actionText:{fontSize:12,fontWeight:'600',color:'#32745e'},heading:{fontSize:11,fontWeight:'700',letterSpacing:1,color:'#64776b',textTransform:'uppercase'},row:{marginTop:10,gap:5},title:{fontSize:15,fontWeight:'600',color:'#203f33'},detail:{fontSize:12,color:'#65766c',lineHeight:19},track:{height:4,backgroundColor:'#e2e7da',borderRadius:2,overflow:'hidden',marginVertical:5},fill:{height:4,backgroundColor:'#287259'},error:{fontSize:12,color:'#a06522',lineHeight:18}});

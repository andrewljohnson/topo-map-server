// Retry only failed visible tile coordinates; never reload the complete map.
export class TileRecovery {
 constructor(){this.failed=new Map()}
 fail(key,now=Date.now()){const previous=this.failed.get(key);if(!previous)this.failed.set(key,{attempt:0,due:now+30000});while(this.failed.size>256)this.failed.delete(this.failed.keys().next().value)}
 success(key){this.failed.delete(key)}
 due(now=Date.now()){const keys=[];for(const [key,row] of this.failed){if(row.due>now)continue;keys.push(key);row.attempt++;row.due=now+Math.min(300000,30000*2**row.attempt);if(keys.length===32)break}return keys}
}

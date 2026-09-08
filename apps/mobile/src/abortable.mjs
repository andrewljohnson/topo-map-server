// Native fetch/body promises can remain pending after abort on iOS. Settle our
// waiter independently so a cancelled transfer cannot retain a scheduler slot.
export function abortable(promise,signal){
 return new Promise((resolve,reject)=>{
  const cancel=()=>{cleanup();reject(Error('Cancelled'))};
  const cleanup=()=>signal.removeEventListener('abort',cancel);
  Promise.resolve(promise).then(value=>{cleanup();if(signal.aborted)reject(Error('Cancelled'));else resolve(value)},error=>{cleanup();reject(error)});
  if(signal.aborted)cancel();else signal.addEventListener('abort',cancel,{once:true});
 });
}

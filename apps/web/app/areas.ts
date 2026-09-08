export type AreaData={type:'FeatureCollection';features:any[]};
export function parseAreaData(value:any):AreaData{if(value?.type!=='FeatureCollection'||!Array.isArray(value.features))throw Error('Invalid area boundaries');return value}

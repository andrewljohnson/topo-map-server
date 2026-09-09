#!/usr/bin/env python3
"""Transparent planning arithmetic, not a promise of nationwide completion time."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RESULTS=ROOT/'experiments/tahoe/results'
def main():
    vector_count,dem_count,world_count,overview_count=144027,146681,21845,48750
    cold=json.loads((RESULTS/'cold-dem-probes.json').read_text())
    threaded=[*json.loads((RESULTS/'cold-dem-probes-threads16.json').read_text()),*json.loads((RESULTS/'cold-dem-probes-threads16kansas.json').read_text())]
    dem_projections=[{'region':r['region'],'workers':r['workers'],'executor':r.get('executor','processes'),'hours':r['seconds']/r['demParents']*dem_count/3600,'GB':r['demBytes']/r['demParents']*dem_count/1e9} for r in cold+threaded+json.loads((RESULTS/'cold-dem-probes-prefetch16.json').read_text())+json.loads((RESULTS/'cold-dem-probes-prefetch16kansas.json').read_text())]
    large=json.loads((RESULTS/'western-1000x-first-scale.json').read_text())
    vector_hours=(large['totalSeconds']-large['dem']['seconds'])/large['vectorParents']*vector_count/3600
    low_gb,high_gb=210,320
    upload=[{'Mbps':rate,'hoursFor210GB':low_gb*8000/rate/3600,'hoursFor320GB':high_gb*8000/rate/3600} for rate in (20,50,100)]
    report={'counts':{'detailedVectorParents':vector_count,'detailedDemParents':dem_count,'worldBaseZ0To7':world_count,'conusBaseZ8To11':overview_count},'coldDemProjections':dem_projections,'westernVectorStageLinearHours':vector_hours,'planningHours':{'detailedVectors':[8,12],'coldDem':[19,27],'overviews':[3,6],'preparationAndValidationReserve':[6,12],'totalWithOverlappingUpload':[36,60]},'storageGB':[low_gb,high_gb],'r2StandardStorageDollarsPerMonth':[(low_gb-10)*.015,(high_gb-10)*.015],'uploadSensitivity':upload,'measuredCloudflareEdgeUploadMbps':json.loads((RESULTS/'upload-link-probe.json').read_text())['medianMbps'],'limitations':['The western vector estimate needs regional density/acquisition allowance.','Cold DEM probes use empty native caches but retain already-pinned source catalogs and the global fallback cache.','Cloudflare edge throughput is not an R2 publication benchmark.','36–60 hours is a planning range, dependent on source availability and successful release-contract pilot.']}
    (RESULTS/'conus-forecast.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

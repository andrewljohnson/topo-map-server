"""Refresh the offline style payload after regions/build_amenities.py."""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'apps/mobile/src/amenity-data.json').read_text())
for feature in data['features']:
    props=feature['properties']
    if props['kind']=='group':
        props['grid_image']='amenity-grid:'+','.join(props['icons'])
        props['text_offset']=[0,((len(props['icons'])+2)//3)+.35]
for name in ['apps/mobile/src/style.mjs','apps/mobile/src/vectorStyle.ts','apps/web/app/vectorStyle.ts']:
    path=root/name
    text,count=re.subn(r'const AMENITY_DATA\s*=.*;\n',lambda _: 'const AMENITY_DATA='+json.dumps(data,separators=(',',':'))+';\n',path.read_text())
    assert count==1,name
    path.write_text(text)

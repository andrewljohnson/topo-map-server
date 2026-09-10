# Twin Peaks PCT survey duplication

User report at -120.23739,39.10252, z14.209976 on California r1. Confirmed visually on live site: OSM/PCTA PCT and generalized USFS PC2000 both draw, including switchbacks and northern approach. Nearby TRT also has agency overlap.

A fresh combined parent 12/679/1563 from source a30f25d still reproduces the PCT overlap, so California r3 does not resolve this report. Keep this limitation explicit; do not claim all reported PCT cases fixed when promoting r3.

Fine source fixtures captured at 14/2719/6254 and6255 in `/tmp/pct-north-inputs.json`; live tile `/tmp/pct-north-live.pbf`; candidate `services/tiles/data/publication/combined/pct-north-proof`. The one-parent preview used four workers alongside publication. Full correspondence fails existing signed-route thresholds: partial/multipart reference alignment, ratio about0.79 in the switchbacks, and ordered shape distance about206m. Some other fragments have no tight interior seed. These measurements do not justify globally increasing the proximity radius.

Further investigation is assigned to the existing parallel QA agent `halfmoon_poi`: compare PCTA/OSM corroboration and USFS survey alignment, preserve unrelated trails/branches and stage a source regression fix for a later immutable candidate. Never modify the running frozen r3 checkout.

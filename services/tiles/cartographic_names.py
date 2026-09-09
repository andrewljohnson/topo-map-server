"""Readable display names while retaining source spellings for matching/provenance."""
import re
KEEP={'PCT','TRT','JMT','CDT','AT','US','USFS','NPS','FS','FR','NF','NFSR','SR','CR','OHV','ATV','II','III','IV'}
def display_name(value):
 name=str(value or '')
 if not name or name!=name.upper() or not any(c.isalpha() for c in name):return name
 def word(match):
  token=match.group()
  if token=='CG':return 'Campground'
  if token in KEEP or any(c.isdigit() for c in token) or len(token)==1:return token
  return token.title()
 return re.sub(r"[A-Z0-9]+(?:'[A-Z]+)?",word,name)

"""Native MOSS protocol parsing with no numeric/scoring/model dependencies.

Matches the frozen whole-meeting scorer; all residual lexical content remains
visible and unknown. This parser never rewrites numbers, fillers or repetitions.
"""
import re
def parse_native(raw):
 pattern=re.compile(r'\[(\d+(?:\.\d+)?)\]\[S(\d+)\](.*?)\[(\d+(?:\.\d+)?)\]',re.S)
 rows=[];residual=[];last=0
 for m in pattern.finditer(raw):
  leftover=raw[last:m.start()]
  if leftover.strip():residual.append({'beforeSegment':len(rows),'text':leftover})
  rows.append({'start':float(m[1]),'end':float(m[4]),'speaker':'S'+m[2],'text':m[3]});last=m.end()
 tail=raw[last:]
 if tail.endswith('<|im_end|>'):tail=tail[:-len('<|im_end|>')]
 if tail.strip():residual.append({'beforeSegment':len(rows),'text':tail})
 all_rows=[]
 for i in range(len(rows)+1):
  all_rows.extend({'speaker':None,'text':r['text'],'start':float('inf'),'end':float('inf')} for r in residual if r['beforeSegment']==i)
  if i<len(rows):all_rows.append(rows[i])
 return rows,all_rows,residual

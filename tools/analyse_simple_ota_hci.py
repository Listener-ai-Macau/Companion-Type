"""Read an existing DLT201 PCAPNG and correlate one simple OTA file.

No hardware access or key/plaintext export. HCI is the host/controller
boundary, not over-air timing or a durable NOR receipt by itself.
"""
from collections import Counter
from pathlib import Path
import argparse, hashlib, json, math, struct


def packets(path):
    data=Path(path).read_bytes();pos=0;interfaces=[]
    while pos<len(data):
        if len(data)-pos<12:raise ValueError('Truncated PCAPNG block')
        kind,size=struct.unpack_from('<II',data,pos)
        if size<12 or size%4 or pos+size>len(data) or struct.unpack_from('<I',data,pos+size-4)[0]!=size:
            raise ValueError('Invalid PCAPNG block extent')
        body=data[pos+8:pos+size-4];pos+=size
        if kind==0x0a0d0d0a:
            if body[:4]!=b'\x4d\x3c\x2b\x1a':raise ValueError('Requires little-endian PCAPNG')
            interfaces=[]
        elif kind==1:
            link=struct.unpack_from('<H',body)[0];resolution=1e-6;offset=8
            while offset+4<=len(body):
                option,count=struct.unpack_from('<HH',body,offset);offset+=4
                value=body[offset:offset+count];offset+=(count+3)&~3
                if option==0:break
                if option==9:
                    if len(value)!=1:raise ValueError('Invalid timestamp resolution')
                    resolution=(2 if value[0]&128 else 10)**(-(value[0]&127))
            interfaces.append((link,resolution))
        elif kind==6:
            interface,hi,lo,captured,original=struct.unpack_from('<5I',body)
            if interface>=len(interfaces) or captured>original or 20+captured>len(body):raise ValueError('Invalid packet extent')
            link,resolution=interfaces[interface]
            if link!=201:raise ValueError('Requires BTP DLT201 interface')
            yield ((hi<<32)|lo)*resolution,body[20:20+captured]


def stats(values):
    values=sorted(values)
    if not values:return {'samples':0}
    return dict(samples=len(values),sum=sum(values),p50=values[math.ceil(.5*len(values))-1],
                p95=values[math.ceil(.95*len(values))-1],max=values[-1])


def analyze(capture,package,address):
    expected=Path(package).read_bytes();peer=bytes.fromhex(address.replace(':',''))[::-1]
    if len(peer)!=6:raise ValueError('Requires explicit six-byte target identity')
    handles=set();pending={};writes=[];controls=[];receipts=[];links=[];captured_chunks={};parameter_signals=[];host_updates=[];truncated=0;other=0
    for stamp,packet in packets(capture):
        if len(packet)<5:continue
        direction=int.from_bytes(packet[:4],'big');kind=packet[4];raw=packet[5:]
        if kind==1 and len(raw)>=17 and int.from_bytes(raw[:2],'little')==0x2013:
            handle,lo,hi,latency,timeout,ce_lo,ce_hi=struct.unpack_from('<7H',raw,3)
            if handle in handles:
                host_updates.append(dict(time=stamp,intervalMinUnits=lo,intervalMaxUnits=hi,latency=latency,supervisionUnits10ms=timeout,minCeUnits625us=ce_lo,maxCeUnits625us=ce_hi,scope='host_request_only_not_applied_result'))
        if kind==4 and len(raw)>=3:
            event=raw[0];v=raw[2:]
            if event==0x3e and len(v)>=12 and v[0] in (1,10) and v[1]==0:
                handle=int.from_bytes(v[2:4],'little')
                if v[6:12]==peer:
                    handles.add(handle);entry=dict(time=stamp,event='target_connected')
                    at=12 if v[0]==1 else 24
                    if len(v)>=at+6:
                        ci,latency,timeout=struct.unpack_from('<3H',v,at)
                        entry.update(intervalUnits=ci,latency=latency,supervisionUnits10ms=timeout)
                    links.append(entry)
            elif event==0x3e and len(v)>=4 and int.from_bytes(v[2:4],'little') in handles and v[0] in (3,12):
                if v[0]==3 and len(v)>=10:
                    ci,latency,timeout=struct.unpack_from('<3H',v,4)
                    links.append(dict(time=stamp,event='target_interval',status=v[1],intervalUnits=ci,latency=latency,supervisionUnits10ms=timeout))
                elif v[0]==12 and len(v)>=6:
                    links.append(dict(time=stamp,event='target_phy',status=v[1],txPhy=v[4],rxPhy=v[5]))
            elif event==0x3e and len(v)>=11 and v[0]==7 and int.from_bytes(v[1:3],'little') in handles:
                tx_octets,tx_us,rx_octets,rx_us=struct.unpack_from('<4H',v,3)
                links.append(dict(time=stamp,event='target_data_length',txOctets=tx_octets,txTimeUs=tx_us,rxOctets=rx_octets,rxTimeUs=rx_us))
            elif event==8 and len(v)>=4 and int.from_bytes(v[1:3],'little') in handles:
                links.append(dict(time=stamp,event='target_encryption',status=v[0],enabled=v[3]))
            elif event==5 and len(v)>=4 and int.from_bytes(v[1:3],'little') in handles:
                handle=int.from_bytes(v[1:3],'little')
                links.append(dict(time=stamp,event='target_disconnect',reason=v[3],status=v[0]))
                if v[0]==0:
                    handles.remove(handle)
                    for key in list(pending):
                        if key[0]==handle:del pending[key]
            continue
        if kind!=2 or len(raw)<4:continue
        packed,count=struct.unpack_from('<HH',raw);handle=packed&4095;pb=(packed>>12)&3
        if handle not in handles:other+=1;continue
        key=(handle,direction)
        if len(raw)-4<count:
            truncated+=1;pending.pop(key,None);continue
        value=raw[4:4+count]
        if pb in (0,2):
            if len(value)<4:pending.pop(key,None);continue
            total,cid=struct.unpack_from('<HH',value)
            pending[key]=[total,cid,bytearray(value[4:]),stamp,1]
        elif pb==1 and key in pending:
            pending[key][2].extend(value);pending[key][4]+=1
        else:continue
        total,cid,value,first,pieces=pending[key]
        if len(value)<total:continue
        del pending[key]
        if len(value)!=total:raise ValueError('Overlong L2CAP value; no synthetic repair')
        if cid==5 and len(value)>=6 and value[0] in (0x12,0x13):
            count=int.from_bytes(value[2:4],'little')
            if count!=len(value)-4:raise ValueError('Invalid signaling length')
            entry=dict(time=stamp,direction=direction,code=value[0],identifier=value[1])
            if value[0]==0x12 and len(value)==12:
                lo,hi,latency,timeout=struct.unpack_from('<4H',value,4)
                entry.update(intervalMinUnits=lo,intervalMaxUnits=hi,latency=latency,supervisionUnits10ms=timeout)
            elif value[0]==0x13 and len(value)==6:entry['result']=int.from_bytes(value[4:6],'little')
            parameter_signals.append(entry)
        if cid!=4 or not value:continue
        opcode=value[0]
        if direction==0 and opcode in (0x12,0x52) and len(value)>=3:
            attribute=int.from_bytes(value[1:3],'little');data=value[3:]
            if len(data)>=20 and data[:4]==b'DOV1':
                controls.append(dict(first=first,time=stamp,operation=data[4],attribute=attribute))
            elif len(data)>4:
                offset=int.from_bytes(data[:4],'little');payload=data[4:]
                if offset+len(payload)<=len(expected) and payload==expected[offset:offset+len(payload)]:
                    if offset in captured_chunks and captured_chunks[offset]!=payload:
                        raise ValueError('Conflicting captured bytes at one file offset')
                    captured_chunks[offset]=bytes(payload)
                    writes.append(dict(first=first,time=stamp,offset=offset,bytes=len(payload),
                        attribute=attribute,attOpcode=opcode,fragments=pieces))
        elif direction==1 and opcode==0x0b and len(value)>=25 and value[1:5]==b'DOV1':
            data=value[1:]
            receipts.append(dict(time=stamp,state=data[5],error=data[6],flags=data[7],
                accepted=int.from_bytes(data[8:12],'little'),expected=int.from_bytes(data[12:16],'little'),
                dataWriteCount=int.from_bytes(data[20:24],'little')))
    unique={};duplicates=0
    for w in writes:
        if w['offset'] in unique:
            if w['bytes']!=unique[w['offset']]['bytes']:raise ValueError('Overlapping packet geometry; retain for manual analysis')
            duplicates+=1
        else:unique[w['offset']]=w
    missing=[];next_offset=0;digest=hashlib.sha256()
    for offset,w in sorted(unique.items()):
        if offset<next_offset:raise ValueError('Overlapping file ranges')
        if offset>next_offset:missing.append(dict(start=next_offset,end=offset))
        digest.update(captured_chunks[offset]);next_offset=offset+w['bytes']
    if next_offset<len(expected):missing.append(dict(start=next_offset,end=len(expected)))
    complete=bool(writes) and not missing and digest.hexdigest()==hashlib.sha256(expected).hexdigest()
    windows=[];start=0
    for control in controls:
        if control['operation']!=2:continue
        segment=[w for w in writes[start:] if w['time']<=control['time']]
        start+=len(segment)
        if not segment:continue
        after=next((r for r in receipts if r['time']>=control['time']),None)
        window_end=max(w['offset']+w['bytes'] for w in segment)
        windows.append(dict(dataPackets=len(segment),bytes=sum(w['bytes'] for w in segment),
            dataFirstTime=segment[0]['first'],lastDataTime=segment[-1]['time'],
            dataSpanMs=(segment[-1]['time']-segment[0]['first'])*1000,
            lastDataToSyncMs=(control['time']-segment[-1]['time'])*1000,
            syncToFirstStatusMs=None if after is None else (after['time']-control['time'])*1000,
            firstStatusAccepted=None if after is None else after['accepted'],
            firstStatusMatchesWindowEnd=after is not None and after['accepted']==window_end,
            statusTime=None if after is None else after['time'],syncTime=control['time']))
    accepted=next((r for r in receipts if r['accepted']==len(expected) and r['expected']==len(expected)),None)
    wall=None if not writes or accepted is None else accepted['time']-writes[0]['first']
    gaps=[(b['dataFirstTime']-a['statusTime'])*1000 for a,b in zip(windows,windows[1:]) if a['statusTime'] is not None]
    partition=None
    if complete and accepted is not None and all(w['firstStatusMatchesWindowEnd'] for w in windows):
        phases=dict(dataSpanMs=sum(w['dataSpanMs'] for w in windows),
            lastDataToSyncMs=sum(w['lastDataToSyncMs'] for w in windows),
            syncToStatusMs=sum(w['syncToFirstStatusMs'] for w in windows),
            betweenWindowsMs=sum(gaps))
        residual=wall*1000-sum(phases.values())
        if abs(residual)>.001:raise ValueError('Complete HCI partition did not balance')
        partition=dict(**phases,wallMs=wall*1000,residualMs=residual,
            limits='Algebraic non-overlapping HCI presentation phases; no attribution of a phase to RF/controller/Flash CPU.')
    return dict(result='EXISTING_SIMPLE_OTA_HCI_BOUNDARY_ANALYSIS',packageBytes=len(expected),
        packageSha256=hashlib.sha256(expected).hexdigest(),hciFileBytesIndependentlyMatched=complete,
        missingFileRanges=missing,capturedFileWrites=len(writes),uniqueFileWrites=len(unique),duplicateFileWrites=duplicates,
        payloadBytesHistogram=dict(Counter(w['bytes'] for w in writes)),
        attOpcodeHistogram=dict(Counter(f'{w["attOpcode"]:02x}' for w in writes)),
        fragmentHistogram=dict(Counter(w['fragments'] for w in writes)),
        selectedTruncatedAcl=truncated,otherPeerAcl=other,links=links,
        l2capParameterSignals=parameter_signals,hostConnectionUpdateRequests=host_updates,
        deviceReportedFullFile=accepted is not None,hciFirstDataToFullStatusSeconds=wall,
        hciBoundaryFileKiBPerSecond=None if not wall else len(expected)/1024/wall,
        windows=windows,statusReceipts=receipts,completeHciPartition=partition,
        timing=dict(dataSpanMs=stats([w['dataSpanMs'] for w in windows]),
            lastDataToSyncMs=stats([w['lastDataToSyncMs'] for w in windows]),
            syncToFirstStatusMs=stats([w['syncToFirstStatusMs'] for w in windows if w['syncToFirstStatusMs'] is not None])),
        limits='HCI presentation and device status, not RF airtime or independent NOR readback. Sum of overlapping phases is not a wall-clock decomposition. Missing bytes are never filled from the package. File includes its176byte package header; this boundary rate does not replace native new-payload qualification or Boot/install confirmation. SMP/key bytes are neither interpreted nor exported.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--package',type=Path,required=True);p.add_argument('--address',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Output already exists; preserve prior evidence')
    result=analyze(a.capture,a.package,a.address)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('windows','statusReceipts')},ensure_ascii=False))

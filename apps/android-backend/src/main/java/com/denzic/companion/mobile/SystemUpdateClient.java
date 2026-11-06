package com.denzic.companion.mobile;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static com.denzic.companion.mobile.SystemUpdatePackage.*;

/** Acknowledged Android transport for the existing DOV1/CUP3 full-file route.
 * Wire fields mirror denzic-platform/ota/protocol and Windows simple_ota_restart.
 * A local Bluetooth write is never counted as durable storage or installation. */
public final class SystemUpdateClient {
    private SystemUpdateClient(){}
    public static final UUID SERVICE=UUID.fromString("1b55f597-f09c-4c7f-9529-adfa64983b06"),CONTROL=UUID.fromString("206c5e29-c64d-4392-8180-66463788533c"),DATA=UUID.fromString("fbc4b0fb-6102-4bd1-abe4-e5e90a9a7e12"),STATUS=UUID.fromString("e571544a-7c41-4650-b0d6-ccebfe1db489"),IDENTITY=UUID.fromString("e571544a-7c41-4650-b0d6-ccebfe1db48a"),READINESS=UUID.fromString("8f7a7001-7b7d-4f3d-9d6f-6c2d1b7c0000"),READINESS_SERVICE=UUID.fromString("8f7a0007-7b7d-4f3d-9d6f-6c2d1b7c0000");
    public interface Connector{RecordingClient.Link connect()throws IOException;}
    public interface Progress{void update(String phase,long accepted,long total)throws IOException;default void identity(String uid)throws IOException{}default void metrics(String json){}}
    /** Bounded host-side metadata. These counters never change durable receipts,
     * admission or installation decisions, and allocate no device RAM/Flash. */
    private static final class Metrics {
        final long started=System.nanoTime(),startedUnixMs=System.currentTimeMillis();final long payloadBytes,packageBytes,targetFirmware,targetResource;final String bundleId;
        long payloadStart,payloadEnd,finishStart,finishEnd,verifyStart,ended,submitNs,receiptNs;
        int mtu,chunk,window,dataWrites,flushes,statusReads,verifyAttempts,verifyFailures,pipelineDepth,creditNotices,creditFallbackReads,staleNotices;
        String scheduling="windowed_durable_receipt";
        boolean retentionConfirmed,installed;String writeMode="unknown",stage="checking",lastError="",uid="";
        byte[] firstLink,lastLink;
        Metrics(SystemUpdatePackage p){payloadBytes=p.firmwareBytes+p.resourceBytes;packageBytes=p.image.length;bundleId=p.id;targetFirmware=p.firmwareVersion;targetResource=p.resourceVersion;}
        void status(Status s){lastLink=s.raw;if(firstLink==null)firstLink=lastLink;}
        static Object elapsed(long first,long last){return first==0||last==0?org.json.JSONObject.NULL:(last-first)/1_000_000.0;}
        static org.json.JSONObject budget(byte[] b)throws org.json.JSONException{
            org.json.JSONObject o=new org.json.JSONObject();if(b==null)return o;
            o.put("rawHex",hex(b));
            if(b.length==64&&magic(b,24,"WOC5")){
                int f=b[48]&255;o.put("flags",f);
                if((f&8)!=0)o.put("txPhy",b[49]&255).put("rxPhy",b[50]&255);
                if((f&4)!=0)o.put("txOctets",u16(b,52)).put("txTimeUs",u16(b,54)).put("rxOctets",u16(b,56)).put("rxTimeUs",u16(b,58));
                if(u16(b,60)!=0)o.put("connectionIntervalMs",u16(b,60)*1.25);
                if(u16(b,62)!=0)o.put("deviceAttMtu",u16(b,62));
            }
            return o;
        }
        String json(){try{
            org.json.JSONObject o=new org.json.JSONObject().put("schema","companion.android.ota-metrics.v1").put("timingBasis","host_monotonic_nanos").put("stage",stage).put("startedUnixMs",startedUnixMs).put("bundleId",bundleId).put("targetFirmware",targetFirmware).put("targetResource",targetResource).put("uid",uid)
                .put("packageBytes",packageBytes).put("payloadBytes",payloadBytes).put("actualAttMtu",mtu).put("chunkBytes",chunk).put("durableWindowChunks",window).put("dataWriteMode",writeMode)
                .put("dataWrites",dataWrites).put("flushes",flushes).put("statusReads",statusReads).put("verifyAttempts",verifyAttempts).put("verifyFailures",verifyFailures).put("dataScheduling",scheduling).put("pipelineDepth",pipelineDepth).put("creditNotices",creditNotices).put("creditFallbackReads",creditFallbackReads).put("staleNotices",staleNotices)
                .put("admissionMs",elapsed(started,payloadStart)).put("payloadMs",elapsed(payloadStart,payloadEnd)).put("submitMs",submitNs/1_000_000.0).put("durableReceiptWaitMs",receiptNs/1_000_000.0)
                .put("finishRetentionMs",elapsed(finishStart,finishEnd)).put("verificationMs",elapsed(verifyStart,ended)).put("postPayloadMs",elapsed(payloadEnd,ended)).put("totalMs",elapsed(started,ended))
                .put("retentionConfirmed",retentionConfirmed).put("installed",installed).put("firstDeviceLink",budget(firstLink)).put("lastDeviceLink",budget(lastLink)).put("lastError",lastError);
            if(payloadStart!=0&&payloadEnd>payloadStart)o.put("payloadKiBps",payloadBytes*1_000_000_000.0/1024/(payloadEnd-payloadStart));
            return o.toString();
        }catch(org.json.JSONException error){return "{\"schema\":\"companion.android.ota-metrics.v1\",\"measurementError\":true}";}}
    }
    static byte[] control(int op,long bytes,int chunk,int window,long crc){byte[] p=new byte[20];System.arraycopy(new byte[]{'D','O','V','1'},0,p,0,4);p[4]=(byte)op;p[5]=1;put32(p,8,bytes);p[12]=(byte)chunk;p[13]=(byte)(chunk>>>8);p[14]=(byte)window;p[15]=(byte)(window>>>8);put32(p,16,crc);return p;}
    static final class Status{
        final byte[] raw;final int state,error,chunk,window,maxChunk,maxWindow;final long accepted,total,generation;final boolean hasGeneration;
        Status(byte[] b)throws IOException{
            if(b==null||b.length<24||!magic(b,0,"DOV1")||b[4]!=1||(b[5]&255)>4)throw new IOException("设备升级状态格式不正确");
            raw=b.clone();state=b[5]&255;error=b[6]&255;accepted=word(b,8);total=word(b,12);chunk=u16(b,16);window=u16(b,18);
            boolean v2=b.length==36&&magic(b,24,"WOC2"),v3=b.length==40&&magic(b,24,"WOC3"),v4=b.length==44&&magic(b,24,"WOC4"),v5=b.length==64&&magic(b,24,"WOC5");
            if(!v2&&!v3&&!v4&&!v5)throw new IOException("设备未提供受支持的完整固件与资源升级能力");
            int payload=u16(b,28),value=u16(b,30),advertisedWindow=u16(b,32),flags=u16(b,34),queue=v2?advertisedWindow:u16(b,36);
            if(payload<240||payload>505||value!=payload+4||advertisedWindow<1||advertisedWindow>128||queue<1||queue>advertisedWindow||queue>(v5&&flags==53?64:16)||!v2&&(b[38]!=0||b[39]!=0)||v2&&flags!=5||v3&&flags!=13||(v4||v5)&&flags!=21&&!(flags==53&&advertisedWindow==64))throw new IOException("设备升级窗口或数据容量无效");
            if(v5){
                int f=b[48]&255;if(!magic(b,44,"BLK1")||(f&~15)!=0||b[51]!=0)throw new IOException("设备当前连接信息无效");
                if((f&1)==0){for(int i=48;i<64;i++)if(b[i]!=0)throw new IOException("设备连接状态不一致");}
                if((f&8)!=0){if(b[49]<1||b[49]>3||b[50]<1||b[50]>3)throw new IOException("设备链路模式无效");}else if(b[49]!=0||b[50]!=0)throw new IOException("设备链路模式未确认");
                int tx=u16(b,52),tt=u16(b,54),rx=u16(b,56),rt=u16(b,58),ci=u16(b,60),mtu=u16(b,62);
                if((f&4)!=0){if(tx<27||tx>251||rx<27||rx>251||tt<328||tt>17040||rt<328||rt>17040)throw new IOException("设备链路容量无效");}else if(tx!=0||tt!=0||rx!=0||rt!=0)throw new IOException("设备链路容量尚未确认");
                if(ci!=0&&(ci<6||ci>3200)||mtu!=0&&(mtu<23||mtu>512))throw new IOException("设备连接间隔或MTU无效");
            }
            maxChunk=payload;maxWindow=advertisedWindow;hasGeneration=v4||v5;generation=hasGeneration?word(b,40):0;
        }
        void receiving(int bytes)throws IOException{if(state!=2||error!=0||total!=bytes||accepted>total)throw new IOException("设备尚未确认本次完整升级文件的接收状态");}
        void sameCapacity(Status previous)throws IOException{if(!Arrays.equals(Arrays.copyOfRange(raw,24,Math.min(raw.length,40)),Arrays.copyOfRange(previous.raw,24,Math.min(previous.raw.length,40))))throw new IOException("设备升级能力在传输期间发生变化");}
        // BEGIN may repack the existing fixed arena for the chosen chunk size.
        // Only its physical queue geometry can change before the first DATA.
        void sameOffer(Status previous)throws IOException{if(!Arrays.equals(Arrays.copyOfRange(raw,24,Math.min(raw.length,36)),Arrays.copyOfRange(previous.raw,24,Math.min(previous.raw.length,36))))throw new IOException("设备升级能力在开始接收时发生变化");}
    }
    static Status observedStatus(RecordingClient.Link link,Metrics metrics)throws IOException{Status s=new Status(link.read(STATUS));metrics.statusReads++;metrics.status(s);return s;}
    static String uid(RecordingClient.Link link)throws IOException{return hex(RecordingClient.readPublishedPeer(link).uid());}
    private static String hex(byte[] value){StringBuilder text=new StringBuilder();for(byte b:value)text.append(String.format(Locale.ROOT,"%02x",b&255));return text.toString();}
    static int readiness(RecordingClient.Link link)throws IOException{
        byte[] b=link.read(READINESS);if(b==null||b.length!=24||b[0]!=1||b[1]<0||b[1]>1||((b[3]&255)>100&&(b[3]&255)!=255))throw new IOException("无法确认设备升级条件，未发送内容");
        int flags=u16(b,6);if((flags&~31)!=0||((b[1]==1)!=(flags==0)))throw new IOException("设备升级条件不一致，未发送内容");return flags;
    }
    static void ready(int blockers)throws IOException{
        if(blockers==0)return;String why=(blockers&2)!=0?"设备正在录音或整理存储":(blockers&8)!=0?"设备电量不足":(blockers&4)!=0?"设备供电状态尚未确认":(blockers&16)!=0?"设备充电状态异常":"设备升级存储未就绪";throw new IOException(why+"，请完成当前任务或检查供电后重试；原录音保留。");
    }
    static void sleep(long ms)throws IOException{try{Thread.sleep(ms);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("升级操作已中断，请重新连接核对实际版本。",e);}}
    static Status fresh(RecordingClient.Link link,Status initial,Metrics metrics)throws IOException{
        if(initial.state==3)throw new IOException("设备已保留完整升级文件，正在等待安装；请先核对实际版本。");
        if(initial.state==0&&initial.error==0&&initial.accepted==0&&initial.total==0){ready(readiness(link));return initial;}
        // User explicitly requested a fresh update; an incomplete old receive is
        // retired, never a fully retained file or an existing recording.
        link.write(CONTROL,control(4,0,0,0,0));long deadline=System.nanoTime()+15_000_000_000L;
        while(System.nanoTime()<deadline){Status s=observedStatus(link,metrics);s.sameCapacity(initial);if(s.state==3)throw new IOException("设备已保留完整升级文件，未重新传入");if(s.state==0&&s.error==0&&s.accepted==0&&s.total==0){int blockers=readiness(link);if(blockers==0)return s;if((blockers&~2)!=0)ready(blockers);}sleep(100);}
        throw new IOException("尚未确认旧下载与临时空间释放，请重新连接读取状态。");
    }
    static Status waitAccepted(RecordingClient.Link link,Status begin,long expected,long lower,long upper,long generation,Metrics metrics)throws IOException{
        long deadline=System.nanoTime()+20_000_000_000L;
        while(System.nanoTime()<deadline){Status s=observedStatus(link,metrics);s.sameCapacity(begin);s.receiving((int)expected);if(s.generation!=generation||s.accepted<lower||s.accepted>upper)throw new IOException("设备接收位置或本次升级编号不一致，未继续发送");if(s.accepted==upper)return s;sleep(50);}
        throw new IOException("尚未确认本轮升级数据已保存，停止传入；请重新连接后从头重试。");
    }
    static void waitRetained(RecordingClient.Link link,Status begin,Metrics metrics)throws IOException{
        long deadline=System.nanoTime()+30_000_000_000L;
        while(System.nanoTime()<deadline){
            Status s=observedStatus(link,metrics);s.sameCapacity(begin);
            if(s.generation!=begin.generation||s.total!=begin.total||s.accepted!=begin.total)
                throw new IOException("设备尚未确认本次完整升级文件，不能将传输完成当作安装成功");
            if(s.error!=0||s.state==4)throw new IOException("设备未能提交完整升级文件，请重新连接核对状态");
            if(s.state==3){metrics.retentionConfirmed=true;return;}
            if(s.state!=1&&s.state!=2)throw new IOException("设备升级提交状态无效，请重新连接核对实际版本");
            sleep(50);
        }
        throw new IOException("设备尚未确认完整升级文件已保留，请重新连接核对实际版本");
    }
    /** Same WOC5 generation-bound durable-credit strategy as the existing
     * Windows continuous215 transport. A local write never returns a credit. */
    private static void continuous(RecordingClient.Link link,Status before,Status begin,SystemUpdatePackage pack,long imageCrc,AtomicBoolean cancel,Progress progress,Metrics metrics)throws IOException{
        int chunk=begin.chunk,depth=Math.min(16,Math.min(begin.window,u16(begin.raw,36))),submitted=0,accepted=0;
        if(depth<1)throw new IOException("设备升级队列容量无效");
        metrics.pipelineDepth=depth;metrics.scheduling="continuous_durable_credit";
        while(accepted<pack.image.length){
            if(cancel.get())throw new IOException("已停止传入；请重新连接核对状态，下一次从头传入。");
            long submittedAt=System.nanoTime();
            while(submitted<pack.image.length&&((submitted-accepted+chunk-1)/chunk)<depth){
                int count=Math.min(chunk,pack.image.length-submitted);byte[] packet=new byte[count+4];put32(packet,0,submitted);System.arraycopy(pack.image,submitted,packet,4,count);link.write(DATA,packet);metrics.dataWrites++;submitted+=count;
            }
            metrics.submitNs+=System.nanoTime()-submittedAt;
            long receiptAt=System.nanoTime(),deadline=receiptAt+20_000_000_000L;
            while(true){
                if(cancel.get())throw new IOException("已停止传入，未要求设备安装。");
                if(System.nanoTime()>=deadline)throw new IOException("设备升级耐久队列回执超时，未继续发送");
                Status s;boolean notice=true;
                try{s=new Status(link.await(STATUS,1000));metrics.creditNotices++;metrics.status(s);}
                catch(java.net.SocketTimeoutException timeout){notice=false;metrics.creditFallbackReads++;s=observedStatus(link,metrics);}
                if(notice&&s.generation==before.generation&&s.generation!=begin.generation){metrics.staleNotices++;continue;}
                s.sameCapacity(begin);
                if(notice&&s.generation==begin.generation&&s.state==1&&s.error==0&&s.accepted==0&&s.total==begin.total){metrics.staleNotices++;continue;}
                s.receiving(pack.image.length);
                if(s.generation!=begin.generation||s.accepted<accepted||s.accepted>submitted||(s.accepted!=pack.image.length&&s.accepted%chunk!=0))throw new IOException("设备升级队列游标或编号不一致，未继续发送");
                if(s.accepted>accepted){accepted=(int)s.accepted;break;}
            }
            metrics.receiptNs+=System.nanoTime()-receiptAt;progress.update("transferring",accepted,pack.image.length);
        }
        // One ordered final fence; do not add a host READ/FLUSH every8 packets.
        long receiptAt=System.nanoTime();link.write(CONTROL,control(2,pack.image.length,begin.chunk,begin.window,imageCrc));metrics.flushes++;
        waitAccepted(link,begin,pack.image.length,pack.image.length,pack.image.length,begin.generation,metrics);metrics.receiptNs+=System.nanoTime()-receiptAt;
    }
    public static void transfer(Connector connector,SystemUpdatePackage pack,AtomicBoolean cancel,Progress progress)throws IOException{
        Metrics metrics=new Metrics(pack);
        try{transferMeasured(connector,pack,cancel,progress,metrics);}
        catch(IOException error){metrics.lastError=error.getMessage()==null?"unknown":error.getMessage();throw error;}
        finally{metrics.ended=System.nanoTime();progress.metrics(metrics.json());}
    }
    private static void transferMeasured(Connector connector,SystemUpdatePackage pack,AtomicBoolean cancel,Progress progress,Metrics metrics)throws IOException{
        RecordingClient.Link link=null;boolean beginSent=false,finishAttempted=false;String identity;IOException finishError=null;
        try{
            progress.update("checking",0,pack.image.length);link=connector.connect();identity=uid(link);metrics.uid=identity;progress.identity(identity);
            Status initial=observedStatus(link,metrics);pack.admit(link.read(IDENTITY));initial=fresh(link,initial,metrics);
            String writeMode=link.otaDataWriteMode();boolean credit=writeMode.equals("without_response")&&initial.raw.length==64&&u16(initial.raw,34)==53;
            int payload=Math.min(Math.min(initial.maxChunk,credit?215:505),link.mtu()-7),requestedWindow=Math.min(initial.maxWindow,credit?64:8);if(payload<16)throw new IOException("蓝牙连接容量不足，未开始升级");
            if(credit)link.subscribe(STATUS);
            if(cancel.get())throw new IOException("已取消升级，未发送完整文件。");
            long imageCrc=crc(pack.image,0,pack.image.length);beginSent=true;link.write(CONTROL,control(1,pack.image.length,payload,requestedWindow,imageCrc));
            Status start=observedStatus(link,metrics);long admissionDeadline=System.nanoTime()+20_000_000_000L;
            while(start.state==1&&start.error==0&&System.nanoTime()<admissionDeadline){sleep(50);start=observedStatus(link,metrics);}
            start.sameOffer(initial);start.receiving(pack.image.length);
            if(start.accepted!=0||start.chunk<1||start.chunk>payload||start.window<1||start.window>requestedWindow||start.hasGeneration&&(start.generation==0||start.generation==initial.generation))throw new IOException("设备未确认从头接收本次文件");
            int chunk=start.chunk,window=start.window,accepted=0;
            metrics.mtu=link.mtu();metrics.chunk=chunk;metrics.window=window;metrics.writeMode=writeMode;metrics.pipelineDepth=credit?Math.min(16,Math.min(window,u16(start.raw,36))):window;metrics.scheduling=credit?"continuous_durable_credit":"windowed_durable_receipt";metrics.stage="transferring";metrics.payloadStart=System.nanoTime();progress.metrics(metrics.json());
            if(credit){continuous(link,initial,start,pack,imageCrc,cancel,progress,metrics);accepted=pack.image.length;}
            else while(accepted<pack.image.length){if(cancel.get())throw new IOException("已停止传入；请重新连接核对状态，下一次从头传入。");int offset=accepted;
                long submittedAt=System.nanoTime();
                for(int n=0;n<window&&offset<pack.image.length;n++){int count=Math.min(chunk,pack.image.length-offset);byte[] packet=new byte[4+count];put32(packet,0,offset);System.arraycopy(pack.image,offset,packet,4,count);link.write(DATA,packet);metrics.dataWrites++;offset+=count;}
                metrics.submitNs+=System.nanoTime()-submittedAt;long receiptAt=System.nanoTime();
                link.write(CONTROL,control(2,pack.image.length,chunk,window,imageCrc));metrics.flushes++;waitAccepted(link,start,pack.image.length,accepted,offset,start.generation,metrics);metrics.receiptNs+=System.nanoTime()-receiptAt;accepted=offset;progress.update("transferring",accepted,pack.image.length);
            }
            metrics.payloadEnd=System.nanoTime();metrics.stage="installing";progress.metrics(metrics.json());
            // FINISH is sent exactly once. A reboot can lose its ATT reply;
            // only exact new running identity may subsequently prove success.
            if(cancel.get())throw new IOException("已停止传入，未要求设备安装；下一次从头传入。");
            progress.update("installing",accepted,pack.image.length);finishAttempted=true;
            metrics.finishStart=System.nanoTime();
            try{
                link.write(CONTROL,control(3,pack.image.length,chunk,window,imageCrc));
                // ATT completion only acknowledges the queued control write.
                // The foreground CRC/read-back may still be using this link;
                // disconnecting now aborts it before the pending install exists.
                waitRetained(link,start,metrics);
            }catch(IOException error){finishError=error;metrics.lastError=error.getMessage();}
            finally{metrics.finishEnd=System.nanoTime();progress.metrics(metrics.json());}
        }catch(IOException error){if(link!=null&&beginSent&&!finishAttempted)try{link.write(CONTROL,control(4,0,0,0,0));}catch(IOException ignored){}throw error;}
        finally{if(link!=null)link.close();}
        metrics.stage="verifying";metrics.verifyStart=System.nanoTime();progress.metrics(metrics.json());progress.update("verifying",pack.image.length,pack.image.length);sleep(10000);long deadline=System.nanoTime()+180_000_000_000L;String last=finishError==null?"":finishError.getMessage();
        while(System.nanoTime()<deadline){metrics.verifyAttempts++;try(RecordingClient.Link current=connector.connect()){
            if(!identity.equals(uid(current)))throw new IOException("升级后设备身份不一致，未确认成功");
            if(pack.installed(current.read(IDENTITY))){metrics.installed=true;metrics.stage="complete";progress.update("complete",pack.image.length,pack.image.length);return;}
            last="尚未看到匹配的新程序、资源与临时空间释放";
        }catch(IOException error){metrics.verifyFailures++;last=error.getMessage();metrics.lastError=last;progress.metrics(metrics.json());}sleep(1000);}
        throw new IOException("完整文件已传入，但尚未确认升级成功。请重新连接核对实际版本，不要重复发送完成请求。"+(last==null?"":" "+last));
    }
    public static boolean verify(Connector connector,SystemUpdatePackage pack,String expectedUid)throws IOException{
        if(expectedUid==null||!expectedUid.matches("[0-9a-f]{24}"))throw new IOException("没有本次升级前的设备身份，不能确认结果。");
        try(RecordingClient.Link link=connector.connect()){if(!expectedUid.equals(uid(link)))throw new IOException("设备身份不同，不能确认原升级结果。");return pack.installed(link.read(IDENTITY));}
    }
}

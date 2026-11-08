package com.denzic.companion.mobile;

/** Packet geometry/negotiation only; no hardware rate qualification. */
public final class RecordingPacketBudgetJvmTest {
    public static void main(String[] args)throws Exception {
        for(int maximum:new int[]{248,249,300,494,495,509})for(int mtu:new int[]{139,185,247,251,498,512,517}){
            byte[] status=new byte[116];status[0]=1;RecorderWire.put32(status,4,66754);RecorderWire.put32(status,12,0x57424155L);
            for(int i=0;i<12;i++)status[20+i]=(byte)(i+1);
            System.arraycopy(new byte[]{'C','R','V','2',2,0,32,0},0,status,84,8);
            RecorderWire.put32(status,92,2047);RecorderWire.put64(status,96,7);
            RangeConsumeClientJvmTest.put(status,104,64,2);RangeConsumeClientJvmTest.put(status,106,1024,2);RangeConsumeClientJvmTest.put(status,108,maximum,2);
            RecorderWire.put32(status,112,RecorderWire.crc(status,84,28));
            RecorderWire.Peer peer=RecorderWire.Peer.fromStatus(status);byte[] request=peer.negotiate(23,mtu);
            int value=((request[2]&255)|((request[3]&63)<<8)),expected=maximum<=248?0:Math.min(Math.min(maximum,495),mtu-3);
            if(value!=expected||(request[3]&0xc0)!=0xc0||RecorderWire.u32(request,28)!=RecorderWire.crc(request,0,28))throw new AssertionError("negotiated geometry/flags/CRC");
        }
        if((495+7+250)/251!=2||(509+7+250)/251!=3)throw new AssertionError("framing arithmetic");
        System.out.println("PASS packet495 negotiation:42 peer/MTU combinations preserve legacy/small limits, range flags and CRC; mathematical two251B data payloads versus three for509, hardware speed not measured");
    }
}

package com.denzic.companion.mobile;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** Android adapter of Windows system_ota.rs: same signed CUP3 target, geometry,
 * full-image hashes and post-boot identity. Only resident Boot authenticates
 * the signature before changing either destination. The phone never holds a key. */
public final class SystemUpdatePackage {
    public static final int ARCHIVE_LIMIT=18*1024*1024;
    private static final String TRUSTED_KEY_SHA="3cf111a3787d31d4cc597dbff5dd6f200ccebc350a53494d8b5a7053ec920085";
    final byte[] image,payloadSha;final long target,appAddress;
    public final String id;public final long firmwareVersion,resourceVersion,staticBytes,firmwareBytes,resourceBytes;
    private SystemUpdatePackage(byte[] image,byte[] sha,long target,long address,long fv,long rv,long stat,long fb,long rb)throws IOException{
        this.image=image;payloadSha=sha;this.target=target;appAddress=address;firmwareVersion=fv;resourceVersion=rv;staticBytes=stat;firmwareBytes=fb;resourceBytes=rb;id=hash(image);
    }
    public JSONObject info()throws JSONException{return new JSONObject().put("id",id).put("firmwareVersion",firmwareVersion).put("resourceVersion",resourceVersion).put("firmwareBytes",firmwareBytes).put("resourceBytes",resourceBytes).put("bytes",image.length).put("consistencyChecked",true).put("authentication","Boot在安装前验证签名");}
    private static IOException bad(String why){return new IOException(why+"；尚未发送升级内容。");}
    static long word(byte[] b,int p)throws IOException{if(b==null||p<0||p>b.length-4)throw bad("升级信息不完整");return (b[p]&255L)|((b[p+1]&255L)<<8)|((b[p+2]&255L)<<16)|((b[p+3]&255L)<<24);}
    static void put32(byte[] b,int p,long value){for(int i=0;i<4;i++)b[p+i]=(byte)(value>>>(i*8));}
    static int u16(byte[] b,int p){return (b[p]&255)|((b[p+1]&255)<<8);}
    static boolean magic(byte[] b,int at,String value){if(b==null||at<0||at+value.length()>b.length)return false;for(int i=0;i<value.length();i++)if(b[at+i]!=(byte)value.charAt(i))return false;return true;}
    static long crc(byte[] b,int at,int length){CRC32 crc=new CRC32();crc.update(b,at,length);return crc.getValue();}
    static byte[] digest(byte[] b,int at,int size)throws IOException{try{MessageDigest d=MessageDigest.getInstance("SHA-256");d.update(b,at,size);return d.digest();}catch(Exception e){throw new IOException("无法校验升级内容",e);}}
    public static String hash(byte[] b)throws IOException{StringBuilder s=new StringBuilder();for(byte value:digest(b,0,b.length))s.append(String.format(Locale.ROOT,"%02x",value&255));return s.toString();}
    private static String hash(byte[] b,int at,int count)throws IOException{StringBuilder s=new StringBuilder();for(byte value:digest(b,at,count))s.append(String.format(Locale.ROOT,"%02x",value&255));return s.toString();}
    private static long number(JSONObject json,String name)throws Exception{
        Object v=json.get(name);if(!(v instanceof Number))throw bad("升级包字段格式不正确："+name);double d=((Number)v).doubleValue();long n=((Number)v).longValue();if(d!=n||n<0||n>0xffffffffL)throw bad("升级包数值越界："+name);return n;
    }
    private static String text(JSONObject json,String name)throws Exception{Object v=json.get(name);if(!(v instanceof String))throw bad("升级包字段格式不正确："+name);return (String)v;}
    private static byte[] readBounded(InputStream in,int limit)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[32768];int n;while((n=in.read(buffer))!=-1){if(n>limit-out.size())throw bad("升级包超过支持的大小");out.write(buffer,0,n);}return out.toByteArray();}
    /** Official mobile ZIP contains exactly manifest + the original signed file;
     * it is an envelope around the unchanged Windows/device package, not another updater format. */
    public static SystemUpdatePackage open(InputStream archive)throws IOException{
        try{
            Map<String,byte[]> files=new HashMap<>();int total=0;
            try(ZipInputStream zip=new ZipInputStream(archive)){ZipEntry e;while((e=zip.getNextEntry())!=null){
                String name=e.getName();if(e.isDirectory()||name.isEmpty()||name.indexOf('/')>=0||name.indexOf('\\')>=0||name.indexOf(':')>=0||name.equals(".")||name.equals("..")||files.containsKey(name)||files.size()>=2)throw bad("升级包目录不符合要求");
                byte[] bytes=readBounded(zip,name.equals("ota_manifest.json")?65536:ARCHIVE_LIMIT-total);total+=bytes.length;if(total>ARCHIVE_LIMIT)throw bad("升级包过大");files.put(name,bytes);
            }}
            byte[] json=files.get("ota_manifest.json");if(json==null||files.size()!=2)throw bad("请选择包含完整固件和资源的官方升级ZIP");
            JSONObject manifest=new JSONObject(new String(json,StandardCharsets.UTF_8));String filename=text(manifest,"file");byte[] image=files.get(filename);if(image==null||filename.equals("ota_manifest.json"))throw bad("升级文件与目录记录不符");return validate(manifest,image);
        }catch(IOException e){throw e;}catch(Exception e){throw new IOException("升级包无法读取或校验；设备和原录音保持不变。",e);}
    }
    static SystemUpdatePackage validate(JSONObject d,byte[] file)throws Exception{
        if(!text(d,"schema").equals("companion.wba.simple-ota.v3")||!text(d,"capability").equals("companion_simple_ota_v3")||!text(d,"mcu").equals("STM32WBA55CEU6")||!text(d,"public_key_sha256").equals(TRUSTED_KEY_SHA)||number(d,"key_id")!=0x44455631L||!Boolean.FALSE.equals(d.get("download_resume")))throw bad("升级包协议或信任标识不匹配");
        String hardware=text(d,"hardware_revision");boolean nor24=hardware.equals("COMPANION-WBA55CE-V1.1-F24-N0");if(!nor24&&!hardware.equals("COMPANION-WBA55CE-V1.1"))throw bad("升级包不适用于当前支持的录音卡硬件");
        long target=nor24?0x45335643L:0x45315643L,address=nor24?0x08006000L:0x08008000L,capacity=nor24?499712:475136;
        if(nor24||d.has("board_target")||d.has("app_address")||d.has("internal_flash_geometry")){
            JSONObject g=d.getJSONObject("internal_flash_geometry");long boot=address-0x08000000L,nvm=524288-boot-capacity;
            if(number(d,"board_target")!=target||number(d,"app_address")!=address||number(g,"board_target")!=target||number(g,"app_address")!=address||number(g,"app_bytes")!=capacity||number(g,"boot_bytes")!=boot||number(g,"nvm_bytes")!=nvm||number(g,"flash_bytes")!=524288||number(g,"nvm_offset")!=524288-nvm)throw bad("升级包的内部存储布局不一致");
        }
        if(file.length<184||file.length>176+capacity+16777216||file.length!=number(d,"bytes")||!hash(file).equals(text(d,"sha256")))throw bad("升级文件长度或完整校验不符");
        if(!magic(file,0,"WUM1")||file[4]!=1||file[5]!=1||file[6]!=3||file[7]!=0||word(file,8)!=0x41425743L||word(file,12)!=target||word(file,28)!=file.length-144||word(file,32)!=crc(file,144,file.length-144)||!Arrays.equals(Arrays.copyOfRange(file,36,68),digest(file,144,file.length-144))||file[68]!=1||file[69]!=0||file[70]!=0||file[71]!=0||word(file,72)!=0x44455631L||word(file,140)!=crc(file,0,140)||!magic(file,144,"CUP3")||file[148]!=3||file[149]!=0||file[150]!=32||file[151]!=0||word(file,172)!=address)throw bad("升级包签名封装、目标或内容不匹配");
        long fv=word(file,152),rv=word(file,156),fb=word(file,160),rb=word(file,164),stat=word(file,168);
        if(word(file,16)!=fv||fv!=number(d,"firmware_version")||rv!=number(d,"resource_version")||fb!=number(d,"firmware_bytes")||rb!=number(d,"resource_bytes")||stat!=number(d,"static_bytes")||fb<8||fb>capacity||rb!=stat||stat<8192||stat%4096!=0||stat>16777216-131072||rv==0||file.length!=176+fb+rb||file.length>16777216-stat-131072||!hash(file,144,file.length-144).equals(text(d,"payload_sha256")))throw bad("升级包版本或存储边界不符");
        long sp=word(file,176),reset=word(file,180);boolean stack=sp%8==0&&(sp>0x20000000L&&sp<=0x20008000L||sp>0x20010000L&&sp<=0x20020000L);
        if(!stack||(reset&1)==0||(reset&~1L)<address||(reset&~1L)>=address+fb)throw bad("固件入口超出应用范围");
        return new SystemUpdatePackage(file,Arrays.copyOfRange(file,36,68),target,address,fv,rv,stat,fb,rb);
    }
    private long identityTarget(byte[] identity)throws IOException{
        if(identity!=null&&identity.length==56&&magic(identity,0,"WSI3"))return 0x45315643L;
        if(identity!=null&&identity.length==60&&magic(identity,0,"WSI4")){long t=word(identity,56);if(t==0x45315643L||t==0x45335643L)return t;}throw bad("设备尚未提供有效运行版本与布局");
    }
    public void admit(byte[] identity)throws IOException{
        if(identityTarget(identity)!=target)throw bad("升级包与设备的内部存储布局不同");
        if(word(identity,20)!=1)throw bad("设备尚未准备好升级");
        if(word(identity,12)!=staticBytes)throw bad("升级包与设备资源边界不同");
        if(firmwareVersion<=word(identity,4)||resourceVersion<word(identity,8))throw bad("升级包版本不高于当前版本，或会降低资源版本");
    }
    public boolean installed(byte[] identity){try{return identityTarget(identity)==target&&word(identity,4)==firmwareVersion&&word(identity,8)==resourceVersion&&word(identity,12)==staticBytes&&word(identity,16)==0&&word(identity,20)==1&&Arrays.equals(Arrays.copyOfRange(identity,24,56),payloadSha);}catch(IOException e){return false;}}
}

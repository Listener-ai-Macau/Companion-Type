package com.denzic.companion.app;
import java.util.*;
public final class SpeechPcmConverterTest {
 static short[] convert(float[] samples,int rate,int channels,int packet)throws Exception{List<Short> values=new ArrayList<>();SpeechPcmConverter c=new SpeechPcmConverter(rate,channels,values::add);for(int i=0;i<samples.length;i+=packet){float[] part=Arrays.copyOfRange(samples,i,Math.min(samples.length,i+packet));c.process(part,part.length);}c.finish();short[] out=new short[values.size()];for(int i=0;i<out.length;i++)out[i]=values.get(i);return out;}
 static double energy(short[] values){double sum=0;for(int i=300;i<values.length;i++)sum+=values[i]*(double)values[i];return Math.sqrt(sum/Math.max(1,values.length-300));}
 public static void main(String[] args)throws Exception {
  float[] mono=new float[48000];for(int i=0;i<mono.length;i++)mono[i]=(float)(Math.sin(i*2*Math.PI*1000/48000)*.5);short[] whole=convert(mono,48000,1,48000),chunked=convert(mono,48000,1,254);if(whole.length!=16000||!Arrays.equals(whole,chunked))throw new AssertionError("Resampling depends on codec packet boundaries");
  float[] high=new float[48000];for(int i=0;i<high.length;i++)high[i]=(float)(Math.sin(i*2*Math.PI*12000/48000)*.5);if(energy(convert(high,48000,1,256))>energy(whole)*.2)throw new AssertionError("Downsampling aliases above speech band");
  float[] opposite=new float[32000];for(int i=0;i<16000;i++){opposite[i*2]=(float)(Math.sin(i*.21)*.5);opposite[i*2+1]=-opposite[i*2];}if(energy(convert(opposite,16000,2,512))<5000)throw new AssertionError("Opposite-phase stereo was erased");
  float[] low=new float[8000];Arrays.fill(low,.25f);if(convert(low,8000,1,157).length!=16000)throw new AssertionError("Low-rate conversion lost end samples");float[] invalid={Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY,0};convert(invalid,16000,1,4);
  System.out.println("PASS streaming packet invariance, anti-aliasing, opposite-phase stereo and exact low-rate duration; no speech/model quality claim.");
 }
}

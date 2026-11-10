package com.denzic.companion.app;
import java.io.IOException;

/** Streaming counterpart of the desktop speech converter; original media remains intact. */
final class SpeechPcmConverter {
 interface Sink {void write(short sample)throws IOException;}
 private final int rate,channels;private final Sink sink;private final LowPass[] filters;
 private long frames,output;private double previous;private boolean invertRight;
 SpeechPcmConverter(int rate,int channels,Sink sink)throws IOException {
  if(rate<8000||rate>192000||channels<1||channels>8)throw new IOException("暂不支持这个音频采样格式。");
  this.rate=rate;this.channels=channels;this.sink=sink;filters=rate>16000?new LowPass[]{new LowPass(rate,.5411961),new LowPass(rate,1.306563)}:null;
 }
 void process(float[] samples,int length)throws IOException {
  if(length%channels!=0)throw new IOException("音频数据帧不完整。");
  if(channels==2){double left=0,right=0,dot=0;for(int i=0;i<length;i+=2){double l=finite(samples[i]),r=finite(samples[i+1]);left+=l*l;right+=r*r;dot+=l*r;}if(left>1e-8&&right>1e-8){double correlation=dot/Math.sqrt(left*right);if(correlation<-.90)invertRight=true;else if(correlation>-.70)invertRight=false;}}
  for(int at=0;at<length;at+=channels){double value=0;for(int channel=0;channel<channels;channel++){double x=finite(samples[at+channel]);value+=channels==2&&channel==1&&invertRight?-x:x;}value/=channels;
   if(filters!=null)for(LowPass filter:filters)value=filter.process(value);
   long index=frames++;
   while(output*(long)rate<=index*16000L){double source=output*(double)rate/16000,part=index==0?1:source-(index-1);emit(index==0?value:previous+(value-previous)*Math.max(0,Math.min(1,part)));}
   previous=value;
  }
 }
 void finish()throws IOException {long expected=(frames*16000L+rate-1)/rate;while(output<expected)emit(previous);}
 long outputSamples(){return output;}
 private void emit(double value)throws IOException {sink.write((short)Math.round(Math.max(-1,Math.min(1,value))*32767));output++;}
 private static double finite(float value){return Float.isFinite(value)?value:0;}
 private static final class LowPass {
  final double b0,b1,b2,a1,a2;double x1,x2,y1,y2;
  LowPass(int rate,double q){double w=2*Math.PI*Math.min(7000,rate*.45)/rate,alpha=Math.sin(w)/(2*q),a0=1+alpha;b0=(1-Math.cos(w))/(2*a0);b1=(1-Math.cos(w))/a0;b2=b0;a1=-2*Math.cos(w)/a0;a2=(1-alpha)/a0;}
  double process(double x){double y=b0*x+b1*x1+b2*x2-a1*y1-a2*y2;x2=x1;x1=x;y2=y1;y1=y;return y;}
 }
}

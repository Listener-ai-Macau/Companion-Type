//! Existing-hardware desktop feasibility core. No OS input, disk or BLE.
//! Reuses unchanged x-io Fusion for Earth-frame gravity removal.
//! Causal stroke integration/zero-velocity decisions are Companion adapters;
//! the upstream Gait-Tracking end-of-stroke interpolation is NONCAUSAL and is
//! deliberately not represented as a real-time mouse implementation.
use super::{fusion,Point};
use serde::Serialize;

#[derive(Clone,Copy,Debug)]
pub struct Raw {pub sequence:u32,pub sensor_ms:u32,pub accel_mg:[f64;3],pub gyro_dps:[f64;3]}
impl Raw {
    pub fn parse(p:&[u8])->Result<Self,&'static str>{
        if p.len()!=32||&p[..4]!=b"CIM1"||p[4]!=5||p[5]!=3||p[6]&!3!=0{return Err("invalid raw CIM5");}
        let mut crc=0xffff_ffffu32;
        for byte in &p[..28]{crc^=*byte as u32;for _ in 0..8{crc=(crc>>1)^((0u32.wrapping_sub(crc&1))&0xedb8_8320);}}
        if !crc!=u32::from_le_bytes(p[28..32].try_into().unwrap()){return Err("raw CRC mismatch");}
        let value=|i|i16::from_le_bytes(p[i..i+2].try_into().unwrap())as f64;
        Ok(Self{sequence:u32::from_le_bytes(p[8..12].try_into().unwrap()),sensor_ms:u32::from_le_bytes(p[12..16].try_into().unwrap()),
            accel_mg:std::array::from_fn(|i|value(16+2*i)),gyro_dps:std::array::from_fn(|i|value(22+2*i)/100.)})
    }
}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct State {pub calibrated:bool,pub moving:bool,pub clutched:bool,pub gaps:u64,pub samples:u64,pub velocity_mps:[f64;2],pub position_m:[f64;2],pub linear_mps2:[f64;3]}
pub struct Desktop {
    fusion:fusion::Fusion,last:Option<(u32,u32)>,count:u32,start_ms:Option<u32>,
    accel_sum:[f64;3],gyro_sum:[f64;3],gyro_bias:[f64;3],rest_up:[f64;3],earth_bias:[f64;3],
    filtered:[f64;2],quiet:f64,stroke:f64,braking:bool,
    pub state:State,
}
impl Default for Desktop {
    fn default()->Self{Self{fusion:fusion::Fusion::default(),last:None,count:0,start_ms:None,accel_sum:[0.;3],gyro_sum:[0.;3],gyro_bias:[0.;3],rest_up:[0.,0.,1.],earth_bias:[0.;3],filtered:[0.;2],quiet:0.,stroke:0.,braking:false,state:State::default()}}
}
impl Desktop {
    fn stop(&mut self){self.state.moving=false;self.state.velocity_mps=[0.;2];self.filtered=[0.;2];self.quiet=0.;self.stroke=0.;self.braking=false;}
    pub fn tap(&mut self){self.stop();self.state.clutched=true;}
    pub fn sample(&mut self,s:Raw)->Point {
        let dt=if let Some((sequence,ms))=self.last{
            let n=s.sequence.wrapping_sub(sequence);
            if n==0||n>=0x8000_0000{return Point::default();}
            let dt=s.sensor_ms.wrapping_sub(ms)as f64/1000.;
            if n!=1||dt>0.05||dt<=0.{self.state.gaps+=1;self.stop();self.state.clutched=true;self.last=Some((s.sequence,s.sensor_ms));return Point::default();}
            dt
        }else{0.01};
        self.last=Some((s.sequence,s.sensor_ms));self.state.samples+=1;
        let norm=s.accel_mg.iter().map(|x|x*x).sum::<f64>().sqrt();
        if !self.state.calibrated {
            if !(850. ..=1150.).contains(&norm)||s.gyro_dps.iter().any(|x|x.abs()>3.){
                self.start_ms=None;self.count=0;self.accel_sum=[0.;3];self.gyro_sum=[0.;3];return Point::default();
            }
            let start=*self.start_ms.get_or_insert(s.sensor_ms);self.count+=1;
            for i in 0..3{self.accel_sum[i]+=s.accel_mg[i];self.gyro_sum[i]+=s.gyro_dps[i];}
            if s.sensor_ms.wrapping_sub(start)<1000||self.count<80{return Point::default();}
            let accel=self.accel_sum.map(|x|x/self.count as f64);self.gyro_bias=self.gyro_sum.map(|x|x/self.count as f64);
            let n=accel.iter().map(|x|x*x).sum::<f64>().sqrt();
            self.rest_up=accel.map(|x|x/n);self.fusion.align(accel);
            let (earth,_)=self.fusion.desktop_step([0.;3],accel,dt,true);self.earth_bias=earth;
            self.state.calibrated=true;self.stop();return Point::default();
        }
        let rates=std::array::from_fn(|i|s.gyro_dps[i]-self.gyro_bias[i]);
        let (earth,up)=self.fusion.desktop_step(rates,s.accel_mg,dt,!self.state.moving);
        let linear=std::array::from_fn(|i|earth[i]-self.earth_bias[i]);self.state.linear_mps2=linear;
        let agreement=(0..3).map(|i|up[i]*self.rest_up[i]).sum::<f64>();
        // A desk stroke keeps the original plane. Tilt/lift/tap candidates
        // suspend displacement; no pretense of knowing table contact from IMU.
        if agreement<0.978||linear[2].abs()>1.5||norm<650.||norm>1350. {
            self.stop();self.state.clutched=true;return Point::default();
        }
        let planar=linear[0].hypot(linear[1]);let quiet=planar<0.055&&rates.iter().all(|x|x.abs()<2.);
        if self.state.clutched {
            self.quiet=if quiet{self.quiet+dt}else{0.};
            if self.quiet>=0.2{self.state.clutched=false;self.stop();}
            return Point::default();
        }
        if !self.state.moving {
            // Adapt residual bias only while classified at rest, never from
            // the middle of a constant-velocity stroke.
            if quiet{for i in 0..3{self.earth_bias[i]+=(earth[i]-self.earth_bias[i])*(dt/2.).min(1.);}}
            if planar<0.10{return Point::default();}
            self.state.moving=true;self.stroke=0.;self.braking=false;
        }
        self.stroke+=dt;
        if self.stroke>2.0{self.stop();self.state.clutched=true;return Point::default();}
        let old=self.state.velocity_mps;
        for i in 0..2 {
            self.filtered[i]+=(linear[i]-self.filtered[i])*(dt/(0.02+dt));
            if old[i]*self.filtered[i]<0.&&self.filtered[i].abs()>0.10{self.braking=true;}
            self.state.velocity_mps[i]=(old[i]+self.filtered[i]*dt).clamp(-0.6,0.6);
        }
        self.quiet=if quiet{self.quiet+dt}else{0.};
        // Rest must follow braking, or have a negligible residual velocity.
        // Quiet acceleration alone cannot distinguish constant speed from rest.
        if self.quiet>=0.12&&(self.braking||self.state.velocity_mps[0].hypot(self.state.velocity_mps[1])<0.005){
            self.stop();return Point::default();
        }
        let delta=Point{x:(old[0]+self.state.velocity_mps[0])*0.5*dt,y:(old[1]+self.state.velocity_mps[1])*0.5*dt};
        self.state.position_m[0]+=delta.x;self.state.position_m[1]+=delta.y;delta
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn raw(n:u32,x:f64,y:f64)->Raw{Raw{sequence:n+1,sensor_ms:n*10,accel_mg:[x,y,1000.],gyro_dps:[0.;3]}}
    fn ready()->Desktop{let mut d=Desktop::default();for n in 0..=120{d.sample(raw(n,0.,0.));}assert!(d.state.calibrated);d}
    #[test]fn c_raw_fixture_and_crc(){let h="43494d310503020108000000f0ffffff0100feffe8036b03589eff7f252106ed";let p=(0..h.len()).step_by(2).map(|i|u8::from_str_radix(&h[i..i+2],16).unwrap()).collect::<Vec<_>>();let s=Raw::parse(&p).unwrap();assert_eq!(s.accel_mg,[1.,-2.,1000.]);assert_eq!(s.gyro_dps,[8.75,-250.,327.67]);}
    #[test]fn stationary_noise_does_not_accumulate_displacement(){let mut d=ready();for n in 121..6121{let noise=((n*7919)%5)as f64-2.;d.sample(raw(n,noise,-noise));}assert!(d.state.position_m[0].hypot(d.state.position_m[1])<0.0001);}
    #[test]fn physical_stroke_direction_and_constant_velocity_are_not_discarded(){
        let mut d=ready();let mut cruise_start=0.;let mut cruise_end=0.;
        for n in 121..231{let a=if n<141{100.}else if n<211{0.}else{-100.};d.sample(raw(n,a,0.));if n==141{cruise_start=d.state.position_m[0];}if n==210{cruise_end=d.state.position_m[0];}}
        assert!(cruise_end-cruise_start>0.09,"constant-speed displacement {:?}",d.state);
        assert!(d.state.position_m[0]>0.10&&d.state.position_m[1].abs()<0.005);
        for n in 231..281{d.sample(raw(n,0.,0.));}assert!(!d.state.moving);
    }
    #[test]fn missing_sample_and_vertical_lift_cannot_be_integrated_as_a_desk_jump(){
        let mut d=ready();d.sample(raw(121,100.,0.));let before=d.state.position_m;
        d.sample(raw(200,0.,0.));assert_eq!(d.state.position_m,before);assert!(d.state.clutched);
        let mut d=ready();let mut s=raw(121,0.,0.);s.accel_mg[2]=1500.;assert_eq!(d.sample(s),Point::default());assert!(d.state.clutched);
    }
}

//! Personal front-corner contacts. Hardware TAP supplies a candidate; raw
//! motion alone never clicks. Segment/deduplicate before affecting the stroke.
use super::{contact_dtw as dtw,desktop::Raw,Point};
use serde::{Deserialize,Serialize};
use std::collections::VecDeque;

#[derive(Clone,Copy,Debug,Deserialize,Serialize,PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Side {Left,Right}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Profile {
    pub schema:u8,pub left:dtw::Series,pub right:dtw::Series,
    pub left_threshold:f64,pub right_threshold:f64,
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]fn fifo_contact_window_keeps_the_old_profile_time_scale_and_rejects_loss(){
        let mut c=Contact::new(None);
        for n in 0..300u32{
            let ticks=n*96;let ms=ticks as f64*0.025;
            c.sample(Raw{frequency_fine:0,sequence:n+1,sensor_ms:ticks/40,sensor_sub_ms_25us:(ticks%40)as u8,continuity_generation:1,high_rate:true,wide_gyro:true,accel_mg:[ms*2.,0.,1000.],gyro_dps:[ms*0.1,0.,0.]});
        }
        assert!(c.raw.front().unwrap().sensor_ms<=150,"the pre-contact baseline must remain available");
        let grid=contact_grid(&c.raw,500).unwrap();assert_eq!(grid.len(),19);
        for (n,s)in grid.iter().enumerate(){let at=470.+n as f64*10.;assert!((s.accel_mg[0]-at*2.).abs()<1e-9);assert!((s.gyro_dps[0]-at*0.1).abs()<1e-9);}
        c.contact(500,0.7,Point::default());assert!(c.pending());
        let mut s=*c.raw.back().unwrap();s.sequence+=1;s.sensor_ms+=2;s.continuity_generation=2;c.sample(s);
        assert_eq!(c.raw.len(),1);assert!(!c.pending(),"old contacts cannot cross a missing FIFO interval");
    }
    #[test]
    #[ignore="Requires the Owner-labelled local capture; never bundles private samples in the product"]
    fn physical_front_corners_match_upstream_and_deduplicate_the_actual_rebounds(){
        let dir=std::path::PathBuf::from(std::env::var("COMPANION_CONTACT_CAPTURE").expect("labelled capture directory"));
        let text=std::fs::read_to_string(dir.join("grt-impact-reference/input.txt")).unwrap();
        let mut values=text.split_whitespace();let count:usize=values.next().unwrap().parse().unwrap();
        let mut series=vec![];
        for _ in 0..count{
            let rows:usize=values.next().unwrap().parse().unwrap();assert_eq!(values.next(),Some("6"));
            let matrix=(0..rows).map(|_|std::array::from_fn(|_|values.next().unwrap().parse::<f64>().unwrap())).collect();
            series.push(dtw::normalize(matrix));
        }
        let text=std::fs::read_to_string(dir.join("grt-impact-reference/distances.txt")).unwrap();
        let expected:Vec<f64>=text.split_whitespace().map(|x|x.parse().unwrap()).collect();
        for i in 0..count{for j in 0..count{
            let actual=dtw::distance(&series[i],&series[j]);let target=expected[i*count+j];
            assert!((actual-target).abs()<1e-8,"GRT parity({i},{j}): {actual} != {target}");
        }}
        let windows:serde_json::Value=serde_json::from_str(&std::fs::read_to_string(dir.join("windows.json")).unwrap()).unwrap();
        let mut c=Contact::new(None);let mut impacts=vec![];
        // Every actual event is replayed; equal physical groups are not
        // silently removed before checking the product's duplicate logic.
        for w in windows.as_array().unwrap(){
            c.raw.clear();
            for s in w["samples"].as_array().unwrap(){c.sample(Raw{
                frequency_fine:0,sensor_sub_ms_25us:0,continuity_generation:0,high_rate:false,wide_gyro:false,sequence:s["sequence"].as_u64().unwrap()as u32,sensor_ms:s["sensorMs"].as_u64().unwrap()as u32,
                accel_mg:std::array::from_fn(|i|s["accelMg"][i].as_f64().unwrap()),gyro_dps:std::array::from_fn(|i|s["gyroDps"][i].as_f64().unwrap()),
            });}
            let ms=w["sensorMs"].as_u64().unwrap()as u32;
            let f=c.feature(ms).expect("actual raw shock window");impacts.push((w["side"].as_str().unwrap(),f.onset,f.series));
        }
        let unique:Vec<_>=impacts.iter().enumerate().filter(|(i,(_,onset,_))|*i==0||onset.wrapping_sub(impacts[i-1].1)>35).map(|(_,x)|x).collect();
        assert_eq!(unique.len(),6,"no amplitude/side-specific retuning to discard a hard example");
        let left=unique.iter().filter(|x|x.0=="leftFront").map(|x|x.2.clone()).collect::<Vec<_>>();
        let right=unique.iter().filter(|x|x.0=="rightFront").map(|x|x.2.clone()).collect::<Vec<_>>();
        let (left,left_threshold)=dtw::train(&left).unwrap();let (right,right_threshold)=dtw::train(&right).unwrap();
        let profile=Profile{schema:2,left,right,left_threshold,right_threshold};profile.validate().unwrap();
        for (side,_,s) in &impacts{assert_eq!(profile.classify(s),Some(if *side=="leftFront"{Side::Left}else{Side::Right}));}
        // Replay causal raw/control ordering into a calibrated Contact. No
        // native OS input or fabricated microphone/pose data is involved.
        let mut raw=std::collections::BTreeMap::new();let mut events=vec![];
        for w in windows.as_array().unwrap(){
            events.push(w["sensorMs"].as_u64().unwrap()as u32);
            for s in w["samples"].as_array().unwrap(){raw.insert(s["sensorMs"].as_u64().unwrap()as u32,Raw{
                frequency_fine:0,sensor_sub_ms_25us:0,continuity_generation:0,high_rate:false,wide_gyro:false,sequence:s["sequence"].as_u64().unwrap()as u32,sensor_ms:s["sensorMs"].as_u64().unwrap()as u32,
                accel_mg:std::array::from_fn(|i|s["accelMg"][i].as_f64().unwrap()),gyro_dps:std::array::from_fn(|i|s["gyroDps"][i].as_f64().unwrap()),
            });}
        }
        let mut c=Contact::new(Some(profile));let mut clicks=vec![];let mut next=0;
        for (ms,s) in raw{
            c.sample(s);let now=ms as f64/1000.;
            while next<events.len()&&events[next]<=ms{c.contact(events[next],now,Point::default());next+=1;}
            clicks.extend(c.poll(now));
        }
        assert_eq!(clicks.iter().map(|x|x.0).collect::<Vec<_>>(),vec![Side::Left,Side::Left,Side::Left,Side::Right,Side::Right,Side::Right]);
        assert_eq!(c.status.suppressed_rebounds,4);assert_eq!(c.status.uncertain,0);assert_eq!(c.status.missed_windows,0);
        println!("Actual10 TAP events ->6 distinct corner clicks,4 physical echoes suppressed;36 GRT distances match. Small personal sample, not qualification.");
    }
}
impl Profile {
    pub fn validate(&self)->Result<(),&'static str>{
        if self.schema!=2 || [&self.left,&self.right].iter().any(|s|!(8..=dtw::MAX_ROWS).contains(&s.len())||!s.iter().flatten().all(|x|x.is_finite())) ||
            ![self.left_threshold,self.right_threshold].iter().all(|x|x.is_finite()&&*x>=0.) ||
            dtw::distance(&self.left,&self.right)<=self.left_threshold.max(self.right_threshold) {
            return Err("左右前角的敲击还没有分开，请重新校准。");
        }Ok(())
    }
    fn classify(&self,f:&[[f64;6]])->Option<Side>{
        let l=dtw::distance(&self.left,f);let r=dtw::distance(&self.right,f);
        // GRT's default is useNullRejection=false. The reliable LSM6DSO TAP
        // already decides whether a contact happened; this stage selects its
        // side. A radius fitted to only three examples rejected14/14 genuine
        // Owner contacts. Keep stored thresholds for provenance/compatibility,
        // without silently enabling the upstream optional rejection mode.
        if l.is_finite()&&l<r{Some(Side::Left)}
        else if r.is_finite()&&r<l{Some(Side::Right)}else{None}
    }
}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Status {
    pub learning:Option<Side>,pub left_samples:usize,pub right_samples:usize,
    pub calibrated:bool,pub missed_windows:u64,pub uncertain:u64,pub last_side:Option<Side>,
    pub suppressed_rebounds:u64,
}
struct Pending {ms:u32,at:f64,point:Point,learning:Option<Side>}
struct Impact {onset:u32,series:dtw::Series}
pub struct Contact {
    raw:VecDeque<Raw>,pending:VecDeque<Pending>,left:Vec<dtw::Series>,right:Vec<dtw::Series>,
    last_impact:Option<u32>,profile:Option<Profile>,pub status:Status,
}
impl Contact {
    pub fn new(profile:Option<Profile>)->Self{
        let calibrated=profile.is_some();Self{raw:VecDeque::with_capacity(64),pending:VecDeque::new(),
            left:vec![],right:vec![],last_impact:None,profile,status:Status{calibrated,..Status::default()}}
    }
    pub fn is_active(&self)->bool{self.profile.is_some()||self.status.learning.is_some()}
    pub fn clear_stream(&mut self){self.raw.clear();self.pending.clear();self.last_impact=None;}
    pub fn discard_pending(&mut self){self.pending.clear();}
    pub fn pending(&self)->bool{!self.pending.is_empty()}
    pub fn reanchor(&mut self,point:Point){for p in &mut self.pending{p.point=point;}}
    pub fn cancel(&mut self){self.status.learning=None;self.pending.clear();}
    pub fn learn(&mut self,side:Side){
        if side==Side::Left{self.left.clear();self.right.clear();self.status.left_samples=0;self.status.right_samples=0;}
        self.pending.clear();self.last_impact=None;self.status.learning=Some(side);
    }
    pub fn finish(&mut self)->Result<Profile,&'static str>{
        let (left,left_threshold)=dtw::train(&self.left).ok_or("请先在左前和右前各轻敲三次，再保存校准。")?;
        let (right,right_threshold)=dtw::train(&self.right).ok_or("请先在左前和右前各轻敲三次，再保存校准。")?;
        let profile=Profile{schema:2,left,right,left_threshold,right_threshold};profile.validate()?;
        self.profile=Some(profile.clone());self.status.calibrated=true;self.cancel();Ok(profile)
    }
    pub fn sample(&mut self,s:Raw){
        if !s.accel_mg.iter().chain(s.gyro_dps.iter()).all(|x|x.is_finite()){return;}
        if self.raw.back().is_some_and(|p|{let n=s.sequence.wrapping_sub(p.sequence);n==0||n>=0x8000_0000}){return;}
        if self.raw.back().is_some_and(|p|p.continuity_generation!=s.continuity_generation||p.high_rate!=s.high_rate){self.clear_stream();}
        // Preserve the same >600ms evidence at417Hz. The old64-frame ring
        // retained only154ms, erasing the baseline before contact evaluation.
        let capacity=if s.high_rate{320}else{64};
        while self.raw.len()>=capacity{self.raw.pop_front();}self.raw.push_back(s);
    }
    pub fn contact(&mut self,ms:u32,now:f64,point:Point){
        if self.pending.len()<8{self.pending.push_back(Pending{ms,at:now,point,learning:self.status.learning});}
        else{self.status.missed_windows+=1;}
    }
    fn feature(&self,ms:u32)->Option<Impact>{
        let relative=|s:&Raw|s.sensor_ms.wrapping_sub(ms)as i32;
        let baseline:Vec<_>=self.raw.iter().filter(|s|(-300..=-180).contains(&relative(s))).collect();
        if baseline.len()<6{return None;}
        let a:[f64;3]=std::array::from_fn(|i|baseline.iter().map(|s|s.accel_mg[i]).sum::<f64>()/baseline.len()as f64);
        let g:[f64;3]=std::array::from_fn(|i|baseline.iter().map(|s|s.gyro_dps[i]).sum::<f64>()/baseline.len()as f64);
        let active=|s:&Raw|s.accel_mg.iter().zip(a).map(|(x,y)|(x-y).powi(2)).sum::<f64>()>=500f64.powi(2)||
            s.gyro_dps.iter().zip(g).map(|(x,y)|(x-y).powi(2)).sum::<f64>()>=50f64.powi(2);
        // Platform segmentation, identical for both sides. A new burst needs
        // an observed quiet interval; ringing events retain the same onset.
        let mut onset=None;let mut previous_active=None;
        for s in self.raw.iter().filter(|s|(-160..=10).contains(&relative(s))){
            if active(s){
                if previous_active.is_none_or(|t|s.sensor_ms.wrapping_sub(t)>30){onset=Some(s.sensor_ms);}
                previous_active=Some(s.sensor_ms);
            }
        }
        let onset=onset?;
        if (self.raw.back()?.sensor_ms.wrapping_sub(onset)as i32)<150{return None;}
        let mut window:Vec<_>=self.raw.iter().filter(|s|(-30..=150).contains(&(s.sensor_ms.wrapping_sub(onset)as i32))).collect();
        // Personal DTW profiles are100Hz waveforms. Resample ONLY this host
        // classification view, never the raw stream or motion integration.
        let resampled;
        if self.raw.back()?.high_rate{
            resampled=contact_grid(&self.raw,onset)?;window=resampled.iter().collect();
        }
        if !(8..=dtw::MAX_ROWS).contains(&window.len())||window.windows(2).any(|w|w[1].sensor_ms.wrapping_sub(w[0].sensor_ms)>35){return None;}
        let series=window.iter().map(|s|std::array::from_fn(|i|if i<3{(s.accel_mg[i]-a[i])/1000.}else{(s.gyro_dps[i-3]-g[i-3])/100.})).collect();
        Some(Impact{onset,series:dtw::normalize(series)})
    }
    pub fn poll(&mut self,now:f64)->Vec<(Side,Point,u32)>{
        let mut clicks=vec![];
        loop {
            let Some(p)=self.pending.front()else{break;};
            let feature=self.feature(p.ms);
            if feature.is_none()&&now-p.at<0.4{break;}
            let p=self.pending.pop_front().unwrap();
            let Some(feature)=feature else{self.status.missed_windows+=1;continue;};
            #[cfg(test)]
            if std::env::var_os("COMPANION_CONTACT_SCORE_REPLAY").is_some(){
                if let Some(profile)=&self.profile{
                    eprintln!("CONTACT_SCORE event_ms={} onset_ms={} left={:.9} right={:.9}",p.ms,feature.onset,
                        dtw::distance(&profile.left,&feature.series),dtw::distance(&profile.right,&feature.series));
                }
            }
            // Physical onset, not event spacing: suppress25/93/99ms echoes
            // without a120ms click lockout or freezing pointer movement.
            if self.last_impact.is_some_and(|t|(feature.onset.wrapping_sub(t)as i32).unsigned_abs()<=35){self.status.suppressed_rebounds+=1;continue;}
            self.last_impact=Some(feature.onset);
            if let Some(side)=p.learning {
                if self.status.learning!=Some(side){continue;}
                let samples=if side==Side::Left{&mut self.left}else{&mut self.right};
                if samples.len()<8{samples.push(feature.series);}
                self.status.left_samples=self.left.len();self.status.right_samples=self.right.len();
            }else if let Some(profile)=&self.profile{
                if let Some(side)=profile.classify(&feature.series){self.status.last_side=Some(side);clicks.push((side,p.point,p.ms));}
                else{self.status.uncertain+=1;}
            }
        }
        clicks
    }
}

fn contact_grid(raw:&VecDeque<Raw>,onset:u32)->Option<Vec<Raw>>{
    let origin=onset.wrapping_sub(30);
    let relative=|s:&Raw|s.sensor_ms.wrapping_sub(origin)as i32 as f64+s.sensor_sub_ms_25us as f64*0.025;
    let values:Vec<_>=raw.iter().collect();
    let mut out=Vec::with_capacity(19);let mut index=1;
    for n in 0..19{
        let at=n as f64*10.;
        while index<values.len()&&relative(values[index])<at{index+=1;}
        if index>=values.len(){return None;}
        let (a,b)=(values[index-1],values[index]);let (ta,tb)=(relative(a),relative(b));
        if ta>at||tb-ta<=0.||tb-ta>35.{return None;}
        let t=(at-ta)/(tb-ta);let mut s=*a;s.sensor_ms=origin.wrapping_add(n*10);s.sensor_sub_ms_25us=0;
        for i in 0..3{s.accel_mg[i]=a.accel_mg[i]+t*(b.accel_mg[i]-a.accel_mg[i]);s.gyro_dps[i]=a.gyro_dps[i]+t*(b.gyro_dps[i]-a.gyro_dps[i]);}
        out.push(s);
    }
    Some(out)
}

//! Device-contact adaptation, independent of the upstream pointer mappings.
//! A reliable firmware contact selects a short six-axis window. Raw motion
//! alone never clicks. Personal left/right examples use normalized nearest
//! centroids; this is not a general claim of inertial contact localization.
use super::{desktop::Raw,Point};
use serde::{Deserialize,Serialize};
use std::collections::VecDeque;

#[derive(Clone,Copy,Debug,Deserialize,Serialize,PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Side {Left,Right}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Profile {pub left:[f64;6],pub right:[f64;6]}
fn norm(v:[f64;6])->f64{v.iter().map(|x|x*x).sum::<f64>().sqrt()}
fn unit(v:[f64;6])->Option<[f64;6]>{let n=norm(v);(n.is_finite()&&n>1e-8).then(||v.map(|x|x/n))}
fn dot(a:[f64;6],b:[f64;6])->f64{a.iter().zip(b).map(|(x,y)|x*y).sum()}
impl Profile {
    pub fn validate(&self)->Result<(),&'static str>{
        if !self.left.iter().chain(self.right.iter()).all(|x|x.is_finite()) ||
            (norm(self.left)-1.).abs()>0.01 || (norm(self.right)-1.).abs()>0.01 || dot(self.left,self.right)>0.85 {
            return Err("左右轻敲样本还没有分开，请分别在两侧重新校准。");
        }Ok(())
    }
    fn classify(&self,f:[f64;6])->Option<Side>{
        let l=dot(f,self.left);let r=dot(f,self.right);
        if l.max(r)<0.3 || (l-r).abs()<0.15{return None;}
        Some(if l>r{Side::Left}else{Side::Right})
    }
}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Status {
    pub learning:Option<Side>,pub left_samples:usize,pub right_samples:usize,
    pub calibrated:bool,pub missed_windows:u64,pub uncertain:u64,pub last_side:Option<Side>,
}
struct Pending {ms:u32,at:f64,point:Point,learning:Option<Side>}
pub struct Contact {
    raw:VecDeque<Raw>,pending:VecDeque<Pending>,left:Vec<[f64;6]>,right:Vec<[f64;6]>,
    last_training_ms:Option<u32>,profile:Option<Profile>,pub status:Status,
}
impl Contact {
    pub fn new(profile:Option<Profile>)->Self{
        let calibrated=profile.is_some();Self{raw:VecDeque::with_capacity(64),pending:VecDeque::new(),
            left:vec![],right:vec![],last_training_ms:None,profile,status:Status{calibrated,..Status::default()}}
    }
    pub fn is_active(&self)->bool{self.profile.is_some()||self.status.learning.is_some()}
    pub fn clear_stream(&mut self){self.raw.clear();self.pending.clear();self.last_training_ms=None;}
    pub fn discard_pending(&mut self){self.pending.clear();}
    pub fn pending(&self)->bool{!self.pending.is_empty()}
    pub fn reanchor(&mut self,point:Point){for p in &mut self.pending{p.point=point;}}
    pub fn cancel(&mut self){self.status.learning=None;self.pending.clear();}
    pub fn learn(&mut self,side:Side){
        // Opening the left step begins one fresh pair of examples. Moving to
        // the right step retains the left examples, not old pending contacts.
        if side==Side::Left{self.left.clear();self.right.clear();self.status.left_samples=0;self.status.right_samples=0;}
        self.pending.clear();self.last_training_ms=None;self.status.learning=Some(side);
    }
    pub fn finish(&mut self)->Result<Profile,&'static str>{
        if self.left.len()<3||self.right.len()<3{return Err("请先在左侧、右侧各轻敲三次，再保存校准。");}
        let mean=|a:&Vec<[f64;6]>|unit(std::array::from_fn(|i|a.iter().map(|v|v[i]).sum::<f64>()));
        let profile=Profile{left:mean(&self.left).ok_or("左侧样本不稳定，请重新校准。")?,right:mean(&self.right).ok_or("右侧样本不稳定，请重新校准。")?};
        profile.validate()?;
        self.profile=Some(profile.clone());self.status.calibrated=true;self.cancel();Ok(profile)
    }
    pub fn sample(&mut self,s:Raw){
        // Keep the recent raw baseline before the owner enters calibration.
        // A first natural tap must not be lost waiting for a new160ms window.
        if !s.accel_mg.iter().chain(s.gyro_dps.iter()).all(|x|x.is_finite()){return;}
        if self.raw.back().is_some_and(|p|{let n=s.sequence.wrapping_sub(p.sequence);n==0||n>=0x8000_0000}){return;}
        if self.raw.len()==64{self.raw.pop_front();}self.raw.push_back(s);
    }
    pub fn contact(&mut self,ms:u32,now:f64,point:Point){
        self.pending.push_back(Pending{ms,at:now,point,learning:self.status.learning});
    }
    fn feature(&self,ms:u32)->Option<[f64;6]>{
        let relative=|s:&Raw|s.sensor_ms.wrapping_sub(ms)as i32;
        let baseline=self.raw.iter().filter(|s|(-160..=-70).contains(&relative(s))).collect::<Vec<_>>();
        let impact=self.raw.iter().filter(|s|(-40..=40).contains(&relative(s))).collect::<Vec<_>>();
        if baseline.len()<4||impact.len()<5{return None;}
        // A long missing interval must not become a fabricated tap direction.
        // No requirement about the owner's tap amplitude, angle or distance.
        let window=self.raw.iter().filter(|s|(-160..=40).contains(&relative(s))).collect::<Vec<_>>();
        if window.windows(2).any(|w|w[1].sensor_ms.wrapping_sub(w[0].sensor_ms)>35){return None;}
        let a:[f64;3]=std::array::from_fn(|i|baseline.iter().map(|s|s.accel_mg[i]).sum::<f64>()/baseline.len()as f64);
        let g:[f64;3]=std::array::from_fn(|i|baseline.iter().map(|s|s.gyro_dps[i]).sum::<f64>()/baseline.len()as f64);
        let features=impact.iter().map(|s|std::array::from_fn(|i|if i<3{(s.accel_mg[i]-a[i])/1000.}else{(s.gyro_dps[i-3]-g[i-3])/100.}));
        let peak=features.max_by(|a,b|norm(*a).total_cmp(&norm(*b)))?;
        unit(peak)
    }
    pub fn poll(&mut self,now:f64)->Vec<(Side,Point)>{
        let mut clicks=vec![];
        loop {
            let Some(p)=self.pending.front()else{break;};
            let complete=self.raw.back().is_some_and(|s|s.sensor_ms.wrapping_sub(p.ms)as i32>=40);
            if !complete&&now-p.at<0.18{break;}
            let p=self.pending.pop_front().unwrap();
            let feature=if complete{self.feature(p.ms)}else{None};
            let Some(feature)=feature else{self.status.missed_windows+=1;continue;};
            if let Some(side)=p.learning {
                if self.status.learning!=Some(side){continue;}
                if self.last_training_ms.is_some_and(|ms|p.ms.wrapping_sub(ms)<160){continue;}
                self.last_training_ms=Some(p.ms);
                let samples=if side==Side::Left{&mut self.left}else{&mut self.right};
                if samples.len()<16{samples.push(feature);}
                self.status.left_samples=self.left.len();self.status.right_samples=self.right.len();
            }else if let Some(profile)=&self.profile{
                if let Some(side)=profile.classify(feature){self.status.last_side=Some(side);clicks.push((side,p.point));}
                else{self.status.uncertain+=1;}
            }
        }
        clicks
    }
}

#[cfg(test)]mod tests {
    use super::*;
    fn profile()->Profile{Profile{left:[0.,0.,0.,1.,0.,0.],right:[0.,0.,0.,-1.,0.,0.]}}
    fn raw(ms:u32,sign:f64)->Raw{Raw{sequence:ms/10+1,sensor_ms:ms,accel_mg:[0.,0.,1000.],gyro_dps:[if ms%500==200{sign*70.}else{0.},0.,0.]}}
    #[test]fn raw_motion_alone_never_emits_a_click(){let mut c=Contact::new(Some(profile()));for ms in(0..1000).step_by(10){c.sample(raw(ms,1.));assert!(c.poll(ms as f64/1000.).is_empty());}}
    #[test]fn timestamp_selects_impact_and_each_reliable_contact_yields_one_click(){
        let mut c=Contact::new(Some(profile()));let mut found=vec![];
        for ms in(0..1000).step_by(10){c.sample(raw(ms,if ms<500{1.}else{-1.}));if ms==210||ms==710{c.contact(ms-10,ms as f64/1000.,Point{x:1.,y:2.});}found.extend(c.poll(ms as f64/1000.));}
        assert_eq!(found.iter().map(|x|x.0).collect::<Vec<_>>(),vec![Side::Left,Side::Right]);
        assert!(c.poll(2.).is_empty());
    }
    #[test]fn missing_raw_window_is_not_guessed_or_replayed_after_stream_restart(){
        let mut c=Contact::new(Some(profile()));c.contact(200,0.21,Point::default());assert!(c.poll(0.5).is_empty());assert_eq!(c.status.missed_windows,1);
        c.contact(200,0.5,Point::default());c.clear_stream();assert!(c.poll(1.).is_empty());
    }
    #[test]fn strength_changes_do_not_swap_sides_and_ambiguous_models_are_rejected(){
        for strength in[0.2,1.,3.]{let p=profile();assert_eq!(p.classify(unit([0.,0.,0.,strength,0.,0.]).unwrap()),Some(Side::Left));}
        let mut p=profile();p.right=p.left;assert!(p.validate().is_err());let mut p=profile();p.left[0]=f64::NAN;assert!(p.validate().is_err());
        assert_eq!(profile().classify([1.,0.,0.,0.,0.,0.]),None);
    }
    #[test]fn personal_calibration_consumes_contacts_without_system_clicks(){
        let mut c=Contact::new(None);c.learn(Side::Left);
        for ms in(0..1500).step_by(10){c.sample(raw(ms,1.));if ms%500==210{c.contact(ms-10,ms as f64/1000.,Point::default());}assert!(c.poll(ms as f64/1000.).is_empty());}
        assert_eq!(c.status.left_samples,3);assert!(c.finish().is_err());c.learn(Side::Right);
        for ms in(1500..3000).step_by(10){c.sample(raw(ms,-1.));if ms%500==210{c.contact(ms-10,ms as f64/1000.,Point::default());}assert!(c.poll(ms as f64/1000.).is_empty());}
        assert_eq!(c.status.right_samples,3);c.finish().unwrap();assert!(c.status.calibrated);assert!(c.status.learning.is_none());
    }
    #[test]fn first_tap_can_use_the_stationary_baseline_received_before_learning(){
        let mut c=Contact::new(None);
        for ms in(0..200).step_by(10){c.sample(raw(ms,1.));}
        c.learn(Side::Left);
        for ms in(200..250).step_by(10){c.sample(raw(ms,1.));if ms==210{c.contact(200,0.21,Point::default());}assert!(c.poll(ms as f64/1000.).is_empty());}
        assert_eq!(c.status.left_samples,1);
    }
}

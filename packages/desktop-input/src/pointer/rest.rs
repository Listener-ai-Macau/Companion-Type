// SPDX-FileCopyrightText: 2021 Daniel Laidig <laidig@control.tu-berlin.de>
// SPDX-License-Identifier: MIT
//! Rest-detection/filter portions of Daniel Laidig's MIT-licensed VQF.
//! Pinned source and adaptation details: third_party/imu-pointer/vqf-rest.md.
//! This estimates quiet sensor input, NOT physical table contact or velocity.
//! Constant-speed sliding is observationally ambiguous with a six-axis IMU.
#[derive(Clone)]
struct LowPass {
    b:[f64;3],a:[f64;2],z:[[f64;3];2],sum:[f64;3],count:u32,ready:bool,period:f64,
}
impl Default for LowPass {
    fn default()->Self{Self::with_period(0.01)}
}
impl LowPass {
    fn with_period(period:f64)->Self{
        let c=(2_f64.sqrt()*period/(2.*0.1)).tan();let d=c*c+2_f64.sqrt()*c+1.;
        let b0=c*c/d;
        Self{b:[b0,2.*b0,b0],a:[2.*(c*c-1.)/d,(1.-2_f64.sqrt()*c+c*c)/d],z:[[0.;3];2],sum:[0.;3],count:0,ready:false,period}
    }
}
impl LowPass {
    fn sample(&mut self,x:[f64;3])->[f64;3]{
        if !self.ready{
            self.count+=1;for i in 0..3{self.sum[i]+=x[i];}
            let y=self.sum.map(|v|v/self.count as f64);
            if self.count as f64*self.period>=0.1{
                for i in 0..3{self.z[0][i]=y[i]*(1.-self.b[0]);self.z[1][i]=y[i]*(self.b[2]-self.a[1]);}
                self.ready=true;
            }
            return y;
        }
        std::array::from_fn(|i|{
            let y=self.b[0]*x[i]+self.z[0][i];
            self.z[0][i]=self.b[1]*x[i]-self.a[0]*y+self.z[1][i];
            self.z[1][i]=self.b[2]*x[i]-self.a[1]*y;y
        })
    }
}
#[derive(Default)]
pub struct Rest {gyro:LowPass,accel:LowPass,quiet:f64}
impl Rest {
    /// Same VQF deviation tests in dps and m/s². Device adapter parameters:
    /// Ts10ms, restFilterTau100ms, restMinT120ms, restThAcc0.1m/s².
    /// Upstream gyro deviation/absolute limits remain2dps. No second AHRS.
    pub fn sample(&mut self,gyro_dps:[f64;3],accel_mg:[f64;3])->bool{
        self.sample_timed(gyro_dps,accel_mg,0.01,0.01)
    }
    pub fn sample_timed(&mut self,gyro_dps:[f64;3],accel_mg:[f64;3],dt:f64,nominal_period:f64)->bool{
        if self.gyro.period!=nominal_period{
            self.gyro=LowPass::with_period(nominal_period);self.accel=LowPass::with_period(nominal_period);self.quiet=0.;
        }
        let g=self.gyro.sample(gyro_dps);
        if (0..3).map(|i|(gyro_dps[i]-g[i]).powi(2)).sum::<f64>()>=4.||g.iter().any(|x|x.abs()>2.){self.quiet=0.;}
        let accel=accel_mg.map(|x|x*0.00980665);let a=self.accel.sample(accel);
        if (0..3).map(|i|(accel[i]-a[i]).powi(2)).sum::<f64>()>=0.01{self.quiet=0.;}
        else{self.quiet+=dt;}
        self.quiet>=0.12
    }
}

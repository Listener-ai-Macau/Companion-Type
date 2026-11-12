use super::*;
fn bounds()->Bounds {Bounds{left:0.,top:0.,width:1920.,height:1080.}}
fn sample(seq:u32,ms:u32,held:bool)->Sample {Sample{sequence:seq,sensor_ms:ms,held,accel:[0.,0.,1000.],gyro:[0.;3]}}
fn calibrated()->Pointer {
    let mut p=Pointer::new(Settings::default(),Point{x:960.,y:540.});
    for n in 0..=27 {p.sample(sample(n+1,n*40,false),n as f64*0.04,bounds());p.frame(n as f64*0.04,bounds());}
    assert!(p.metrics.calibrated);p
}
#[test]
fn independent_c_packer_fixture_and_crc_rejection(){
    let hex="43494d310103010007000000f0ffffff0100feffe8036b03589eff7f85e13d5e";
    let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
    let s=Sample::parse(&bytes).unwrap();assert_eq!(s.sensor_ms,0xfffffff0);assert!(s.held);
    assert_eq!(s.accel,[1.,-2.,1000.]);assert_eq!(s.gyro,[8.75,-250.,327.67]);
    let mut corrupt=bytes;corrupt[22]^=1;assert!(Sample::parse(&corrupt).is_err());
}
#[test]
fn upstream_equations_have_expected_units_and_frame_invariance(){
    let s=Settings{deadzone:1.,sensitivity:2.,acceleration:0.5,..Settings::default()};
    assert_eq!(axis_speed(1.,&s),0.);assert_eq!(axis_speed(-61.,&s),-5040.);
    let center=laser(0.,0.,1.,bounds());assert_eq!(center,Point{x:960.,y:540.});
    let left=laser(25.,0.,1.,bounds());assert!(left.x.abs()<1e-10);
    let mut a=Smoother::default();let mut b=Smoother::default();
    a.target(Point{x:100.,y:0.},0.);b.target(Point{x:100.,y:0.},0.);
    a.step(0.016,1./60.,0.55);for n in 1..=2 {b.step(n as f64/120.,1./120.,0.55);}
    assert!((a.velocity.x-b.velocity.x).abs()<1e-10);
    let mut euro=OneEuro::default();assert_eq!(euro.update(4.,0.04),4.);assert_eq!(euro.update(4.,0.04),4.);
    let next=euro.update(100.,0.04);assert!(next>4.&&next<100.);
}
#[test]
fn calibration_requires_a_continuous_stationary_interval_and_removes_bias(){
    let mut p=Pointer::new(Settings::default(),Point{x:960.,y:540.});
    for n in 0..=80 {let mut s=sample(n+1,n*40,false);s.gyro=[0.7,0.2,-0.8];
        if n==15 {s.gyro[0]=30.;} p.sample(s,n as f64*0.04,bounds());p.frame(n as f64*0.04,bounds());
        if n==30 {assert!(!p.metrics.calibrated);}}
    assert!(p.metrics.calibrated);assert!(p.shown.distance(Point{x:960.,y:540.})<1e-8);
}
#[test]
fn tap_click_and_hold_drag_use_original_down_location_and_release_on_gap(){
    let mut p=calibrated();p.sample(sample(29,1120,true),1.12,bounds());
    p.frame(1.12,bounds());p.sample(sample(30,1160,false),1.16,bounds());
    assert!(matches!(p.frame(1.16,bounds()).buttons.as_slice(),[Button::Click(_)]));
    for n in 31..=42 {let time=n as f64*0.04;p.sample(sample(n,n*40,true),time,bounds());p.frame(time,bounds());}
    assert!(p.metrics.dragging);let f=p.frame(2.1,bounds());assert_eq!(f.buttons,vec![Button::Up]);
    assert!(!p.metrics.dragging);assert!(p.frame(2.2,bounds()).buttons.is_empty());
    p.sample(sample(43,1720,false),2.21,bounds());assert!(p.frame(2.21,bounds()).buttons.is_empty());
}
#[test]
fn lost_button_release_and_pause_never_create_a_click(){
    let mut p=calibrated();p.sample(sample(29,1120,true),1.12,bounds());p.pause(true);
    p.sample(sample(30,1160,false),1.16,bounds());assert!(p.frame(1.16,bounds()).buttons.is_empty());
    p.pause(false);p.sample(sample(31,1200,false),1.2,bounds());assert!(p.frame(1.2,bounds()).buttons.is_empty());
    let mut s=sample(32,1240,false);s.gyro[2]=20.;p.sample(s,1.24,bounds());assert!(p.frame(1.25,bounds()).position.is_some());
    for n in 126..150 {p.frame(n as f64/100.,bounds());}
    assert!(p.frame(1.6,bounds()).position.is_none());
}
#[test]
fn sensor_clock_wrap_duplicate_and_sequence_gap_are_not_integrated_twice(){
    let mut p=calibrated();p.last=Some((u32::MAX,0xfffffff0));
    p.sample(sample(1,24,false),1.12,bounds());assert_eq!(p.metrics.missing,1);
    let count=p.metrics.samples;p.sample(sample(1,24,true),1.13,bounds());
    assert_eq!(p.metrics.samples,count);assert_eq!(p.metrics.duplicates,1);assert!(p.pressed.is_none());
}

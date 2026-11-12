use super::*;
fn bounds()->Bounds {Bounds{left:0.,top:0.,width:1920.,height:1080.,primary:None}}
fn sample(seq:u32,ms:u32,held:bool)->Sample {Sample{sequence:seq,sensor_ms:ms,held,tap_serial:0,fused:false,device_ready:None,accel:[0.,0.,1000.],gyro:[0.;3]}}
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


#[test]
fn fused_c_fixture_is_not_fused_again_and_has_tap_serial() {
    let hex="43494d31020301ff07000000f0ffffff0100feffe8036b03589eff7fe5204850";
    let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
    let s=Sample::parse(&bytes).unwrap();assert!(s.fused);assert_eq!(s.tap_serial,255);
    let mut p=calibrated();let mut s=sample(29,1120,false);
    s.fused=true;s.accel=[0.,500.,866.];p.sample(s,1.12,bounds());
    assert!(p.target.unwrap().y<400.);
}
#[test]
fn body_double_tap_click_is_once_with_wrap_and_never_replayed_after_pause_or_gap() {
    let mut p=calibrated();
    let mut s=sample(29,1120,false);s.tap_serial=255;p.sample(s,1.12,bounds());
    assert!(p.frame(1.12,bounds()).buttons.is_empty());
    s.sequence=30;s.sensor_ms=1160;s.tap_serial=0;p.sample(s,1.16,bounds());
    assert!(matches!(p.frame(1.16,bounds()).buttons.as_slice(),[Button::Click(_)]));
    s.sequence=31;s.sensor_ms=1200;p.sample(s,1.2,bounds());assert!(p.frame(1.2,bounds()).buttons.is_empty());
    p.pause(true);s.sequence=32;s.sensor_ms=1240;s.tap_serial=1;p.sample(s,1.24,bounds());
    p.pause(false);s.sequence=33;s.sensor_ms=1280;p.sample(s,1.28,bounds());assert!(p.frame(1.28,bounds()).buttons.is_empty());
    s.sequence=34;s.sensor_ms=1680;s.tap_serial=2;p.sample(s,1.68,bounds());assert!(p.frame(1.68,bounds()).buttons.is_empty());
}
#[test]
fn upstream_fusion_tracks_physical_roll_without_raw_acceleration_lowpass() {
    let mut f=fusion::Fusion::default();f.step([0.;3],[0.,0.,1000.],0.01);f.align([0.,0.,1000.]);
    let mut up=[0.;3];
    for n in 1..=200 {
        let angle=(n as f64*0.1).to_radians();
        up=f.step([10.,0.,0.],[0.,angle.sin()*1000.,angle.cos()*1000.],0.01).0;
    }
    let measured=up[1].atan2(up[2]).to_degrees();
    assert!((measured-20.).abs()<0.5,"physical roll={measured}");
}

#[test]
fn watch_pause_keeps_tracking_aim_and_primary_screen_controls_projection_scale() {
    let b=Bounds{width:3840.,primary:Some([0.,0.,1920.,1080.]),..bounds()};
    assert!((laser(-25.,0.,1.,b).x-1920.).abs()<1e-8);
    let defaults=Settings::default();assert_eq!((defaults.smoothing,defaults.deadzone,defaults.acceleration),(0.55,3.,0.6));
    let mut p=calibrated();p.pause(true);
    for n in 29..=53 {let mut s=sample(n,(n-1)*40,false);s.fused=true;s.gyro[2]=10.;p.sample(s,(n-1) as f64*0.04,bounds());}
    assert!((p.heading-10.).abs()<0.01);assert!(p.frame(2.08,bounds()).position.is_none());
    p.pause(false);let mut s=sample(54,2120,false);s.fused=true;p.sample(s,2.12,bounds());
    assert!(p.target.unwrap().x<800.); // Resume points to current aim, not the pre-pause heading.
}


#[test]
fn board_calibrated_packet_uses_q14_gravity_and_no_second_fixed_host_bias() {
    let hex="43494d31030303ff07000000f0ffffff000000206d376b03589eff7f10f854e6";
    let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
    let s=Sample::parse(&bytes).unwrap();assert!(s.fused);assert_eq!(s.device_ready,Some(true));
    assert!((s.accel[1]-500.).abs()<0.01);
    let mut p=Pointer::new(Settings::default(),Point{x:960.,y:540.});
    let mut s=sample(1,0,false);s.fused=true;s.device_ready=Some(false);s.gyro=[0.8,-0.7,0.5];
    for n in 0..100 {s.sequence=n+1;s.sensor_ms=n*10;p.sample(s,n as f64*0.01,bounds());}
    assert!(!p.metrics.calibrated);
    s.device_ready=Some(true);s.gyro=[0.;3];
    for n in 100..2100 {s.sequence=n+1;s.sensor_ms=n*10;p.sample(s,n as f64*0.01,bounds());p.frame(n as f64*0.01,bounds());}
    assert!(p.metrics.calibrated);assert_eq!(p.bias,[0.;3]);assert!(p.heading.abs()<1e-10);
    s.sequence+=1;s.sensor_ms+=10;s.device_ready=Some(false);p.sample(s,21.,bounds());
    assert!(!p.metrics.calibrated);assert!(p.frame(21.,bounds()).position.is_none());
}

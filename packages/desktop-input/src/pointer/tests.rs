use super::*;
fn raw_sample(n:u32)->desktop::Raw{desktop::Raw{sequence:n+1,sensor_ms:n*10,accel_mg:[0.,0.,1000.],gyro_dps:[0.;3]}}
fn coarse_ready()->Pointer{
    let mut p=Pointer::new(Settings{mapping:Mapping::Relative,desktop_motion:true,..Settings::default()},Point{x:960.,y:540.});
    for n in 0..121{p.sample_raw(raw_sample(n),n as f64/100.);p.frame(n as f64/100.,bounds());}
    assert!(p.metrics.calibrated);p
}
#[test]fn raw_desktop_path_moves_and_keeps_ordinary_mouse_position_without_snapback(){
    let mut p=coarse_ready();
    for n in 121..131{let mut s=raw_sample(n);s.accel_mg[0]=100.;p.sample_raw(s,n as f64/100.);p.frame(n as f64/100.,bounds());}
    assert!(p.shown.x>960.);
    p.external_position(Point{x:1600.,y:800.});
    assert!(p.control(Control{sequence:1,sensor_ms:1300,events:CLICK}).unwrap());
    let click=p.frame(1.305,bounds());assert!(matches!(click.buttons[0],Button::Click(Point{x:1600.,y:800.})));
    for n in 131..180{p.sample_raw(raw_sample(n),n as f64/100.);assert!(p.frame(n as f64/100.,bounds()).position.is_none());}
    assert_eq!(p.shown,Point{x:1600.,y:800.});
    for n in 180..190{let mut s=raw_sample(n);s.accel_mg[0]=-100.;p.sample_raw(s,n as f64/100.);p.frame(n as f64/100.,bounds());}
    assert!(p.shown.x<1600.);
}
#[test]fn raw_contact_reuses_reliable_control_clock_rewinds_and_consumes_retry_once(){
    let mut p=coarse_ready();let mut s=raw_sample(121);s.gyro_dps[2]=90.;p.sample_raw(s,1.21);p.frame(1.22,bounds());
    let click=Control{sequence:1,sensor_ms:1210,events:CLICK};assert!(p.control(click).unwrap());
    assert!(!p.control(click).unwrap());let frame=p.frame(1.23,bounds());
    assert_eq!(frame.buttons.len(),1);assert!(matches!(frame.buttons[0],Button::Click(Point{x:960.,y:540.})));
    assert!(p.frame(1.24,bounds()).buttons.is_empty());
}
#[test]fn raw_mode_does_not_silently_accept_a_different_pose_schema_and_calibration_restarts(){
    let mut p=coarse_ready();let count=p.metrics.samples;
    p.sample(sample(900,2000,false),2.,bounds());assert_eq!(p.metrics.samples,count);
    p.calibrate();assert!(!p.metrics.calibrated);p.sample_raw(raw_sample(122),1.22);assert!(!p.metrics.calibrated);
    let invalid=Settings{desktop_motion:true,..Settings::default()};assert!(invalid.validate().is_err());
}
#[test]fn new_raw_stream_accepts_restart_counter_without_waiting_for_old_sequence(){
    let mut p=coarse_ready();p.pause(true);p.begin_stream();p.pause(false);
    for n in 0..121{p.sample_raw(raw_sample(n),2.+n as f64/100.);p.frame(2.+n as f64/100.,bounds());}
    assert!(p.metrics.calibrated);assert!(!p.metrics.paused);
    for n in 121..131{let mut s=raw_sample(n);s.accel_mg[0]=100.;p.sample_raw(s,2.+n as f64/100.);p.frame(2.+n as f64/100.,bounds());}
    assert!(p.shown.x>960.);
}
fn bounds()->Bounds {Bounds{left:0.,top:0.,width:1920.,height:1080.,primary:None}}
fn side_profile()->contact::Profile{
    let mut left=vec![[0.;6];19];left[3][3]=0.7;
    let mut right=vec![[0.;6];19];right[3][3]=-0.7;
    contact::Profile{schema:2,left:contact_dtw::normalize(left),right:contact_dtw::normalize(right),left_threshold:1e-6,right_threshold:1e-6}
}
fn side_ready()->Pointer{
    let mut p=Pointer::new(Settings{mapping:Mapping::Relative,desktop_motion:true,contact_profile:Some(side_profile()),..Settings::default()},Point{x:960.,y:540.});
    for n in 0..121{p.sample_raw(raw_sample(n),n as f64/100.);p.frame(n as f64/100.,bounds());}p
}
#[test]fn contact_stream_keeps_fused_motion_and_raw_acceleration_separate_without_counting_twice(){
    // Independent C packer fixture: gravity +Z, gyro90deg/s around Z, raw
    // acceleration[1,-2,1000]. Both projections share one sequence and clock.
    let hex="43494d310603030209000000000000000000000000400000000028230100feffe8030000adc11945";
    let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
    let motion=Sample::parse(&bytes).unwrap();let raw=desktop::Raw::parse(&bytes).unwrap();
    assert_eq!(motion.accel,[0.,0.,1000.]);assert_eq!(raw.accel_mg,[1.,-2.,1000.]);assert_eq!(motion.gyro,raw.gyro_dps);
    let settings=Settings{contact_regions:true,..Settings::relative_remote()};assert!(settings.validate().is_ok());assert_eq!(settings.pointer_options(),72);
    let mut p=Pointer::new(settings,Point::default());p.sample_raw(raw,0.);p.sample(motion,0.,bounds());
    assert_eq!(p.metrics.samples,1);assert!(p.coarse.is_none());assert!(p.metrics.calibrated);
    let mut bad=bytes;bad[28]^=1;assert!(Sample::parse(&bad).is_err());assert!(desktop::Raw::parse(&bad).is_err());
}
#[test]fn regional_clicks_do_not_freeze_movement_or_rewind_the_ordinary_mouse(){
    let mut p=Pointer::new(Settings{contact_regions:true,contact_profile:Some(side_profile()),..Settings::relative_remote()},Point{x:960.,y:540.});
    let mut clicks=vec![];let mut moved_while_pending=false;
    for n in 0..80{
        let mut raw=raw_sample(n);if n==40{raw.gyro_dps[0]=70.;}
        let motion=Sample{fused:true,device_ready:Some(true),gyro:[5.,0.,0.],..sample(n+1,n*10,false)};
        p.sample_raw(raw,n as f64/100.);p.sample(motion,n as f64/100.,bounds());
        if n==41{p.control(Control{sequence:1,sensor_ms:400,events:CLICK}).unwrap();}
        if n==50{p.external_position(Point{x:1500.,y:800.});}
        let pending=p.contacts.pending();let f=p.frame(n as f64/100.,bounds());
        moved_while_pending|=pending&&f.position.is_some();
        clicks.extend(f.buttons);
    }
    assert!(moved_while_pending,"contact recognition cannot reintroduce the rejected150ms movement freeze");
    assert_eq!(clicks.len(),1);assert!(matches!(clicks[0],Button::Click(point)if point.x==1500.&&point.y>=800.));
}
#[test]fn single_and_double_shell_taps_keep_the_target_at_default_sensitivity(){
    let origin=Point{x:960.,y:540.};
    let mut p=Pointer::new(Settings{contact_regions:true,contact_profile:Some(side_profile()),..Settings::relative_remote()},origin);
    assert_eq!(p.settings.sensitivity,1.);
    let mut clicks=vec![];
    for n in 0..105{
        let mut raw=raw_sample(n);let shock=n==40||n==60;
        if shock{raw.accel_mg[0]=1000.;raw.gyro_dps[0]=70.;}
        let motion=Sample{fused:true,device_ready:Some(true),gyro:raw.gyro_dps,..sample(n+1,n*10,false)};
        p.sample_raw(raw,n as f64/100.);p.sample(motion,n as f64/100.,bounds());
        if n==41||n==61{p.control(Control{sequence:n,sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        let f=p.frame(n as f64/100.,bounds());clicks.extend(f.buttons);
        assert_eq!(p.shown,origin,"contact impulse leaked into movement at sample{n}");assert!(f.position.is_none());
    }
    assert_eq!(clicks,vec![Button::Click(origin),Button::Click(origin)],"two contacts200ms apart remain a same-target double click");
    for n in 105..125{
        let mut raw=raw_sample(n);raw.gyro_dps=[0.,2.,0.];
        p.sample_raw(raw,n as f64/100.);p.sample(Sample{fused:true,device_ready:Some(true),gyro:raw.gyro_dps,..sample(n+1,n*10,false)},n as f64/100.,bounds());p.frame(n as f64/100.,bounds());
    }
    assert!(p.shown.x>origin.x,"normal fine movement after the clicks must still work");
}
#[test]fn distinct190ms_taps_are_two_clicks_while_a25ms_ring_event_is_suppressed(){
    let mut p=side_ready();let mut clicks=vec![];
    for n in 121..200{
        let mut s=raw_sample(n);if n==150||n==169{s.gyro_dps[0]=70.;}
        p.sample_raw(s,n as f64/100.);
        if n==151||n==153||n==170{p.control(Control{sequence:n,sensor_ms:if n==153{1525}else{(n-1)*10},events:CLICK}).unwrap();}
        clicks.extend(p.frame(n as f64/100.,bounds()).buttons);
    }
    assert_eq!(clicks.len(),2);assert_eq!(p.contact_status().suppressed_rebounds,1);
}
#[test]fn learned_right_and_left_contacts_reach_distinct_system_buttons_once_each(){
    let mut p=side_ready();let mut clicks=vec![];
    for n in 121..210{
        let mut s=raw_sample(n);if n==150{s.gyro_dps[0]=-70.;}if n==185{s.gyro_dps[0]=70.;}
        p.sample_raw(s,n as f64/100.);
        if n==151||n==186{let e=Control{sequence:if n==151{1}else{2},sensor_ms:(n-1)*10,events:CLICK};assert!(p.control(e).unwrap());assert!(!p.control(e).unwrap());}
        clicks.extend(p.frame(n as f64/100.,bounds()).buttons);
    }
    assert_eq!(clicks.len(),2);assert!(matches!(clicks[0],Button::RightClick(_)));assert!(matches!(clicks[1],Button::Click(_)));
}
#[test]fn two_contacts_are_two_clicks_and_pause_cannot_replay_a_pending_contact(){
    let mut p=side_ready();let mut clicks=vec![];
    for n in 121..210{
        let mut s=raw_sample(n);if n==150||n==185{s.gyro_dps[0]=70.;}p.sample_raw(s,n as f64/100.);
        if n==151||n==186{p.control(Control{sequence:if n==151{1}else{2},sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        clicks.extend(p.frame(n as f64/100.,bounds()).buttons);
    }
    assert_eq!(clicks.len(),2);assert!(clicks.iter().all(|c|matches!(c,Button::Click(_))));
    p.control(Control{sequence:3,sensor_ms:2090,events:CLICK}).unwrap();p.pause(true);p.pause(false);
    for n in 210..240{p.sample_raw(raw_sample(n),n as f64/100.);assert!(p.frame(n as f64/100.,bounds()).buttons.is_empty());}
}
#[test]fn ordinary_mouse_motion_reanchors_a_delayed_side_click(){
    let mut p=side_ready();let mut clicks=vec![];
    for n in 121..170{
        let mut s=raw_sample(n);if n==150{s.gyro_dps[0]=-70.;}p.sample_raw(s,n as f64/100.);
        if n==151{p.control(Control{sequence:1,sensor_ms:1500,events:CLICK}).unwrap();p.external_position(Point{x:1600.,y:800.});}
        clicks.extend(p.frame(n as f64/100.,bounds()).buttons);
    }
    assert_eq!(clicks,vec![Button::RightClick(Point{x:1600.,y:800.})]);
}
#[test]fn profile_roundtrip_keeps_the_model_and_invalid_model_cannot_enable_input(){
    let p=Settings{mapping:Mapping::Relative,desktop_motion:true,contact_profile:Some(side_profile()),contact_device:Some("card-a".into()),..Settings::default()};
    let round:Settings=serde_json::from_str(&serde_json::to_string(&p).unwrap()).unwrap();assert!(round.validate().is_ok());assert_eq!(round.contact_device.as_deref(),Some("card-a"));
    let mut bad=round;bad.contact_profile.as_mut().unwrap().right=bad.contact_profile.as_ref().unwrap().left.clone();assert!(bad.validate().is_err());
}
#[test]fn full_pointer_calibration_collects_two_sides_without_any_cursor_or_click_output(){
    let mut p=coarse_ready();p.learn_contact(contact::Side::Left).unwrap();
    let mut control=0;
    for n in 121..281{
        let mut s=raw_sample(n);if [150,200,250].contains(&n){s.gyro_dps[0]=70.;}p.sample_raw(s,n as f64/100.);
        if [151,201,251].contains(&n){control+=1;p.control(Control{sequence:control,sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        let f=p.frame(n as f64/100.,bounds());assert!(f.position.is_none()&&f.buttons.is_empty());
    }
    assert_eq!(p.contact_status().left_samples,3);p.learn_contact(contact::Side::Right).unwrap();
    for n in 281..441{
        let mut s=raw_sample(n);if [310,360,410].contains(&n){s.gyro_dps[0]=-70.;}p.sample_raw(s,n as f64/100.);
        if [311,361,411].contains(&n){control+=1;p.control(Control{sequence:control,sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        let f=p.frame(n as f64/100.,bounds());assert!(f.position.is_none()&&f.buttons.is_empty());
    }
    assert_eq!(p.contact_status().right_samples,3);p.finish_contacts().unwrap();assert!(p.settings.contact_profile.is_some());
}
fn sample(seq:u32,ms:u32,held:bool)->Sample {Sample{sequence:seq,sensor_ms:ms,held,tap_serial:0,fused:false,device_ready:None,aim:None,accel:[0.,0.,1000.],gyro:[0.;3]}}
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

fn aim_sample(seq:u32,ms:u32,heading:f64)->Sample {
    Sample{fused:true,device_ready:Some(true),aim:Some([heading,90.,0.]),..sample(seq,ms,false)}
}
fn aim_pointer()->Pointer {
    let mut p=Pointer::new(Settings::default(),Point{x:960.,y:540.});
    p.sample(aim_sample(1,0,0.),0.,bounds());p.sample(aim_sample(2,10,0.),0.01,bounds());p.frame(0.01,bounds());p
}
#[test]
fn laser_start_and_recenter_keep_the_existing_cursor_for_the_first_click() {
    let initial=Point{x:1450.,y:810.};
    let mut p=Pointer::new(Settings::default(),initial);
    for n in 0..25 {
        p.sample(aim_sample(n+1,n*10,0.),n as f64/100.,bounds());
        assert!(p.frame(n as f64/100.,bounds()).position.is_none());
    }
    p.control(Control{sequence:1,sensor_ms:240,events:CLICK}).unwrap();
    assert_eq!(p.frame(0.245,bounds()).buttons,vec![Button::Click(initial)]);
    let recentered=Point{x:420.,y:260.};p.recenter(recentered);
    for n in 25..50 {
        p.sample(aim_sample(n+1,n*10,15.),n as f64/100.,bounds());
        assert!(p.frame(n as f64/100.,bounds()).position.is_none());
    }
    p.control(Control{sequence:2,sensor_ms:490,events:CLICK}).unwrap();
    assert_eq!(p.frame(0.495,bounds()).buttons,vec![Button::Click(recentered)]);
    p.sample(aim_sample(51,500,13.),0.5,bounds());
    assert!(p.frame(0.51,bounds()).position.unwrap().x>recentered.x);
}
#[test]
fn cim4_matches_independent_c_fixture_and_preserves_angles_rates_gravity() {
    let hex="43494d31040303ff07000000f0ffffffd204000000206d37d7f66b03b831ec81";
    let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
    let s=Sample::parse(&bytes).unwrap();assert_eq!(s.aim,Some([12.34,-23.45,8.75]));
    assert_eq!(s.device_ready,Some(true));assert_eq!(s.accel[0],0.);assert_eq!(s.accel[1],500.);
}
#[test]
fn device_heading_recovers_all_turns_when_eighty_motion_packets_are_missing() {
    let mut full=aim_pointer();let mut lossy=aim_pointer();let mut legacy=aim_pointer();
    legacy.heading_zero=None;
    // Watch's device loop integrates90deg/s at100Hz regardless of whether
    // its BLE write is accepted. Drop the middle800ms at the receiver.
    for n in 1..=100 {
        let s=aim_sample(n+2,n*10+10,n as f64*0.9);let now=n as f64*0.01+0.01;
        full.sample(s,now,bounds());full.frame(now,bounds());
        if n<=10||n>90 {
            lossy.sample(s,now,bounds());lossy.frame(now,bounds());
            let mut old=s;old.aim=None;old.gyro=[0.,0.,90.];legacy.sample(old,now,bounds());
        }
    }
    assert!((full.heading-90.).abs()<1e-8);assert!((lossy.heading-full.heading).abs()<1e-8);
    assert_eq!(lossy.metrics.missing,80);assert!(legacy.heading<25.,"old integration loses the turn: {}",legacy.heading);
    // Recenter and wrap use the absolute device heading, without a reset
    // command or another round trip to the card.
    lossy.recenter(Point{x:960.,y:540.});lossy.sample(aim_sample(103,1020,179.),1.02,bounds());
    lossy.sample(aim_sample(104,1030,-179.),1.03,bounds());assert!((lossy.heading-2.).abs()<1e-8);
}
#[test]
fn reliable_click_survives_missing_motion_and_duplicate_control_is_not_replayed() {
    let mut p=aim_pointer();
    let down=Control{sequence:1,sensor_ms:30,events:DOWN};
    let up=Control{sequence:2,sensor_ms:120,events:UP};
    assert_eq!(p.control(down),Ok(true));assert_eq!(p.control(down),Ok(false));
    // No motion packet carries either button edge.
    assert_eq!(p.control(up),Ok(true));assert_eq!(p.control(up),Ok(false));
    assert!(matches!(p.frame(0.2,bounds()).buttons.as_slice(),[Button::Click(_)]));
    assert!(p.frame(0.21,bounds()).buttons.is_empty());
    // A complete short press replayed in one foreground retains one click.
    p.control(Control{sequence:3,sensor_ms:200,events:DOWN|UP}).unwrap();
    assert!(matches!(p.frame(0.22,bounds()).buttons.as_slice(),[Button::Click(_)]));
    // CIM4 copies of level/tap serial cannot produce duplicate buttons.
    let mut s=aim_sample(3,230,0.);s.held=true;s.tap_serial=1;p.sample(s,0.23,bounds());
    s.sequence+=1;s.sensor_ms+=10;s.held=false;s.tap_serial=2;p.sample(s,0.24,bounds());
    assert!(p.frame(0.24,bounds()).buttons.is_empty());
    p.control(Control{sequence:4,sensor_ms:250,events:DOWN}).unwrap();
    p.control(Control{sequence:5,sensor_ms:700,events:UP}).unwrap();
    assert!(matches!(p.frame(0.25,bounds()).buttons.as_slice(),[Button::Down(_),Button::Up]));
    let mut s=aim_sample(100,1000,5.);s.held=true;p.sample(s,1.,bounds());
    p.control(Control{sequence:6,sensor_ms:990,events:DOWN}).unwrap();
    p.control(Control{sequence:7,sensor_ms:1030,events:UP}).unwrap();
    assert!(matches!(p.frame(1.,bounds()).buttons.as_slice(),[Button::Click(_)]));
}
#[test]
fn reliable_drag_release_pause_overflow_and_sequence_wrap_are_bounded() {
    // Simulate regular motion during the hold, rather than a stale gap.
    let mut p=aim_pointer();p.control(Control{sequence:u32::MAX,sensor_ms:30,events:DOWN}).unwrap();
    for n in 3..=40 {let mut s=aim_sample(n,n*10,0.);s.held=true;p.sample(s,n as f64*0.01,bounds());p.frame(n as f64*0.01,bounds());}
    assert!(p.metrics.dragging);
    assert_eq!(p.control(Control{sequence:1,sensor_ms:410,events:UP}),Ok(true));
    assert_eq!(p.frame(0.41,bounds()).buttons,vec![Button::Up]);
    p.pause(true);p.control(Control{sequence:2,sensor_ms:420,events:CLICK}).unwrap();p.pause(false);
    assert!(p.frame(0.42,bounds()).buttons.is_empty());
    assert!(p.control(Control{sequence:3,sensor_ms:430,events:OVERFLOW|UP}).is_err());
    assert!(!p.metrics.dragging);
}

#[test]
fn ordinary_mouse_reanchors_laser_without_snap_back_or_losing_next_card_turn() {
    let mut p=aim_pointer();
    // There is unfinished interpolation when the ordinary mouse takes over.
    p.sample(aim_sample(3,20,5.),0.02,bounds());p.frame(0.02,bounds());
    let physical=Point{x:1200.,y:700.};p.external_position(physical);
    for n in 4..30 {
        p.sample(aim_sample(n,n*10,5.),n as f64*0.01,bounds());
        assert!(p.frame(n as f64*0.01,bounds()).position.is_none());
        assert!(p.shown.distance(physical)<1e-8);
    }
    p.sample(aim_sample(30,300,7.),0.3,bounds());
    assert!(p.frame(0.3,bounds()).position.unwrap().x<physical.x);
    // A second ordinary move establishes a new anchor again.
    let physical=Point{x:600.,y:300.};p.external_position(physical);
    p.sample(aim_sample(31,310,7.),0.31,bounds());
    assert!(p.frame(0.31,bounds()).position.is_none());assert_eq!(p.shown,physical);
}
#[test]
fn ordinary_mouse_reanchors_relative_motion_instead_of_restoring_old_position() {
    let mut p=aim_pointer();p.settings.mapping=Mapping::Relative;
    let physical=Point{x:1250.,y:720.};p.external_position(physical);
    for n in 3..30 {let mut s=aim_sample(n,n*10,0.);s.aim=Some([0.,0.,0.]);p.sample(s,n as f64*0.01,bounds());assert!(p.frame(n as f64*0.01,bounds()).position.is_none());}
    assert_eq!(p.shown,physical);
    let mut s=aim_sample(30,300,0.);s.aim=Some([0.,15.,0.]);p.sample(s,0.3,bounds());
    assert!(p.frame(0.3,bounds()).position.unwrap().x<physical.x);
}

#[test]
fn actual_typec_front_lift_moves_up_in_the_existing_angular_mapper() {
    // Physically labelled device frames bind the board's connector direction
    // to the upstream screen projection; no fitted or generated sensor values.
    let fixture:serde_json::Value=serde_json::from_str(include_str!("fixtures/typec-forward66830.json")).unwrap();
    assert_eq!(fixture["frontSensorAxis"],"+Y");
    let mut p=Pointer::new(Settings::default(),Point{x:960.,y:540.});
    let mut start=None;let mut highest:f64=540.;
    for packet in fixture["packets"].as_array().unwrap() {
        let hex=packet.as_str().unwrap();
        let bytes=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
        let s=Sample::parse(&bytes).unwrap();assert!(s.aim.is_some());
        let first=*start.get_or_insert(s.sensor_ms);
        let now=s.sensor_ms.wrapping_sub(first)as f64/1000.;
        p.sample(s,now,bounds());
        let frame=p.frame(now,bounds());assert!(frame.buttons.is_empty());
        if let Some(position)=frame.position{highest=highest.min(position.y);}
    }
    assert!(p.metrics.calibrated);
    assert!(!p.settings.desktop_motion);
    assert!(highest<340.,"raising the physical Type-C front must move upward, got {highest}");
}

fn surface_pointer()->Pointer{
    let settings=Settings{desktop_motion:true,contact_regions:true,contact_profile:Some(side_profile()),key_role:KeyRole::Regrip,..Settings::relative_remote()};
    assert!(settings.validate().is_ok());assert_eq!(settings.pointer_options(),72);
    let mut p=Pointer::new(settings,Point{x:960.,y:540.});
    for n in 0..121{surface_frame(&mut p,n,[0.,0.,1000.],[0.;3]);}
    assert!(p.metrics.calibrated);assert!(!p.metrics.surface_paused);p
}
fn surface_frame(p:&mut Pointer,n:u32,a:[f64;3],g:[f64;3])->Frame{
    p.sample_raw(desktop::Raw{sequence:n+1,sensor_ms:n*10,accel_mg:a,gyro_dps:g},n as f64/100.);
    // Real CIM6 also dispatches a fused packet. It must not double-count the
    // clock or reactivate the angular mapper in surface mode.
    p.sample(Sample{fused:true,device_ready:Some(true),gyro:g,..sample(n+1,n*10,false)},n as f64/100.,bounds());
    p.frame(n as f64/100.,bounds())
}
#[test]fn surface_pointer_uses_acceleration_with_zero_gyro_and_keeps_a_coasting_stroke(){
    let mut p=surface_pointer();let mut begin=0.;let mut end=0.;
    for n in 121..281{
        let a=if n<141{100.}else if n<211{0.}else if n<231{-100.}else{0.};
        surface_frame(&mut p,n,[a,0.,1000.],[0.;3]);
        if n==145{begin=p.shown.x;}if n==205{end=p.shown.x;}
    }
    assert!(end-begin>100.,"constant speed must not be discarded as rest: {begin}->{end}");
    assert!(p.shown.x>1060.);assert!((p.shown.y-540.).abs()<2.);
    assert_eq!(p.metrics.samples,281);assert!(p.coarse.as_ref().unwrap().desktop.has_surface());
}
#[test]fn surface_pointer_does_not_use_gyro_as_a_fallback_direction(){
    let mut p=surface_pointer();let origin=p.shown;
    for n in 121..221{let f=surface_frame(&mut p,n,[0.,0.,1000.],[0.,0.,30.]);assert!(f.position.is_none());}
    assert_eq!(p.shown,origin);
}
#[test]fn surface_pointer_lift_and_air_reposition_do_not_move_then_landing_rearms(){
    let mut p=surface_pointer();let origin=p.shown;let mut n=121;
    for(count,z,x,rest)in[(15,100.,0.,false),(20,0.,50.,false),(15,-100.,0.,false),(100,0.,0.,true),(15,-100.,0.,false),(20,0.,-50.,false),(15,100.,0.,false),(100,0.,0.,true)]{
        let _=rest;for _ in 0..count{surface_frame(&mut p,n,[x,0.,1000.+z],[0.;3]);n+=1;assert_eq!(p.shown,origin,"air reposition leaked at{n}: {:?}",p.planar_state());}
    }
    assert!(!p.metrics.surface_paused,"landing failed to rearm: {:?}",p.planar_state());
    for _ in 0..20{surface_frame(&mut p,n,[100.,0.,1000.],[0.;3]);n+=1;}
    assert!(p.shown.x>origin.x,"must still track after being put down");
}
#[test]fn surface_clicks_keep_the_target_and_key_regrip_reestablishes_the_plane(){
    let mut p=surface_pointer();let origin=p.shown;let mut clicks=vec![];
    for n in 121..205{
        let shock=n==140||n==160;let a=if shock{[1000.,0.,1000.]}else{[0.,0.,1000.]};let g=if shock{[70.,0.,0.]}else{[0.;3]};
        let f=surface_frame(&mut p,n,a,g);clicks.extend(f.buttons);
        if n==141||n==161{p.control(Control{sequence:n,sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        assert_eq!(p.shown,origin,"sample{n}: {:?}",p.planar_state());
    }
    assert_eq!(clicks,vec![Button::Click(origin),Button::Click(origin)]);
    p.control(Control{sequence:205,sensor_ms:2040,events:DOWN}).unwrap();
    p.control(Control{sequence:206,sensor_ms:2050,events:UP}).unwrap();assert!(!p.metrics.calibrated);
    for n in 206..330{surface_frame(&mut p,n,[0.,0.,1000.],[0.;3]);}
    assert!(p.metrics.calibrated);assert!(!p.metrics.surface_paused);assert_eq!(p.shown,origin);
}
#[test]fn ready_cim6_regional_clicks_cannot_leak_a_pose_prediction_tail(){
    let mut p=surface_pointer();let origin=p.shown;let mut clicks=vec![];
    p.observe_device_readiness(Some(true));
    for n in 121..230{
        let shock=n==140||n==160;
        let raw=desktop::Raw{sequence:n+1,sensor_ms:n*10,
            accel_mg:if shock{[1000.,0.,1000.]}else{[0.,0.,1000.]},
            gyro_dps:if shock{[70.,0.,0.]}else{[0.;3]}};
        let at=n as f64/100.;
        p.sample_raw_gravity(raw,Some([0.,0.,1000.]),at);
        p.sample(Sample{fused:true,device_ready:Some(true),gyro:raw.gyro_dps,..sample(n+1,n*10,false)},at,bounds());
        if n==141||n==161{p.control(Control{sequence:n,sensor_ms:(n-1)*10,events:CLICK}).unwrap();}
        clicks.extend(p.frame(at,bounds()).buttons);
        assert_eq!(p.shown,origin,"sample{n}: {:?}",p.planar_state());
    }
    assert!(p.planar_state().unwrap().pose_prediction);
    assert_eq!(clicks,vec![Button::Click(origin),Button::Click(origin)]);
}

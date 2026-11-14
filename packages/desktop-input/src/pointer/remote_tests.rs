use super::*;
#[test]fn relative_body_tap_hits_the_visible_cursor_without_rewinding_it(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    for n in 1..32{let t=n as f64/100.;p.sample(sample(n,[0.,20.,0.]),t,bounds());p.frame(t,bounds());}
    let visible=p.shown;p.control(Control{sequence:1,sensor_ms:310,events:CLICK}).unwrap();
    assert_eq!(p.frame(0.311,bounds()).buttons,vec![Button::Click(visible)]);
}
#[test]fn ordinary_mouse_reanchors_a_queued_relative_click_before_native_output(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());
    p.control(Control{sequence:1,sensor_ms:10,events:CLICK}).unwrap();
    let mouse=Point{x:1500.,y:800.};p.external_position(mouse);
    assert_eq!(p.frame(0.02,bounds()).buttons,vec![Button::Click(mouse)]);
}
#[test]fn held_gyro_clutch_stabilizes_motion_but_still_allows_shell_clicks(){
    let mut p=Pointer::new(Settings{key_role:KeyRole::Regrip,..Settings::relative_remote()},Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());
    p.control(Control{sequence:1,sensor_ms:10,events:DOWN}).unwrap();
    p.sample(sample(2,[50.,80.,0.]),0.02,bounds());
    p.control(Control{sequence:2,sensor_ms:20,events:CLICK}).unwrap();
    let f=p.frame(0.02,bounds());assert!(f.position.is_none());assert_eq!(f.buttons,vec![Button::Click(Point{x:960.,y:540.})]);
}
#[test]fn owner_side_tilt_reproduction_right_roll_must_move_right(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    for n in 1..102{let now=n as f64/100.;let mut s=sample(n,[0.,10.,0.]);let angle=(now*10.).to_radians();s.accel=[-angle.sin()*1000.,0.,angle.cos()*1000.];p.sample(s,now,bounds());p.frame(now,bounds());}
    assert!(p.shown.x>1100.,"Owner right-side tilt suppressed: {:?}",p.shown);
}
fn bounds()->Bounds{Bounds{left:0.,top:0.,width:1920.,height:1080.,primary:None}}
fn sample(n:u32,gyro:[f64;3])->Sample{Sample{sequence:n,sensor_ms:n*10,held:false,tap_serial:0,fused:true,device_ready:Some(true),accel:[0.,0.,1000.],gyro,aim:None}}
fn ready()->Pointer{
    // Preserve the128 turn-profile regressions; the new default is side tilt.
    let settings=Settings{relative_horizontal:RelativeHorizontal::Turn,tap_click:false,..Settings::relative_remote()};
    let mut p=Pointer::new(settings,Point{x:960.,y:540.});p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());p
}
#[test]fn small_turns_and_subpixel_motion_survive_the_complete_frame_path(){
    for rate in [0.2,1.,2.]{
        let mut p=ready();let mut outputs=0;
        for n in 2..102{let now=n as f64/100.;p.sample(sample(n,[0.,0.,rate]),now,bounds());if p.frame(now,bounds()).position.is_some(){outputs+=1;}}
        assert!(outputs>0,"{rate}deg/s disappeared below the old per-frame pixel cutoff");
        assert!(p.shown.x<959.,"{rate}deg/s: {:?}",p.shown);
    }
}
#[test]fn zero_rate_stops_immediately_and_device_zero_noise_does_not_creep(){
    let mut p=ready();
    for n in 2..22{let now=n as f64/100.;p.sample(sample(n,[0.,0.,10.]),now,bounds());p.frame(now,bounds());}
    p.sample(sample(22,[0.;3]),0.22,bounds());let before=p.shown;p.frame(0.22,bounds());assert_eq!(p.shown,before);
    for n in 23..1023{let now=n as f64/100.;let noise=if n%2==0{0.03}else{-0.03};p.sample(sample(n,[noise,0.,noise]),now,bounds());p.frame(now,bounds());}
    assert!(p.shown.distance(before)<0.5,"device-scale zero noise {:?}",p.shown);
}
#[test]fn player_space_keeps_yaw_direction_with_a_naturally_pitched_grip(){
    for degrees in [-60_f64,-30.,0.,30.,60.]{
        let a=degrees.to_radians();let up=[0.,a.sin(),a.cos()];
        let gyro=up.map(|x|x*10.);let turn=relative::player_space(gyro,up);
        assert!((turn.x-10.).abs()<0.0001,"grip{degrees}: {turn:?}");
    }
    assert_eq!(relative::player_space([10.,0.,0.],[0.,0.,1.]),Point{x:0.,y:10.});
}
#[test]fn pause_regrip_and_ordinary_mouse_resume_from_the_current_position(){
    let mut p=ready();p.sample(sample(2,[0.,0.,20.]),0.02,bounds());p.frame(0.02,bounds());
    p.pause(true);
    for n in 3..13{let now=n as f64/100.;p.sample(sample(n,[10.,0.,30.]),now,bounds());assert!(p.frame(now,bounds()).position.is_none());}
    let mouse=Point{x:1500.,y:800.};p.external_position(mouse);p.pause(false);
    for n in 13..20{let now=n as f64/100.;p.sample(sample(n,[0.;3]),now,bounds());assert!(p.frame(now,bounds()).position.is_none());}
    assert_eq!(p.shown,mouse);
    p.sample(sample(20,[0.,0.,2.]),0.20,bounds());p.frame(0.20,bounds());assert!(p.shown.x<mouse.x&&p.shown.x>mouse.x-2.);
}
#[test]fn physical_press_freezes_click_jolt_and_short_release_has_no_motion_tail(){
    let mut p=ready();p.sample(sample(2,[0.;3]),0.02,bounds());
    p.control(Control{sequence:1,sensor_ms:20,events:DOWN}).unwrap();let point=p.shown;
    for n in 3..10{let now=n as f64/100.;p.sample(sample(n,[20.,0.,30.]),now,bounds());assert!(p.frame(now,bounds()).position.is_none());}
    p.control(Control{sequence:2,sensor_ms:100,events:UP}).unwrap();
    let f=p.frame(0.1,bounds());assert_eq!(f.buttons,vec![Button::Click(point)]);assert!(f.position.is_none());
    assert_eq!(p.shown,point);
    // Body taps are consumed/ACKed but cannot add an accidental second click.
    assert!(p.control(Control{sequence:3,sensor_ms:100,events:CLICK}).unwrap());assert!(p.frame(0.11,bounds()).buttons.is_empty());
}
#[test]fn physical_hold_starts_drag_at180ms_and_pause_releases_it_once(){
    let mut p=ready();p.sample(sample(2,[0.;3]),0.02,bounds());
    p.control(Control{sequence:1,sensor_ms:20,events:DOWN}).unwrap();p.frame(0.02,bounds());
    assert!(p.frame(0.19,bounds()).buttons.is_empty());
    assert!(matches!(p.frame(0.201,bounds()).buttons.as_slice(),[Button::Down(_)]));
    p.pause(true);assert_eq!(p.frame(0.21,bounds()).buttons,vec![Button::Up]);assert!(p.frame(0.22,bounds()).buttons.is_empty());
}
#[test]fn recorded_typec_front_lift_moves_up_with_relative_pitch_sign(){
    let fixture:serde_json::Value=serde_json::from_str(include_str!("fixtures/typec-forward66830.json")).unwrap();
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});let mut origin=None;let mut highest=540_f64;
    for h in fixture["packets"].as_array().unwrap(){
        let h=h.as_str().unwrap();let bytes=(0..h.len()).step_by(2).map(|i|u8::from_str_radix(&h[i..i+2],16).unwrap()).collect::<Vec<_>>();
        let s=Sample::parse(&bytes).unwrap();let start=*origin.get_or_insert(s.sensor_ms);let now=s.sensor_ms.wrapping_sub(start)as f64/1000.;
        p.sample(s,now,bounds());if let Some(pos)=p.frame(now,bounds()).position{highest=highest.min(pos.y);}
    }
    assert!(highest<440.,"physical front lift must move up, got{highest}");
}

#[test]fn tilt_direction_and_fine_motion_are_independent_of_pitch_grip(){
    for pitch in [-60_f64,0.,60.]{for rate in [-2_f64,-0.2,0.2,2.]{
        let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
        for n in 1..202{let now=n as f64/100.;let mut s=sample(n,[0.,rate,0.]);let a=pitch.to_radians();s.accel=[0.,a.sin()*1000.,a.cos()*1000.];p.sample(s,now,bounds());p.frame(now,bounds());}
        assert!((p.shown.x-960.)*rate>0.,"pitch{pitch}/roll{rate}: {:?}",p.shown);
        assert_eq!(p.shown.y,540.);
    }}
}
#[test]fn tilt_keeps_the_same_pitch_response_as_the128_turn_profile(){
    let mut turn=ready();let mut tilt=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    tilt.sample(sample(1,[0.;3]),0.01,bounds());tilt.frame(0.01,bounds());
    for n in 2..102{let now=n as f64/100.;let s=sample(n,[-5.,0.,0.]);turn.sample(s,now,bounds());tilt.sample(s,now,bounds());turn.frame(now,bounds());tilt.frame(now,bounds());assert_eq!(tilt.shown,turn.shown);}
}
#[test]fn body_taps_click_once_per_physical_edge_without_an_impact_tail(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    for n in 1..22{let now=n as f64/100.;p.sample(sample(n,[0.;3]),now,bounds());p.frame(now,bounds());}
    let point=p.shown;p.sample(sample(22,[100.,80.,0.]),0.22,bounds());
    let edge=Control{sequence:1,sensor_ms:220,events:CLICK};
    assert!(p.control(edge).unwrap());assert!(!p.control(edge).unwrap());
    let frame=p.frame(0.22,bounds());assert_eq!(frame.buttons,vec![Button::Click(point)]);assert!(frame.position.is_none());
    p.sample(sample(23,[0.;3]),0.23,bounds());assert!(p.frame(0.23,bounds()).position.is_none());
    // Two intentional physical taps remain two OS clicks, without a new timer.
    p.control(Control{sequence:2,sensor_ms:350,events:CLICK}).unwrap();
    p.control(Control{sequence:3,sensor_ms:480,events:CLICK}).unwrap();
    assert_eq!(p.frame(0.48,bounds()).buttons,vec![Button::Click(point),Button::Click(point)]);
    p.pause(true);p.control(Control{sequence:4,sensor_ms:500,events:CLICK}).unwrap();p.pause(false);
    assert!(p.frame(0.5,bounds()).buttons.is_empty());
}

#[test]fn held_clutch_regrips_without_returning_the_cursor_or_clicking(){
    let mut p=Pointer::new(Settings{key_role:KeyRole::Regrip,..Settings::relative_remote()},Point{x:960.,y:540.});
    for n in 1..22{let t=n as f64/100.;p.sample(sample(n,[0.,10.,0.]),t,bounds());p.frame(t,bounds());}
    let target=p.shown;p.control(Control{sequence:1,sensor_ms:220,events:DOWN}).unwrap();
    assert!(p.metrics.regripping);
    for n in 22..72{let t=n as f64/100.;p.sample(sample(n,[5.,-10.,0.]),t,bounds());let f=p.frame(t,bounds());assert!(f.position.is_none()&&f.buttons.is_empty());}
    p.control(Control{sequence:2,sensor_ms:710,events:CLICK}).unwrap();
    let steady=p.frame(0.711,bounds());assert!(steady.position.is_none());assert_eq!(steady.buttons,vec![Button::Click(target)]);
    p.control(Control{sequence:3,sensor_ms:720,events:UP}).unwrap();assert!(!p.metrics.regripping);
    let f=p.frame(0.72,bounds());assert!(f.position.is_none()&&f.buttons.is_empty());assert_eq!(p.shown,target);
    for n in 73..83{let t=n as f64/100.;p.sample(sample(n,[0.;3]),t,bounds());assert!(p.frame(t,bounds()).position.is_none());}
    for n in 83..94{let t=n as f64/100.;p.sample(sample(n,[0.,2.,0.]),t,bounds());p.frame(t,bounds());}
    assert!(p.shown.x>target.x);assert_eq!(p.shown.y,target.y);
    p.control(Control{sequence:4,sensor_ms:930,events:CLICK}).unwrap();assert!(matches!(p.frame(0.931,bounds()).buttons.as_slice(),[Button::Click(_)]));
}
#[test]fn early_tap_feedback_counts_received_edges_without_faking_a_calibrated_click(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    let tap=Control{sequence:1,sensor_ms:10,events:CLICK};p.control(tap).unwrap();p.control(tap).unwrap();
    assert_eq!(p.metrics.tap_events,1);assert!(p.frame(0.01,bounds()).buttons.is_empty());
    p.sample(sample(1,[0.;3]),0.02,bounds());p.frame(0.02,bounds());
    p.control(Control{sequence:2,sensor_ms:20,events:CLICK}).unwrap();assert_eq!(p.metrics.tap_events,2);
    assert!(matches!(p.frame(0.021,bounds()).buttons.as_slice(),[Button::Click(_)]));
}
#[test]fn forwarded_held_tap_does_not_add_a_second_click_to_legacy_key_click_drag(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());
    p.control(Control{sequence:1,sensor_ms:10,events:DOWN}).unwrap();
    p.control(Control{sequence:2,sensor_ms:20,events:CLICK}).unwrap();
    assert!(p.frame(0.02,bounds()).buttons.is_empty());
    p.control(Control{sequence:3,sensor_ms:50,events:UP}).unwrap();
    assert_eq!(p.frame(0.05,bounds()).buttons,vec![Button::Click(Point{x:960.,y:540.})]);
}
#[test]fn clutch_release_does_not_cancel_user_pause_and_gaps_cannot_leave_it_held(){
    let mut p=Pointer::new(Settings{key_role:KeyRole::Regrip,..Settings::relative_remote()},Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());
    p.control(Control{sequence:1,sensor_ms:10,events:DOWN}).unwrap();p.pause(true);
    p.control(Control{sequence:2,sensor_ms:20,events:UP}).unwrap();assert!(p.metrics.paused);assert!(!p.metrics.regripping);
    p.pause(false);p.control(Control{sequence:3,sensor_ms:30,events:DOWN}).unwrap();
    assert!(p.frame(0.5,bounds()).buttons.is_empty());assert!(!p.metrics.regripping);assert!(p.metrics.stream_stale);
}

#[test]fn reliable_shell_click_cannot_be_followed_by_same_frame_impact_movement(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());let point=p.shown;
    p.control(Control{sequence:1,sensor_ms:10,events:CLICK}).unwrap();
    // The next CIM is allowed to arrive before the120Hz native frame.
    p.sample(sample(2,[120.,200.,0.]),0.02,bounds());
    let f=p.frame(0.02,bounds());assert_eq!(f.buttons,vec![Button::Click(point)]);
    assert!(f.position.is_none(),"click immediately followed by impact movement: {:?}",f.position);
    assert_eq!(p.shown,point);
}
#[test]fn actual_owner136_rebound_is_discarded_without_replaying_its_delta(){
    let fixture:serde_json::Value=serde_json::from_str(include_str!("fixtures/owner136-tap-rebound.json")).unwrap();
    for tap in fixture["taps"].as_array().unwrap(){
        let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
        p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());let point=p.shown;
        p.control(Control{sequence:1,sensor_ms:10,events:CLICK}).unwrap();
        assert_eq!(p.frame(0.011,bounds()).buttons,vec![Button::Click(point)]);
        let mut seq=1;
        for row in tap["after"].as_array().unwrap(){
            let delta=row["deltaMs"].as_u64().unwrap()as u32;if delta>=150{break;}
            seq+=1;let mut s=sample(seq,[0.;3]);s.sensor_ms=10+delta;
            s.gyro=std::array::from_fn(|i|row["gyroCentiDps"][i].as_f64().unwrap()/100.);
            p.sample(s,s.sensor_ms as f64/1000.,bounds());
            assert!(p.frame(s.sensor_ms as f64/1000.,bounds()).position.is_none(),"actual impact moved click cursor");
            assert_eq!(p.shown,point);
        }
        // Discarded samples must not become a delayed movement after settling.
        seq+=1;let mut s=sample(seq,[0.;3]);s.sensor_ms=170;p.sample(s,0.17,bounds());assert!(p.frame(0.17,bounds()).position.is_none());
        seq+=1;s=sample(seq,[0.,2.,0.]);s.sensor_ms=180;p.sample(s,0.18,bounds());p.frame(0.18,bounds());assert!(p.shown.x>point.x);
    }
}
#[test]fn shell_click_settling_preserves_double_clicks_and_the_ordinary_mouse(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    p.sample(sample(1,[0.;3]),0.01,bounds());p.frame(0.01,bounds());
    p.control(Control{sequence:1,sensor_ms:10,events:CLICK}).unwrap();p.frame(0.011,bounds());
    let mouse=Point{x:1400.,y:700.};p.external_position(mouse);
    p.sample(sample(2,[100.,200.,0.]),0.02,bounds());assert!(p.frame(0.02,bounds()).position.is_none());assert_eq!(p.shown,mouse);
    p.control(Control{sequence:2,sensor_ms:20,events:CLICK}).unwrap();assert_eq!(p.frame(0.021,bounds()).buttons,vec![Button::Click(mouse)]);
    p.pause(true);p.pause(false);p.sample(sample(3,[0.,2.,0.]),0.03,bounds());p.frame(0.03,bounds());assert!(p.shown.x>mouse.x,"explicit resume retains no stale click freeze");
}

use super::*;
#[test]fn an_unresolved_regional_candidate_does_not_cancel_a_planar_stroke(){
    let settings=Settings{desktop_motion:true,contact_regions:true,
        contact_profile:Some(contact::Profile{schema:2,left:vec![[0.;6];8],right:vec![[1.;6];8],left_threshold:0.,right_threshold:0.}),
        ..Settings::relative_remote()};
    let(mut candidate,mut reference)=(Pointer::new(settings.clone(),Point{x:960.,y:540.}),Pointer::new(settings,Point{x:960.,y:540.}));
    for n in 1..241{
        let at=n as f64/100.;let acceleration=if (150..165).contains(&n){100.}else{0.};
        for p in [&mut candidate,&mut reference]{
            p.observe_device_readiness(Some(true));
            p.sample_raw_gravity(desktop::Raw{wide_gyro:false,sequence:n,sensor_ms:n*10,accel_mg:[acceleration,0.,1000.],gyro_dps:[0.;3]},Some([0.,0.,1000.]),at);
        }
        // No matching impact exists in these samples. The event must time out
        // without resetting the stroke either on arrival or on completion.
        if n==166{candidate.control(Control{sequence:1,sensor_ms:n*10,events:CLICK}).unwrap();}
        let f=candidate.frame(at,bounds());reference.frame(at,bounds());assert!(f.buttons.is_empty());
        // Candidate quarantine may discard output briefly, but neither its
        // arrival nor timeout may erase the observed coasting velocity.
        if (166..225).contains(&n){assert!(candidate.planar_state().unwrap().velocity_mps[0]>0.08,"candidate erased established velocity at sample{n}");}
    }
    assert_eq!(candidate.contacts.status.missed_windows,1);
    assert!(candidate.shown.x>1060.);
}
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
#[test]fn desktop_ready_waits_for_the_actual_cim6_calibration_flag(){
    let mut p=Pointer::new(Settings{desktop_motion:true,..Settings::relative_remote()},Point{x:960.,y:540.});
    for n in 1..121{
        p.observe_device_readiness(Some(false));
        p.sample_raw_gravity(desktop::Raw{wide_gyro:false,sequence:n,sensor_ms:n*10,accel_mg:[0.,0.,1000.],gyro_dps:[20.,10.,5.]},Some([0.,0.,1000.]),n as f64/100.);
        assert!(!p.metrics.calibrated);
    }
    p.observe_device_readiness(Some(true));
    for n in 121..181{p.sample_raw_gravity(desktop::Raw{wide_gyro:false,sequence:n,sensor_ms:n*10,accel_mg:[0.,0.,1000.],gyro_dps:[0.;3]},Some([0.,0.,1000.]),n as f64/100.);}
    assert!(p.metrics.calibrated&&p.planar_state().unwrap().pose_prediction);
    assert_eq!(p.shown,Point{x:960.,y:540.});
}
#[test]fn sensor_clock_rate_cannot_hide_slow_wallclock_delivery_or_erase_recovery_time(){
    let mut p=Pointer::new(Settings::relative_remote(),Point{x:960.,y:540.});
    for n in 1..21{p.sample(sample(n,[0.;3]),n as f64*0.2,bounds());}
    assert!((p.metrics.sensor_hz-100.).abs()<0.01);
    assert!((p.metrics.receive_hz-5.).abs()<0.01);
    p.frame(6.,bounds());assert!(p.metrics.receive_hz<4.,"silence must remain in the rate denominator");
    p.begin_stream();p.sample(sample(1,[0.;3]),6.5,bounds());
    assert!(p.metrics.receive_hz<5.,"recovery must not reset the wallclock denominator");
}
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

#[test]
#[ignore="Local Owner142 raw trace only; no private data is bundled"]
fn owner142_recorded_taps_and_impact_motion_replay(){
    // Diagnostic ablation only: reuse actual board Fusion gravity without
    // enabling the second host pose predictor. No production setting changes.
    let board_direct=std::env::var_os("COMPANION_BOARD_DIRECT_REPLAY").is_some();
    let root=std::path::PathBuf::from(std::env::var("COMPANION_CONTACT_EVALUATION").expect("Owner trace"));
    let receipt:serde_json::Value=serde_json::from_str(&std::fs::read_to_string(root.join("result.json")).unwrap()).unwrap();
    // A failed native mode-exit can omit finalPointer. Preserve that failure;
    // replay the actual last IPC snapshot instead of inventing default settings.
    let calls:serde_json::Value=if receipt["sessions"][0]["finalPointer"].is_null(){
        serde_json::from_str(&std::fs::read_to_string(root.join("native-1/native-calls.json")).unwrap()).unwrap()
    }else{serde_json::Value::Null};
    let snapshot=if calls.is_null(){&receipt["sessions"][0]["finalPointer"]}else{
        &calls.as_array().unwrap().iter().rev().find(|v|v["cmd"]=="get_companion_pointer"&&v["response"]["value"]["settings"].is_object()).expect("actual native pointer snapshot")["response"]["value"]
    };
    let settings:Settings=serde_json::from_value(snapshot["settings"].clone()).unwrap();
    let rows:serde_json::Value=serde_json::from_str(&std::fs::read_to_string(root.join("offline-diagnosis/timeline.json")).unwrap()).unwrap();
    let mut p=Pointer::new(settings,Point{x:960.,y:540.});
    let rows=rows.as_array().unwrap();let zero=rows[0]["hostUs"].as_u64().unwrap();
    let mut next_frame=0.;let mut clicks=vec![];let mut positions=vec![];let mut states=vec![];let mut sequence=None;let mut inferred_restarts=0;
    let observe_frames=std::env::var_os("COMPANION_OBSERVE_FRAME_LATENCY").is_some();let mut deliveries=vec![];
    for row in rows{
        let at=(row["hostUs"].as_u64().unwrap()-zero)as f64/1e6;
        while next_frame<at{
            let f=p.frame(next_frame,bounds());
            if observe_frames{deliveries.push(serde_json::json!({"at":next_frame,"emitted":f.position.is_some(),"stale":p.metrics.stream_stale,"sampleAgeS":p.clock_offset.map(|off|next_frame-p.sensor_clock-off)}));}
            clicks.extend(f.buttons);positions.push((next_frame,p.shown));next_frame+=1./60.;
        }
        if row["kind"]=="motion"{
            let h=row["packet"].as_str().unwrap();let bytes=(0..h.len()).step_by(2).map(|i|u8::from_str_radix(&h[i..i+2],16).unwrap()).collect::<Vec<_>>();
            let raw=desktop::Raw::parse(&bytes).unwrap();
            if p.settings.desktop_motion&&sequence.is_some_and(|old:u32|raw.sequence.wrapping_sub(old)>=0x8000_0000){p.begin_stream();inferred_restarts+=1;}
            let fused=Sample::parse(&bytes).unwrap();sequence=Some(raw.sequence);
            if board_direct&&fused.device_ready==Some(true){p.desktop_device_ready=None;}
            p.sample_raw_gravity(raw,Some(fused.accel),at);p.sample(fused,at,bounds());
            if p.settings.desktop_motion{states.push(serde_json::json!({"at":at,"calibrated":p.metrics.calibrated,"surfacePaused":p.metrics.surface_paused,"tapBlocked":p.tap_motion.blocked(),"state":p.planar_state()}));}
        }else if row["kind"]=="calibrate"{p.calibrate();}
        else{p.control(Control{sequence:row["sequence"].as_u64().unwrap()as u32,sensor_ms:row["sensorMs"].as_u64().unwrap()as u32,events:row["events"].as_u64().unwrap()as u16}).unwrap();}
    }
    let left=clicks.iter().filter(|x|matches!(x,Button::Click(_))).count();let right=clicks.iter().filter(|x|matches!(x,Button::RightClick(_))).count();
    let mut report=serde_json::json!({"left":left,"right":right,"tapEvents":p.metrics.tap_events,"contacts":p.contact_status(),"positions":positions,"states":states,"inferredStreamRestartsFromSequenceReset":inferred_restarts,"labelsKnown":false,"boardDirectDiagnostic":board_direct,"scope":"Actual raw trace/core replay, fixed1920x1080 bounds and60Hz output; positions are predictions, not recorded OS coordinates. Planar stream restart inferred only from a backwards sequence. Board-direct, when explicitly enabled, is diagnostic, not shipped runtime."});
    if observe_frames{report["frameDelivery"]=serde_json::json!(deliveries);}
    let output=std::env::var("COMPANION_CONTACT_REPLAY_OUT").expect("report destination");std::fs::write(output,serde_json::to_string_pretty(&report).unwrap()).unwrap();
    if std::env::var_os("COMPANION_EXPECT_DESK_REPAIR").is_some(){
        // Explicit Owner155 clarification: this capture was pushed on the
        // desk. Do not infer intended motion labels for other Owner captures.
        assert!(states.iter().filter(|s|s["calibrated"]==true).all(|s|s["state"]["surface"].is_null()||s["state"]["surface"]["phase"]=="ready"),"reported desk sliding must not latch the lift-return timer");
    }
    let expected=snapshot["metrics"]["tapEvents"].as_u64().unwrap()as usize;
    println!("Actual{expected} taps ->left{left}/right{right}; uncertain{}; labels unknown",p.contact_status().uncertain);
    if std::env::var_os("COMPANION_EXPECT_CONTACT_REPAIR").is_some(){assert_eq!(clicks.len(),expected,"reliable physical taps must reach the nearest GRT template, not all be rejected by a three-example radius");}
    if let Ok(text)=std::fs::read_to_string(root.join("offline-diagnosis/native-baseline.json")){
        let baseline:serde_json::Value=serde_json::from_str(&text).unwrap();
        if baseline["acceptedBaseline"]==true{assert_eq!(left,baseline["left"].as_u64().unwrap()as usize);assert_eq!(right,baseline["right"].as_u64().unwrap()as usize);}
    }
}

#[test]
#[ignore="Local normal147 stationary CIM6 capture; never bundled"]
fn actual_surface_stationary_readiness_does_not_become_a_false_lift(){
    for root in std::env::var("COMPANION_SURFACE_EVALUATION").expect("explicit local surface capture").split(';'){
        check_surface_stationary_trace(std::path::Path::new(root));
    }
}
fn check_surface_stationary_trace(root:&std::path::Path){
    let proof:serde_json::Value=serde_json::from_str(&std::fs::read_to_string(root.join("../../runtime-proof.json")).unwrap()).unwrap();
    let settings:Settings=serde_json::from_value(proof["pointerSettings"].clone()).unwrap();
    let mut p=Pointer::new(settings,Point{x:960.,y:540.});
    let log=std::fs::read_to_string(root.join("native/app.log")).unwrap();
    let(mut first,mut count,mut ready,mut still,mut path,mut last)=(None,0usize,0usize,0usize,0.,p.shown);
    let mut previously_moving=false;
    for line in log.lines().filter(|s|s.contains("desktop_input_motion_wire")){
        let h=line.split("packet=").nth(1).unwrap().split_whitespace().next().unwrap();
        let bytes=(0..h.len()).step_by(2).map(|i|u8::from_str_radix(&h[i..i+2],16).unwrap()).collect::<Vec<_>>();
        let raw=desktop::Raw::parse(&bytes).unwrap();let zero=*first.get_or_insert(raw.sensor_ms);let at=raw.sensor_ms.wrapping_sub(zero)as f64/1000.;
        let fused=Sample::parse(&bytes).unwrap();p.sample_raw_gravity(raw,Some(fused.accel),at);p.sample(fused,at,bounds());p.frame(at,bounds());
        if let Some(c)=&p.coarse{
            if std::env::var_os("COMPANION_SURFACE_MOVING_DIAGNOSTICS").is_some()&&at>5.&&
                (c.desktop.state.moving!=previously_moving||c.desktop.state.moving&&c.desktop.state.translation_inhibited){
                println!("surface moving edge at{at:.3} {:?}",c.desktop.state);
            }
            previously_moving=c.desktop.state.moving;
        }
        if at>5.{count+=1;if !p.metrics.surface_paused{ready+=1;}if let Some(c)=&p.coarse{if c.desktop.state.stationary{still+=1;}}
            path+=(p.shown.x-last.x).hypot(p.shown.y-last.y);
        }
        last=p.shown;
        if count>0&&count%100==0{println!("surface captured at{at:.2} {:?}",p.coarse.as_ref().unwrap().desktop.state);}
    }
    println!("Actual stationary capture: samples{count},ready{ready},rest{still},path{path:.4}px");
    assert!(count>2000&&still>count*9/10);
    assert!(ready>count*9/10,"stationary hardware trace entered a false lift");
    assert!(path<3.,"stationary raw data caused{path}px predicted cursor movement");
}

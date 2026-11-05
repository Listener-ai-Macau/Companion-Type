use crate::action_export::{self, Action, CalendarReminderSelection, CalendarSlotSelection};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::HashSet;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Request {
    session_key: String,
    title: String,
    tasks: Vec<Task>,
    #[serde(default)]
    draft: bool,
    reminder_minutes: Option<u16>,
    reminders: Option<Vec<CalendarReminderSelection>>,
    slots: Option<Vec<CalendarSlotSelection>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Task {
    id: Option<String>,
    text: String,
    completed: bool,
    due: Option<String>,
}

pub fn export_json(input: &str) -> Result<String, String> {
    if input.len() > 4 * 1024 * 1024 {
        return Err("日历数据过大，请分批导出。".into());
    }
    let request: Request = serde_json::from_str(input)
        .map_err(|e| format!("日历数据格式不正确：{e}"))?;
    if request.session_key.trim().is_empty() || request.tasks.len() > 4096 {
        return Err("录音标识为空或待办数量超过上限，请重新选择。".into());
    }
    let mut seen=HashSet::new();
    let mut ids=Vec::with_capacity(request.tasks.len());
    for task in &request.tasks {
        let id=match &task.id {
            Some(id) if !id.trim().is_empty() && seen.insert(id) => {
                let mut hash=Sha256::new();
                for field in ["companion-mobile-calendar-task", &request.session_key, id] {
                    hash.update((field.len() as u64).to_be_bytes());
                    hash.update(field.as_bytes());
                }
                Some(format!("{:x}@companion-mobile",hash.finalize()))
            },
            Some(_) => return Err("待办标识为空或重复，请重新选择。".into()),
            None => None,
        };
        ids.push(id);
    }
    let actions: Vec<Action> = request.tasks.into_iter().map(|task| Action {
        text: task.text, completed: task.completed, due: task.due,
    }).collect();
    let (calendar, items) = action_export::calendar_events_with_slots_and_ids(
        &request.session_key, "offlineStore", &request.title, &actions, request.draft,
        &action_export::stamp_now(), request.reminder_minutes, request.reminders.as_deref(),
        None, request.slots.as_deref(), Some(&ids),
    )?;
    serde_json::to_string(&serde_json::json!({"calendar": calendar, "items": items}))
        .map_err(|e| format!("无法生成日历数据：{e}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    #[test]
    fn confirmed_tasks_export_locally_and_completed_are_excluded() {
        let request = json!({"sessionKey":"session-1", "title":"会议",
            "tasks":[{"text":"完成报价", "completed":true, "due":"2026-11-01"},
            {"text":"如果客户修改，确认交货时间", "completed":false, "due":"2026-11-02T14:00:00+08:00"}],
            "reminderMinutes":30});
        let result: Value = serde_json::from_str(&export_json(&request.to_string()).unwrap()).unwrap();
        let ics = result["calendar"].as_str().unwrap().replace("\r\n ", "");
        assert_eq!(ics.matches("BEGIN:VEVENT").count(), 1);
        assert!(!ics.contains("完成报价"));
        assert!(ics.contains("如果客户修改"));
        assert!(ics.contains("DTSTART:20261102T060000Z\r\n"));
        assert!(ics.contains("TRIGGER;RELATED=START:-PT30M\r\n"));
        assert_eq!(result["items"][0]["status"], "completed");
    }

    #[test]
    fn requires_confirmed_date_and_rejects_unknown_inputs() {
        let request = json!({"sessionKey":"session", "title":"会议", "tasks":[
            {"text":"发报价", "completed":false, "due":"下周一"}]});
        assert!(export_json(&request.to_string()).is_err());
        let mut invalid = request;
        invalid["unexpected"] = json!(true);
        assert!(export_json(&invalid.to_string()).is_err());
    }

    #[test]
    fn explicit_slot_and_individual_reminder_use_preview_uid() {
        let mut request = json!({"sessionKey":"session", "title":"会议", "tasks":[
            {"text":"检查样品", "completed":false, "due":"2026-11-02"}]});
        let first: Value = serde_json::from_str(&export_json(&request.to_string()).unwrap()).unwrap();
        let uid = first["items"][0]["uid"].as_str().unwrap();
        request["slots"] = json!([{"uid":uid, "slot":{"start":"2026-11-02T14:00:00+08:00", "end":"2026-11-02T15:00:00+08:00"}}]);
        request["reminders"] = json!([{"uid":uid, "reminder":{"kind":"at", "at":"2026-11-02T13:30:00+08:00"}}]);
        let second: Value = serde_json::from_str(&export_json(&request.to_string()).unwrap()).unwrap();
        let ics = second["calendar"].as_str().unwrap();
        assert!(ics.contains("DTSTART:20261102T060000Z\r\n"));
        assert!(ics.contains("DTEND:20261102T070000Z\r\n"));
        assert!(ics.contains("20261102T053000Z"));
    }

    #[test]
    fn saved_task_identity_survives_edits_and_reordering() {
        let first = json!({"sessionKey":"recording", "title":"会议", "tasks":[
            {"id":"task-a", "text":"检查样品", "completed":false, "due":"2026-11-02"},
            {"id":"task-b", "text":"发送报价", "completed":false, "due":"2026-11-03"}]});
        let a: Value = serde_json::from_str(&export_json(&first.to_string()).unwrap()).unwrap();
        let mut changed = json!({"sessionKey":"recording", "title":"会议", "tasks":[
            {"id":"task-b", "text":"发送报价", "completed":false, "due":"2026-11-03"},
            {"id":"task-a", "text":"检查蓝色样品", "completed":false, "due":"2026-11-04"}]});
        changed["reminders"]=json!([{"uid":a["items"][0]["uid"],"reminder":{"kind":"at","at":"2026-11-04T13:30:00+08:00"}}]);
        let b: Value = serde_json::from_str(&export_json(&changed.to_string()).unwrap()).unwrap();
        assert_eq!(a["items"][0]["uid"], b["items"][1]["uid"]);
        assert_eq!(a["items"][1]["uid"], b["items"][0]["uid"]);
        assert!(b["calendar"].as_str().unwrap().replace("\r\n ", "").contains(b["items"][1]["uid"].as_str().unwrap()));
        assert!(b["calendar"].as_str().unwrap().contains("20261104T053000Z"));
        let mut duplicate=changed.clone();
        duplicate["tasks"][0]["id"]=json!("task-a");
        assert!(export_json(&duplicate.to_string()).is_err());
        changed["sessionKey"]=json!("another-recording");
        changed.as_object_mut().unwrap().remove("reminders");
        let other: Value=serde_json::from_str(&export_json(&changed.to_string()).unwrap()).unwrap();
        assert_ne!(other["items"][1]["uid"],a["items"][0]["uid"]);
    }
}

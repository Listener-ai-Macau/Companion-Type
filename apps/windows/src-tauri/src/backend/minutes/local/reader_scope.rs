//! Retain verified qualifications to a reported approach without creating assignments.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::super::source_resolution::split_turn_label;
use super::{
    source_context,
    source_review::{self, Role},
    timed_evidence::Timing,
};

struct Sentence<'a> {
    speaker: Option<&'a str>,
    text: &'a str,
    source: &'a str,
}

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(*cue))
}

fn boundary(text: &str) -> bool {
    has(
        text,
        &[
            "下一个问题",
            "下一项",
            "另一个问题",
            "换个话题",
            "接下来讨论",
            "论坛内容就",
            "到这里结束",
        ],
    )
}

fn stated(text: &str) -> bool {
    !source_context::question_only(text)
        && !boundary(text)
        && !has(
            text,
            &[
                "举例",
                "假设",
                "假如",
                "听说",
                "据说",
                "如果可以",
                "建议以后",
                "尚未决定",
                "暂时还没定",
                "不再",
                "取消",
            ],
        )
}

fn pair_scope(text: &str) -> Option<&str> {
    ["分层", "分组", "分级", "分类"]
        .into_iter()
        .find(|cue| text.contains(cue))
}

fn delivery_channel(text: &str, modes: &[&str]) -> bool {
    has(text, modes) && has(text, &["我们", "本组", "本单位", "本部门", "我们这边"])
}

pub(super) fn grounded_reported_scopes(
    source: &[Value],
    audit: &source_review::Review,
    timing: Option<&Timing<'_>>,
) -> Vec<Vec<usize>> {
    static SPLIT_COUNT: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"[零一二两三四五六七八九十百0-9]+\s*(?:个|种|类|组|批|层|档|节|次)")
            .expect("a literal quantity distinguishes the scope")
    });
    static LIMIT: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"(?:不超过|不多于|最多)\s*[零一二两三四五六七八九十百0-9]+\s*(?:分钟|秒钟|小时)|[零一二两三四五六七八九十百0-9]+\s*(?:分钟|秒钟|小时)以内"
    ).expect("a stated duration limit")
    });
    static AUTHORITY: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"(?:是由|应由|应该由|需要由|由)[\p{Han}]{1,22}?(?:部门|机构|委员会|负责人|主管|总经办|管理层|教育厅|工作组)(?:统一|正式|最后|来|负责)*?(?:确定|决定|审批|批准)"
    ).expect("the stated decision authority")
    });
    let mut current = None;
    let rows: Vec<_> = source
        .iter()
        .map(|row| {
            let raw = row["text"].as_str().expect("source text").trim();
            let body = match split_turn_label(raw) {
                Some((speaker, body)) => {
                    current = Some(speaker);
                    body.trim()
                }
                None => raw,
            };
            Sentence {
                speaker: current,
                text: body,
                source: row["id"].as_str().expect("source id"),
            }
        })
        .collect();
    let rows = rows.as_slice();
    let following = |start: usize, distance: usize| {
        (start + 1..(start + 1 + distance).min(rows.len())).take_while(move |&i| {
            rows[i].speaker == rows[start].speaker
                && !boundary(rows[i].text)
                && timing.is_none_or(|time| time.speech_gap_within(i - 1, i, 3_000))
        })
    };
    let mut groups = Vec::new();
    for (i, row) in rows.iter().enumerate() {
        let text = row.text;
        if row.speaker.is_none() || !stated(text) {
            continue;
        }
        let mark = audit.by_source.get(row.source);
        if mark == Some(&Role::Condition)
            && has(text, &["实施", "实行", "采用", "安排", "执行", "开展"])
            && has(text, &["我们", "本组", "本部门", "本单位"])
            && SPLIT_COUNT.is_match(text)
        {
            let related = pair_scope(text).and_then(|scope| {
                following(i, 3).find(|&j| {
                    let complement = rows[j].text;
                    stated(complement)
                        && complement.contains(scope)
                        && has(
                            complement,
                            &["也是", "另一个", "另外", "同样", "也按", "还按"],
                        )
                        && has(complement, &["安排", "处理", "执行", "交付", "配置"])
                })
            });
            if let Some(related) = related {
                groups.push(vec![i, related]);
            }
        }

        if mark == Some(&Role::Decision)
            && AUTHORITY.is_match(text)
            && !super::source_authority::Authority::from_source(text)
                .literal_collective_decision(text)
        {
            let baseline = (i.saturating_sub(4)..i)
                .rev()
                .take_while(|&j| {
                    rows[j].speaker == row.speaker
                        && !boundary(rows[j].text)
                        && timing.is_none_or(|time| time.speech_gap_within(j, j + 1, 3_000))
                })
                .find(|&j| {
                    let prior = rows[j].text;
                    stated(prior)
                        && has(prior, &["按照", "沿用", "维持"])
                        && has(prior, &["正常", "平时", "原计划", "既有", "原来的"])
                        && has(
                            prior,
                            &["进度", "在开展", "继续推进", "正常运转", "照常", "在安排"],
                        )
                });
            if let Some(baseline) = baseline {
                let other_holiday_scope = has(text, &["假期", "放假", "暑假", "寒假"])
                    .then(|| {
                        (i.saturating_sub(9)..baseline)
                            .rev()
                            .take_while(|&j| {
                                !boundary(rows[j].text)
                                    && timing
                                        .is_none_or(|time| time.speech_gap_within(j, j + 1, 3_000))
                            })
                            .find(|&j| {
                                let scope = rows[j].text;
                                stated(scope)
                                    && has(scope, &["假期", "放假", "暑假", "寒假"])
                                    && has(
                                        scope,
                                        &[
                                            "还没有权利",
                                            "没有权利来定",
                                            "没有权限",
                                            "无权决定",
                                            "本单位不能决定",
                                        ],
                                    )
                                    && has(
                                        scope,
                                        &[
                                            "部门来定",
                                            "教育厅来定",
                                            "主管来定",
                                            "管理层来定",
                                            "委员会来定",
                                        ],
                                    )
                            })
                    })
                    .flatten();
                groups.push(
                    other_holiday_scope
                        .into_iter()
                        .chain([baseline, i])
                        .collect(),
                );
            }
        }

        if delivery_channel(text, &["线上", "在线"])
            && has(text, &["只有", "就", "只安排", "只开", "只设"])
            && SPLIT_COUNT.is_match(text)
        {
            let counterpart = following(i, 5).find(|&j| {
                let other = rows[j].text;
                stated(other)
                    && delivery_channel(other, &["线下"])
                    && has(other, &["采取", "安排", "采用", "执行", "提供"])
            });
            if let Some(counterpart) = counterpart {
                let media = following(counterpart, 2).find(|&j| {
                    let detail = rows[j].text;
                    stated(detail)
                        && has(detail, &["录制", "制作", "发送", "推送"])
                        && has(detail, &["视频", "音频", "微课", "录音"])
                });
                let limit = media.and_then(|media| {
                    following(media, 2).find(|&j| {
                        let detail = rows[j].text;
                        stated(detail)
                            && has(detail, &["视频", "音频", "微课", "录音"])
                            && LIMIT.is_match(detail)
                    })
                });
                if let Some(limit) = limit {
                    groups.push(vec![i, counterpart, limit]);
                }
            }
        }

        if has(text, &["我认为", "我觉得", "我们认为", "我们强调"])
            && has(text, &["必须把", "要把", "首先把"])
            && has(text, &["放在首位", "放在第一位"])
            && has(
                text,
                &["不能脱离", "不能只追求", "不能单纯", "不能光看", "不能为了"],
            )
        {
            groups.push(vec![i]);
        }
    }
    groups
}

#[cfg(test)]
#[test]
fn scope_evidence_neither_infers_a_new_decision_nor_crosses_speaker_boundaries() {
    let mut rows = [
        "说话人1: 我们实行分级响应，安排两个级别的保障。",
        "另外，工单处理也是分级来执行。",
        "说话人2: 这段时间仍然按照平时进度在开展。",
        "至于什么时候停运，我觉得是由主管部门来确定。",
        "说话人3: 我们线上只有三节课，就给专业讲解。",
        "那操作训练呢？",
        "我们就是采取线下方式。",
        "每次训练都会录制一个短视频。",
        "这个视频大概三分钟以内。",
        "我认为必须把材料安全放在首位，不能只追求外观。",
    ]
    .iter()
    .enumerate()
    .map(|(i, text)| serde_json::json!({"id":format!("e{i}"),"text":text}))
    .collect::<Vec<_>>();
    let mut review = source_review::Review::default();
    review.by_source.insert("e0".into(), Role::Condition);
    review.by_source.insert("e3".into(), Role::Decision);
    assert_eq!(
        grounded_reported_scopes(&rows, &review, None),
        [vec![0, 1], vec![2, 3], vec![4, 6, 8], vec![9]]
    );
    rows[1]["text"] = serde_json::json!("说话人4: 工单处理也是分级来执行。");
    rows[3]["text"] = serde_json::json!("至于什么时候停运，我们已经决定下周停运。");
    rows[6]["text"] = serde_json::json!("说话人5: 我们就是采取线下方式。");
    assert_eq!(grounded_reported_scopes(&rows, &review, None), [vec![9]]);
}

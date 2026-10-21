//! Explicit clear intent is separate from blank replacement fields.
use super::{merge_settings, CompanionProductSettings};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum CredentialKind {
    VolcAppKey,
    VolcAccessKey,
    OpenaiAsrApiKey,
    DeepseekApiKey,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CredentialBlocks {
    #[serde(default)]
    pub volc_app_key: bool,
    #[serde(default)]
    pub volc_access_key: bool,
    #[serde(default)]
    pub openai_asr_api_key: bool,
    #[serde(default)]
    pub deepseek_api_key: bool,
}
impl CredentialBlocks {
    pub(super) fn any(&self) -> bool {
        self.volc_app_key || self.volc_access_key || self.openai_asr_api_key || self.deepseek_api_key
    }
    fn set(&mut self, kind: CredentialKind, blocked: bool) {
        match kind {
            CredentialKind::VolcAppKey => self.volc_app_key = blocked,
            CredentialKind::VolcAccessKey => self.volc_access_key = blocked,
            CredentialKind::OpenaiAsrApiKey => self.openai_asr_api_key = blocked,
            CredentialKind::DeepseekApiKey => self.deepseek_api_key = blocked,
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionProductSettingsPatch {
    #[serde(flatten)]
    pub settings: CompanionProductSettings,
    #[serde(default)]
    pub clear_credentials: Vec<CredentialKind>,
}

fn key(settings: &mut CompanionProductSettings, kind: CredentialKind) -> &mut String {
    match kind {
        CredentialKind::VolcAppKey => &mut settings.volc_app_key,
        CredentialKind::VolcAccessKey => &mut settings.volc_access_key,
        CredentialKind::OpenaiAsrApiKey => &mut settings.openai_asr_api_key,
        CredentialKind::DeepseekApiKey => &mut settings.deepseek_api_key,
    }
}

impl CompanionProductSettingsPatch {
    pub(super) fn validate(&self) -> Result<(), String> {
        let mut settings = self.settings.clone();
        for kind in [CredentialKind::VolcAppKey, CredentialKind::VolcAccessKey,
            CredentialKind::OpenaiAsrApiKey, CredentialKind::DeepseekApiKey] {
            let value = key(&mut settings, kind);
            if !value.is_empty() && value.trim().is_empty() {
                return Err("密钥不能只包含空白；留空保持原值，删除请使用清空操作。".into());
            }
        }
        for (index, kind) in self.clear_credentials.iter().enumerate() {
            if self.clear_credentials[..index].contains(kind) || !key(&mut settings, *kind).is_empty() {
                return Err("同一密钥不能同时替换和清空；请保留一种操作后重试。".into());
            }
        }
        Ok(())
    }

    pub(super) fn merge(self, current: CompanionProductSettings) -> CompanionProductSettings {
        let mut updated = merge_settings(current, self.settings.clone());
        let mut patch = self.settings;
        for kind in [CredentialKind::VolcAppKey, CredentialKind::VolcAccessKey,
            CredentialKind::OpenaiAsrApiKey, CredentialKind::DeepseekApiKey] {
            if !key(&mut patch, kind).is_empty() {
                updated.credential_blocks.set(kind, false);
            }
        }
        for kind in self.clear_credentials {
            key(&mut updated, kind).clear();
            updated.credential_blocks.set(kind, true);
        }
        updated
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn blank_retains_clear_blocks_fallback_and_replacement_reenables_only_its_key() {
        let mut base = CompanionProductSettings::default();
        base.deepseek_api_key = "existing-private".into(); base.volc_access_key = "other-private".into();
        let blank = CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![] };
        let unchanged = blank.merge(base.clone()); assert_eq!(unchanged.deepseek_api_key, base.deepseek_api_key);
        let cleared = CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![CredentialKind::DeepseekApiKey] }.merge(base);
        assert!(cleared.deepseek_api_key.is_empty() && cleared.credential_blocks.deepseek_api_key);
        assert_eq!(cleared.volc_access_key, "other-private");
        let public = cleared.public_with_environment("fixture", |name| matches!(name,
            "DEEPSEEK_API_KEY" | "COMPANION_TYPE_VOLC_ACCESS_KEY").then(|| "inherited-private".into()));
        assert!(!public.deepseek_api_key_set && public.volc_access_key_set);
        assert!(!serde_json::to_string(&public).unwrap().contains("private"));
        let mut replacement = CompanionProductSettings::default(); replacement.deepseek_api_key = "replacement-private".into();
        let replaced = CompanionProductSettingsPatch { settings: replacement, clear_credentials: vec![] }.merge(cleared);
        assert_eq!(replaced.deepseek_api_key, "replacement-private"); assert!(!replaced.credential_blocks.deepseek_api_key);
    }
    #[test]
    fn conflicting_duplicate_unknown_or_whitespace_intents_cannot_be_applied() {
        let mut settings = CompanionProductSettings::default(); settings.deepseek_api_key = "new-private".into();
        assert!(CompanionProductSettingsPatch { settings, clear_credentials: vec![CredentialKind::DeepseekApiKey] }.validate().is_err());
        assert!(CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![CredentialKind::DeepseekApiKey, CredentialKind::DeepseekApiKey] }.validate().is_err());
        let mut settings = CompanionProductSettings::default(); settings.deepseek_api_key = "  ".into();
        assert!(CompanionProductSettingsPatch { settings, clear_credentials: vec![] }.validate().is_err());
        let mut json = serde_json::to_value(CompanionProductSettings::default()).unwrap();
        json["clearCredentials"] = serde_json::json!(["unknownKey"]);
        assert!(serde_json::from_value::<CompanionProductSettingsPatch>(json).is_err());
    }
}

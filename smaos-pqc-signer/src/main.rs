//! Hybrid Ed25519 + ML-DSA-65 signer for AEIB receipts (prototype).
//!
//! Provides deterministic hybrid classical (Ed25519) and post-quantum (ML-DSA-65)
//! signatures. Keys are loaded from a persistent profile store instead of being
//! regenerated per execution loop:
//!   1. `--key-file <path>` (explicit override)
//!   2. `SMAOS_PQC_KEY_FILE` environment variable
//!   3. profile entry in `config/signer_profiles.json` (`--profile <name>`)
//!   4. default repo-local store `keys/signer_profiles/<profile>.json`
//! Persisted key stores are written with POSIX 0600 access control inside a
//! 0700 directory. `--ephemeral` is an explicit, single-run opt-out.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use ed25519_dalek::{
    Signature as EdSignature, Signer as EdSigner, SigningKey as EdSigningKey,
    Verifier as EdVerifier, VerifyingKey as EdVerifyingKey,
};
use ml_dsa::signature::{Signer as MlSigner, Verifier as MlVerifier};
use ml_dsa::{
    EncodedSignature, EncodedVerifyingKey, Generate, Keypair, MlDsa65,
    Signature as MlSignature, SigningKey as MlSigningKey, VerifyingKey as MlVerifyingKey,
};
use serde::{Deserialize, Serialize};
use serde_json::json;

pub struct HybridSig {
    pub ed_pk: Vec<u8>,
    pub ed_sig: Vec<u8>,
    pub ml_pk: Vec<u8>,
    pub ml_sig: Vec<u8>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct PersistedKeyStore {
    pub format: String,
    pub ed25519_secret_hex: String,
    pub mldsa65_seed_hex: String,
}

/// Environment variable overriding the resolved profile key file.
pub const KEY_FILE_ENV: &str = "SMAOS_PQC_KEY_FILE";
/// Profile used when `--profile` is not supplied.
pub const DEFAULT_PROFILE: &str = "default";
/// Repo-local profile configuration: profile name -> key file path.
pub const DEFAULT_PROFILE_CONFIG: &str = "config/signer_profiles.json";
/// Repo-local directory holding per-profile persistent key stores.
pub const DEFAULT_PROFILE_KEY_DIR: &str = "keys/signer_profiles";

/// Profile configuration mapping profile names to persistent key store paths.
#[derive(Serialize, Deserialize, Debug, Default)]
pub struct SignerProfileConfig {
    #[serde(default)]
    pub profiles: HashMap<String, String>,
}

/// Loads the profile configuration.
///
/// A missing file yields an empty configuration (default directory fallback).
/// A *malformed* configuration fails closed: the caller must not silently
/// sign with unintended key material.
pub fn load_profile_config(
    config_path: &Path,
) -> Result<SignerProfileConfig, Box<dyn std::error::Error>> {
    if !config_path.exists() {
        return Ok(SignerProfileConfig::default());
    }
    let content = std::fs::read_to_string(config_path)?;
    let config: SignerProfileConfig = serde_json::from_str(&content).map_err(|e| {
        format!("invalid profile configuration {}: {e}", config_path.display())
    })?;
    Ok(config)
}

/// Resolves the persistent key store for this run.
///
/// Precedence: explicit `--key-file` > `SMAOS_PQC_KEY_FILE` > profile entry in
/// the profile configuration > `default_key_dir/<profile>.json`.
/// Returns `Ok(None)` only when the caller explicitly requested ephemeral keys.
pub fn resolve_key_file(
    explicit_key_file: Option<&Path>,
    profile: &str,
    config_path: &Path,
    default_key_dir: &Path,
) -> Result<Option<PathBuf>, Box<dyn std::error::Error>> {
    if let Some(path) = explicit_key_file {
        return Ok(Some(path.to_path_buf()));
    }

    if let Ok(env_path) = std::env::var(KEY_FILE_ENV) {
        let trimmed = env_path.trim();
        if !trimmed.is_empty() {
            return Ok(Some(PathBuf::from(trimmed)));
        }
    }

    let config = load_profile_config(config_path)?;
    if let Some(mapped) = config.profiles.get(profile) {
        if !mapped.trim().is_empty() {
            return Ok(Some(PathBuf::from(mapped)));
        }
    }

    let mut fallback = default_key_dir.to_path_buf();
    fallback.push(format!("{profile}.json"));
    Ok(Some(fallback))
}

pub fn sign_hybrid_with_keys(
    msg: &[u8],
    ed: &EdSigningKey,
    ml: &MlSigningKey<MlDsa65>,
) -> HybridSig {
    let ed_sig = EdSigner::sign(ed, msg);
    let ml_sig = MlSigner::sign(ml, msg);
    let ml_vk = Keypair::verifying_key(ml);
    HybridSig {
        ed_pk: ed.verifying_key().as_bytes().to_vec(),
        ed_sig: ed_sig.to_bytes().to_vec(),
        ml_pk: ml_vk.encode().to_vec(),
        ml_sig: ml_sig.encode().to_vec(),
    }
}

pub fn sign_hybrid(msg: &[u8]) -> HybridSig {
    let ed = EdSigningKey::generate(&mut rand::rngs::OsRng);
    let ml = MlSigningKey::<MlDsa65>::generate();
    sign_hybrid_with_keys(msg, &ed, &ml)
}

/// Load keys from key file, or generate and persist to file with 0600 permissions.
pub fn load_or_generate_keypair(
    key_file: Option<&Path>,
) -> Result<(EdSigningKey, MlSigningKey<MlDsa65>), Box<dyn std::error::Error>> {
    if let Some(path) = key_file {
        if path.exists() {
            let content = std::fs::read_to_string(path)?;
            let store: PersistedKeyStore = serde_json::from_str(&content)?;
            let ed_bytes: [u8; 32] = hex::decode(&store.ed25519_secret_hex)?
                .as_slice()
                .try_into()
                .map_err(|_| "Invalid Ed25519 secret length (must be 32 bytes)")?;
            let ml_bytes: [u8; 32] = hex::decode(&store.mldsa65_seed_hex)?
                .as_slice()
                .try_into()
                .map_err(|_| "Invalid ML-DSA-65 seed length (must be 32 bytes)")?;

            let ed_key = EdSigningKey::from_bytes(&ed_bytes);
            let ml_key = MlSigningKey::<MlDsa65>::from_seed(&ml_bytes.into());
            return Ok((ed_key, ml_key));
        } else {
            // Create the containing key directory as 0700 (unix) before persisting
            if let Some(parent) = path.parent() {
                if !parent.as_os_str().is_empty() && !parent.exists() {
                    #[cfg(unix)]
                    {
                        use std::os::unix::fs::DirBuilderExt;
                        std::fs::DirBuilder::new().recursive(true).mode(0o700).create(parent)?;
                    }
                    #[cfg(not(unix))]
                    {
                        std::fs::create_dir_all(parent)?;
                    }
                }
            }

            // Generate and persist with 0600 permissions
            let ed = EdSigningKey::generate(&mut rand::rngs::OsRng);
            let ml = MlSigningKey::<MlDsa65>::generate();
            let store = PersistedKeyStore {
                format: "aeib-hybrid-v1".to_string(),
                ed25519_secret_hex: hex::encode(ed.to_bytes()),
                mldsa65_seed_hex: hex::encode(ml.to_seed()),
            };
            let serialized = serde_json::to_string_pretty(&store)?;

            #[cfg(unix)]
            {
                use std::io::Write;
                use std::os::unix::fs::OpenOptionsExt;
                let mut f = std::fs::OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o600)
                    .open(path)?;
                f.write_all(serialized.as_bytes())?;
            }
            #[cfg(not(unix))]
            {
                std::fs::write(path, serialized)?;
            }
            return Ok((ed, ml));
        }
    }

    // Ephemeral fallback
    let ed = EdSigningKey::generate(&mut rand::rngs::OsRng);
    let ml = MlSigningKey::<MlDsa65>::generate();
    Ok((ed, ml))
}

/// Both signatures must verify; failure of either rejects the receipt.
pub fn verify_hybrid(msg: &[u8], s: &HybridSig) -> bool {
    let ed_ok = (|| {
        let pk: [u8; 32] = s.ed_pk.as_slice().try_into().ok()?;
        let sig: [u8; 64] = s.ed_sig.as_slice().try_into().ok()?;
        let vk = EdVerifyingKey::from_bytes(&pk).ok()?;
        Some(vk.verify(msg, &EdSignature::from_bytes(&sig)).is_ok())
    })()
    .unwrap_or(false);

    let ml_ok = (|| {
        let pk = EncodedVerifyingKey::<MlDsa65>::try_from(s.ml_pk.as_slice()).ok()?;
        let vk = MlVerifyingKey::<MlDsa65>::decode(&pk);
        let enc = EncodedSignature::<MlDsa65>::try_from(s.ml_sig.as_slice()).ok()?;
        let sig = MlSignature::<MlDsa65>::decode(&enc)?;
        Some(vk.verify(msg, &sig).is_ok())
    })()
    .unwrap_or(false);

    ed_ok && ml_ok
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    // Cross-lingual verification mode: allows external runtimes (Python, Go) to verify via native Rust
    if args.len() >= 7 && args[1] == "--verify-hybrid" {
        let ed_pk_hex = &args[2];
        let ed_sig_hex = &args[3];
        let ml_pk_hex = &args[4];
        let ml_sig_hex = &args[5];
        let msg = &args[6];

        let ed_pk_bytes = match hex::decode(ed_pk_hex) {
            Ok(b) => b,
            Err(_) => {
                println!("{{\"verified\": false, \"reason\": \"invalid ed_pk_hex\"}}");
                std::process::exit(1);
            }
        };
        let ed_sig_bytes = match hex::decode(ed_sig_hex) {
            Ok(b) => b,
            Err(_) => {
                println!("{{\"verified\": false, \"reason\": \"invalid ed_sig_hex\"}}");
                std::process::exit(1);
            }
        };
        let ml_pk_bytes = match hex::decode(ml_pk_hex) {
            Ok(b) => b,
            Err(_) => {
                println!("{{\"verified\": false, \"reason\": \"invalid ml_pk_hex\"}}");
                std::process::exit(1);
            }
        };
        let ml_sig_bytes = match hex::decode(ml_sig_hex) {
            Ok(b) => b,
            Err(_) => {
                println!("{{\"verified\": false, \"reason\": \"invalid ml_sig_hex\"}}");
                std::process::exit(1);
            }
        };

        let hybrid_sig = HybridSig {
            ed_pk: ed_pk_bytes,
            ed_sig: ed_sig_bytes,
            ml_pk: ml_pk_bytes,
            ml_sig: ml_sig_bytes,
        };

        let verified = verify_hybrid(msg.as_bytes(), &hybrid_sig);
        println!("{{\"verified\": {verified}}}");
        if verified {
            std::process::exit(0);
        } else {
            std::process::exit(1);
        }
    }

    if args.len() >= 5 && args[1] == "--verify-ed25519" {
        let pk_hex = &args[2];
        let sig_hex = &args[3];
        let msg = &args[4];
        let pk_bytes = match hex::decode(pk_hex) {
            Ok(b) => b,
            Err(_) => {
                eprintln!("Invalid public key hex");
                std::process::exit(1);
            }
        };
        let sig_bytes = match hex::decode(sig_hex) {
            Ok(b) => b,
            Err(_) => {
                eprintln!("Invalid signature hex");
                std::process::exit(1);
            }
        };
        let pk_arr: [u8; 32] = match pk_bytes.as_slice().try_into() {
            Ok(a) => a,
            Err(_) => {
                eprintln!("Public key must be 32 bytes");
                std::process::exit(1);
            }
        };
        let sig_arr: [u8; 64] = match sig_bytes.as_slice().try_into() {
            Ok(a) => a,
            Err(_) => {
                eprintln!("Signature must be 64 bytes");
                std::process::exit(1);
            }
        };
        let vk = match EdVerifyingKey::from_bytes(&pk_arr) {
            Ok(k) => k,
            Err(_) => {
                eprintln!("Invalid Ed25519 verifying key");
                std::process::exit(1);
            }
        };
        let sig = EdSignature::from_bytes(&sig_arr);
        match vk.verify_strict(msg.as_bytes(), &sig) {
            Ok(_) => {
                println!("{{\"verified\": true}}");
                std::process::exit(0);
            }
            Err(e) => {
                eprintln!("Verification failed: {e}");
                println!("{{\"verified\": false}}");
                std::process::exit(1);
            }
        }
    }

    let mut key_file_path: Option<String> = None;
    let mut profile = DEFAULT_PROFILE.to_string();
    let mut ephemeral = false;
    let mut message: String = "{\"aeib.caid\":\"uuid-1234-test\"}".to_string();

    let mut i = 1;
    while i < args.len() {
        if args[i] == "--key-file" && i + 1 < args.len() {
            key_file_path = Some(args[i + 1].clone());
            i += 2;
        } else if args[i] == "--profile" && i + 1 < args.len() {
            profile = args[i + 1].clone();
            i += 2;
        } else if args[i] == "--ephemeral" {
            ephemeral = true;
            i += 1;
        } else if args[i] == "--message" && i + 1 < args.len() {
            message = args[i + 1].clone();
            i += 2;
        } else if !args[i].starts_with("--") {
            message = args[i].clone();
            i += 1;
        } else {
            i += 1;
        }
    }

    if ephemeral && key_file_path.is_some() {
        eprintln!("Error: --ephemeral conflicts with --key-file (persistent store requested twice).");
        std::process::exit(2);
    }

    let resolved_key_file: Option<PathBuf> = if ephemeral {
        eprintln!("[smaos-pqc-signer] key source: ephemeral (explicit --ephemeral opt-out)");
        None
    } else {
        let resolved = resolve_key_file(
            key_file_path.as_deref().map(Path::new),
            &profile,
            Path::new(DEFAULT_PROFILE_CONFIG),
            Path::new(DEFAULT_PROFILE_KEY_DIR),
        );
        match resolved {
            Ok(path) => {
                if let Some(p) = &path {
                    eprintln!("[smaos-pqc-signer] key source: profile '{profile}' -> {}", p.display());
                }
                path
            }
            Err(e) => {
                eprintln!("Error resolving key store: {e}");
                std::process::exit(1);
            }
        }
    };

    let (ed, ml) = match load_or_generate_keypair(resolved_key_file.as_deref()) {
        Ok(keys) => keys,
        Err(e) => {
            eprintln!("Error loading/generating keys: {}", e);
            std::process::exit(1);
        }
    };

    let s = sign_hybrid_with_keys(message.as_bytes(), &ed, &ml);
    let verified = verify_hybrid(message.as_bytes(), &s);
    let receipt = json!({
        "payload": message,
        "signatures": {
            "ed25519": {"public_key": hex::encode(&s.ed_pk), "signature": hex::encode(&s.ed_sig)},
            "ml-dsa-65": {"public_key": hex::encode(&s.ml_pk), "signature": hex::encode(&s.ml_sig)}
        },
        "self_verified": verified
    });
    println!("{}", serde_json::to_string_pretty(&receipt).unwrap());
    if !verified {
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;
    const MSG: &[u8] = b"{\"aeib.caid\":\"abc\"}";

    /// Serializes tests that touch the process-global `SMAOS_PQC_KEY_FILE` variable.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn unique_temp_dir(tag: &str) -> PathBuf {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("smaos_pqc_signer_{tag}_{unique}"));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn explicit_key_file_wins_over_profile_resolution() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        std::env::remove_var(KEY_FILE_ENV);

        let dir = unique_temp_dir("explicit");
        let mapped = dir.join("mapped.json");
        let config = dir.join("signer_profiles.json");
        let config_json =
            serde_json::json!({"profiles": {"default": mapped.display().to_string()}}).to_string();
        std::fs::write(&config, config_json).unwrap();

        let explicit = dir.join("explicit.json");
        let resolved = resolve_key_file(
            Some(&explicit),
            DEFAULT_PROFILE,
            &config,
            &dir.join("keys"),
        )
        .unwrap()
        .unwrap();
        assert_eq!(resolved, explicit);
    }

    #[test]
    fn profile_entry_in_config_is_used() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        std::env::remove_var(KEY_FILE_ENV);

        let dir = unique_temp_dir("profile_entry");
        let mapped = dir.join("ci.json");
        let config = dir.join("signer_profiles.json");
        let config_json =
            serde_json::json!({"profiles": {"ci": mapped.display().to_string()}}).to_string();
        std::fs::write(&config, config_json).unwrap();

        let resolved = resolve_key_file(None, "ci", &config, &dir.join("keys")).unwrap().unwrap();
        assert_eq!(resolved, mapped);
    }

    #[test]
    fn missing_config_falls_back_to_default_profile_dir() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        std::env::remove_var(KEY_FILE_ENV);

        let dir = unique_temp_dir("fallback");
        let key_dir = dir.join("keys").join("signer_profiles");
        let resolved = resolve_key_file(
            None,
            DEFAULT_PROFILE,
            &dir.join("missing_profiles.json"),
            &key_dir,
        )
        .unwrap()
        .unwrap();
        assert_eq!(resolved, key_dir.join(format!("{DEFAULT_PROFILE}.json")));
    }

    #[test]
    fn env_var_overrides_profile_config() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());

        let dir = unique_temp_dir("env");
        let mapped = dir.join("mapped.json");
        let config = dir.join("signer_profiles.json");
        let config_json =
            serde_json::json!({"profiles": {"default": mapped.display().to_string()}}).to_string();
        std::fs::write(&config, config_json).unwrap();

        let env_path = dir.join("env_override.json");
        std::env::set_var(KEY_FILE_ENV, &env_path);
        let resolved = resolve_key_file(None, DEFAULT_PROFILE, &config, &dir.join("keys"));
        std::env::remove_var(KEY_FILE_ENV);

        assert_eq!(resolved.unwrap().unwrap(), env_path);
    }

    #[test]
    fn malformed_profile_config_fails_closed() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        std::env::remove_var(KEY_FILE_ENV);

        let dir = unique_temp_dir("malformed");
        let config = dir.join("signer_profiles.json");
        std::fs::write(&config, "{\"profiles\": not_json").unwrap();

        // Refuses to resolve a key store rather than silently generating new keys.
        assert!(resolve_key_file(None, DEFAULT_PROFILE, &config, &dir.join("keys")).is_err());
    }

    #[test]
    fn shipped_profile_config_maps_default_profile() {
        let repo_root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let config = repo_root.join(DEFAULT_PROFILE_CONFIG);
        assert!(config.is_file(), "expected {} to exist", config.display());

        let parsed = load_profile_config(&config).expect("shipped profile config must parse");
        assert!(parsed.profiles.contains_key(DEFAULT_PROFILE));
    }

    #[test]
    fn profile_store_persists_keys_across_loads_with_strict_permissions() {
        let dir = unique_temp_dir("persist");
        let key_path = resolve_key_file(
            None,
            DEFAULT_PROFILE,
            &dir.join("missing_profiles.json"),
            &dir.join("signer_profiles"),
        )
        .unwrap()
        .unwrap();

        let (ed1, ml1) = load_or_generate_keypair(Some(&key_path)).unwrap();
        let (ed2, ml2) = load_or_generate_keypair(Some(&key_path)).unwrap();

        assert_eq!(ed1.to_bytes(), ed2.to_bytes());
        assert_eq!(ml1.to_seed(), ml2.to_seed());

        let sig = sign_hybrid_with_keys(MSG, &ed2, &ml2);
        assert!(verify_hybrid(MSG, &sig));

        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            let file_mode = std::fs::metadata(&key_path).unwrap().mode() & 0o777;
            assert_eq!(file_mode, 0o600, "key store must have 0600 permissions");
            let dir_mode = std::fs::metadata(key_path.parent().unwrap())
                .unwrap()
                .mode()
                & 0o777;
            assert_eq!(dir_mode, 0o700, "key directory must have 0700 permissions");
        }

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn roundtrip_verifies() {
        assert!(verify_hybrid(MSG, &sign_hybrid(MSG)));
    }

    #[test]
    fn tampered_message_fails() {
        let s = sign_hybrid(MSG);
        assert!(!verify_hybrid(b"{\"aeib.caid\":\"abd\"}", &s));
    }

    #[test]
    fn tampered_ml_sig_fails_even_if_ed_valid() {
        let mut s = sign_hybrid(MSG);
        s.ml_sig[10] ^= 0x01;
        assert!(!verify_hybrid(MSG, &s));
    }

    #[test]
    fn tampered_ed_sig_fails_even_if_ml_valid() {
        let mut s = sign_hybrid(MSG);
        s.ed_sig[0] ^= 0x01;
        assert!(!verify_hybrid(MSG, &s));
    }

    #[test]
    fn truncated_key_fails_closed() {
        let mut s = sign_hybrid(MSG);
        s.ml_pk.truncate(10);
        assert!(!verify_hybrid(MSG, &s));
    }

    #[test]
    fn key_persistence_roundtrip_and_permissions() {
        let unique_name = format!(
            "test_hybrid_key_{}.json",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let key_path = std::env::temp_dir().join(unique_name);

        // 1. First run: generates and saves with 0600
        let (ed1, ml1) = load_or_generate_keypair(Some(&key_path)).unwrap();
        assert!(key_path.exists());

        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            let meta = std::fs::metadata(&key_path).unwrap();
            let mode = meta.mode() & 0o777;
            assert_eq!(mode, 0o600, "Key file must have 0600 permissions");
        }

        let sig1 = sign_hybrid_with_keys(MSG, &ed1, &ml1);
        assert!(verify_hybrid(MSG, &sig1));

        // 2. Second run: loads existing keys
        let (ed2, ml2) = load_or_generate_keypair(Some(&key_path)).unwrap();
        assert_eq!(ed1.to_bytes(), ed2.to_bytes());
        assert_eq!(ml1.to_seed(), ml2.to_seed());

        let sig2 = sign_hybrid_with_keys(MSG, &ed2, &ml2);
        assert_eq!(sig1.ed_pk, sig2.ed_pk);
        assert_eq!(sig1.ml_pk, sig2.ml_pk);
        assert!(verify_hybrid(MSG, &sig2));

        // Clean up
        let _ = std::fs::remove_file(key_path);
    }
}

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.fernet import Fernet

from config.location import get_local_anchor_dir
from utils.logger import Logger


_BUG_REPORTS_ROOT = "bug_reports"
_CREDENTIALS_ROOTS = {"accounts", "ece"}
_PROFILES_ROOT = "playwright_profiles"
_SETTINGS_KEY_FILENAME = "settings.key"
_VOLATILE_PROFILE_DIR_NAMES = {
    name.casefold()
    for name in (
        "BrowserMetrics",
        "Cache",
        "CacheStorage",
        "Code Cache",
        "component_crx_cache",
        "Crashpad",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "GPUCache",
        "GrShaderCache",
        "OnDeviceHeadSuggestModel",
        "OptimizationHints",
        "OptimizationGuidePredictionModels",
        "ShaderCache",
        "blob_storage",
    )
}
_VOLATILE_PROFILE_FILE_NAMES = {
    name.casefold()
    for name in (
        "DevToolsActivePort",
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
    )
}


@dataclass(frozen=True)
class ConfigBackupOptions:
    settings_state: bool = True
    profiles: bool = True
    credentials: bool = True

    def any_enabled(self) -> bool:
        return bool(self.settings_state or self.profiles or self.credentials)

    def all_enabled(self) -> bool:
        return bool(self.settings_state and self.profiles and self.credentials)

    def labels(self) -> list[str]:
        labels: list[str] = []
        if self.settings_state:
            labels.append("Settings & State")
        if self.profiles:
            labels.append("Profiles")
        if self.credentials:
            labels.append("Credentials")
        return labels


def _normalize_options(options: ConfigBackupOptions | None) -> ConfigBackupOptions:
    if options is None:
        return ConfigBackupOptions()
    return ConfigBackupOptions(
        settings_state=bool(options.settings_state),
        profiles=bool(options.profiles),
        credentials=bool(options.credentials),
    )


def _format_options(options: ConfigBackupOptions) -> str:
    labels = options.labels()
    return ", ".join(labels) if labels else "None"


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except Exception:
        try:
            return path.expanduser().absolute()
        except Exception:
            return path


def _is_subpath(child: Path, parent: Path) -> bool:
    try:
        _safe_resolve(child).relative_to(_safe_resolve(parent))
        return True
    except Exception:
        return False


def _looks_like_config_dir(path: Path) -> bool:
    return (
        (path / "settings.json.enc").is_file()
        or (path / "settings.key").is_file()
        or (path / "playwright_profiles").is_dir()
        or (path / "accounts").is_dir()
        or (path / "ece").is_dir()
    )


def _ensure_safe_target_config_dir(config_dir: Path) -> tuple[bool, str]:
    target = _safe_resolve(config_dir)

    # Never allow filesystem roots
    if target == Path(target.anchor):
        return False, "Refusing to use a filesystem root as a config directory."

    # Never allow wiping/moving the app directory or any directory containing it
    anchor = _safe_resolve(get_local_anchor_dir())
    if target == anchor or _is_subpath(anchor, target):
        return (
            False,
            "Refusing to use the application folder (or a parent of it) as the config directory.",
        )

    if target.exists():
        if not target.is_dir():
            return False, "Config directory path exists but is not a directory."

        try:
            has_any = any(target.iterdir())
        except Exception:
            has_any = True

        if has_any and not _looks_like_config_dir(target):
            return (
                False,
                "Config directory is not empty and does not look like an IntenseRP Next config directory.",
            )

    return True, ""


def _normalize_zip_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if p.suffix.lower() != ".zip":
        p = p.with_suffix(".zip")
    return _safe_resolve(p)


def _zip_path_parts(arcname: str | Path) -> tuple[str, ...]:
    try:
        return tuple(PurePosixPath(str(arcname).replace("\\", "/")).parts)
    except Exception:
        return tuple()


def _profile_member_parts(arcname: str | Path) -> tuple[str, ...]:
    parts = _zip_path_parts(arcname)
    for index, part in enumerate(parts):
        if part.casefold() == _PROFILES_ROOT.casefold():
            return parts[index + 1 :]
    return tuple()


def _should_skip_volatile_profile_member(arcname: str | Path) -> bool:
    profile_parts = _profile_member_parts(arcname)
    if not profile_parts:
        return False

    lowered_parts = tuple(part.casefold() for part in profile_parts)
    if any(part in _VOLATILE_PROFILE_DIR_NAMES for part in lowered_parts):
        return True

    return lowered_parts[-1] in _VOLATILE_PROFILE_FILE_NAMES


def _should_include_backup_member(arcname: str | Path, options: ConfigBackupOptions) -> bool:
    parts = _zip_path_parts(arcname)
    if not parts:
        return False

    root = parts[0]
    if root == _BUG_REPORTS_ROOT:
        return False

    if root == _SETTINGS_KEY_FILENAME:
        # Credentials are encrypted with the same key. Keep the key in
        # credentials-only backups so selective import can re-encrypt safely
        return bool(options.settings_state or options.credentials)

    if root == _PROFILES_ROOT:
        return bool(options.profiles) and not _should_skip_volatile_profile_member(arcname)

    if root in _CREDENTIALS_ROOTS:
        return bool(options.credentials)

    return bool(options.settings_state)


def create_config_backup_zip(
    config_dir: str | Path,
    output_zip: str | Path,
    options: ConfigBackupOptions | None = None,
) -> tuple[bool, str]:
    options = _normalize_options(options)
    if not options.any_enabled():
        return False, "Select at least one backup category."

    src_dir = _safe_resolve(Path(config_dir))
    zip_path = _normalize_zip_path(output_zip)

    if not src_dir.exists() or not src_dir.is_dir():
        return False, f"Config directory does not exist: {src_dir}"

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    skipped: list[str] = []
    added_count = 0
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in src_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    if _safe_resolve(file_path) == zip_path:
                        continue
                except Exception:
                    pass

                try:
                    arcname = file_path.relative_to(src_dir).as_posix()
                except Exception:
                    arcname = file_path.name

                if not _should_include_backup_member(arcname, options):
                    continue

                try:
                    zf.write(file_path, arcname=arcname)
                    added_count += 1
                except Exception as e:
                    skipped.append(f"{arcname} ({e})")
    except Exception as e:
        return False, f"Failed to write zip: {e}"

    if added_count <= 0:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False, f"No files matched the selected categories: {_format_options(options)}"

    if skipped:
        preview = "\n".join(skipped[:10])
        suffix = "\n\nSome files could not be added. Stop the app (or stop services) and try again for a complete backup."
        if len(skipped) > 10:
            suffix = f"\n\n...and {len(skipped) - 10} more." + suffix
        Logger.warning(f"Backup zip created with skipped files ({len(skipped)}).")
        return (
            True,
            f"Backup created: {zip_path}\n\nIncluded: {_format_options(options)}\n\n"
            f"Skipped files:\n{preview}{suffix}",
        )

    return True, f"Backup created: {zip_path}\n\nIncluded: {_format_options(options)}"


def _validate_decryptable_settings(root: Path) -> tuple[bool, str]:
    key_file = root / "settings.key"
    settings_file = root / "settings.json.enc"

    if not key_file.is_file():
        return False, "Backup is missing settings.key."
    if not settings_file.is_file():
        return False, "Backup is missing settings.json.enc."

    try:
        key = key_file.read_bytes()
        cipher = Fernet(key)
        decrypted = cipher.decrypt(settings_file.read_bytes())
        json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        return False, f"Backup settings could not be decrypted/parsed: {e}"

    return True, ""


def _read_key_file(root: Path) -> tuple[bool, str, bytes | None]:
    key_file = root / _SETTINGS_KEY_FILENAME
    if not key_file.is_file():
        return False, "Backup is missing settings.key."

    try:
        return True, "", key_file.read_bytes()
    except Exception as e:
        return False, f"Backup settings.key could not be read: {e}", None


def _load_or_create_target_key(target_dir: Path) -> tuple[bool, str, bytes | None]:
    key_file = target_dir / _SETTINGS_KEY_FILENAME
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create target config directory: {e}", None

    if key_file.exists():
        try:
            return True, "", key_file.read_bytes()
        except Exception as e:
            return False, f"Failed to read target settings.key: {e}", None

    key = Fernet.generate_key()
    try:
        key_file.write_bytes(key)
    except Exception as e:
        return False, f"Failed to write target settings.key: {e}", None
    return True, "", key


def _read_encrypted_json(path: Path, key: bytes) -> tuple[bool, str, Any]:
    try:
        decrypted = Fernet(key).decrypt(path.read_bytes())
        return True, "", json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        return False, f"Failed to decrypt/parse {path.name}: {e}", None


def _write_encrypted_json(path: Path, key: bytes, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    path.write_bytes(Fernet(key).encrypt(raw))


def _path_contains_encrypted_json(path: Path) -> bool:
    if path.is_file():
        return path.name.endswith(".json.enc")
    if not path.is_dir():
        return False

    try:
        for child in path.rglob("*"):
            if child.is_file() and child.name.endswith(".json.enc"):
                return True
    except Exception:
        return False
    return False


def _copy_path_with_reencrypted_json(
    src: Path,
    dst: Path,
    source_key: bytes | None,
    target_key: bytes | None,
) -> None:
    if src.is_file():
        if src.name.endswith(".json.enc"):
            if source_key is None or target_key is None:
                raise ValueError(f"Cannot import encrypted file without settings.key: {src.name}")
            ok, reason, payload = _read_encrypted_json(src, source_key)
            if not ok:
                raise ValueError(reason)
            _write_encrypted_json(dst, target_key, payload)
            return

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return

    if not src.is_dir():
        return

    dst.mkdir(parents=True, exist_ok=True)
    for child in src.rglob("*"):
        try:
            rel = child.relative_to(src)
        except Exception:
            rel = Path(child.name)
        out_path = dst / rel
        if child.is_dir():
            out_path.mkdir(parents=True, exist_ok=True)
            continue
        if child.name.endswith(".json.enc"):
            if source_key is None or target_key is None:
                raise ValueError(f"Cannot import encrypted file without settings.key: {child.name}")
            ok, reason, payload = _read_encrypted_json(child, source_key)
            if not ok:
                raise ValueError(reason)
            _write_encrypted_json(out_path, target_key, payload)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(child, out_path)


def _is_unsafe_zip_member(name: str) -> bool:
    if not name or name in (".", ".."):
        return True
    if "\\" in name:
        return True

    posix = PurePosixPath(name)
    if posix.is_absolute():
        return True

    if any(part in ("..", "") for part in posix.parts):
        return True

    # Block Windows drive prefixes like "C:/..."
    if posix.parts and ":" in posix.parts[0]:
        return True

    return False


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> tuple[bool, str]:
    skipped_volatile_members = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if _is_unsafe_zip_member(name):
                    return False, f"Zip contains an unsafe path: {name}"
                if _should_skip_volatile_profile_member(name):
                    skipped_volatile_members += 1
                    continue
                if name.endswith("/"):
                    # directory entry
                    continue

                rel = PurePosixPath(name)
                out_path = dest_dir.joinpath(*rel.parts)
                out_path.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except Exception as e:
        return False, f"Failed to read/extract zip: {e}"

    if skipped_volatile_members:
        Logger.info(
            "Skipped "
            f"{skipped_volatile_members} volatile browser profile cache item(s) while extracting backup."
        )

    return True, ""


def _find_backup_root(extract_dir: Path) -> Path | None:
    if _looks_like_config_dir(extract_dir):
        return extract_dir

    try:
        entries = list(extract_dir.iterdir())
    except Exception:
        return None

    dirs = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]

    if len(dirs) == 1 and not files:
        candidate = dirs[0]
        if _looks_like_config_dir(candidate):
            return candidate

    return None


def _make_unique_import_dirs(parent: Path, ts: str, *prefixes: str) -> tuple[Path, ...]:
    paths = tuple(parent / f"{prefix}_{ts}" for prefix in prefixes)
    for i in range(2, 1000):
        if not any(path.exists() for path in paths):
            return paths
        paths = tuple(parent / f"{prefix}_{ts}_{i}" for prefix in prefixes)
    return paths


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink(missing_ok=True)


def _copy_path_raw(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _replace_entire_config_dir(root: Path, target_dir: Path) -> tuple[bool, str]:
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # apparently our long paths are close to MAX_PATH on Windows
    staging_dir, old_dir = _make_unique_import_dirs(
        parent,
        ts,
        "__i",
        "__o",
    )

    try:
        shutil.copytree(root, staging_dir)
    except Exception as e:
        try:
            shutil.rmtree(staging_dir)
        except Exception:
            pass
        return False, f"Failed to stage imported config directory: {e}"

    try:
        if target_dir.exists():
            if old_dir.exists():
                shutil.rmtree(old_dir)
            target_dir.rename(old_dir)
        staging_dir.rename(target_dir)
    except Exception as e:
        # Roll back best-effort: restore original and remove staging
        try:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
        except Exception:
            pass
        try:
            if old_dir.exists() and not target_dir.exists():
                old_dir.rename(target_dir)
        except Exception:
            pass
        return False, f"Failed to replace config directory contents: {e}"

    # Cleanup old config dir after successful swap
    try:
        if old_dir.exists():
            shutil.rmtree(old_dir)
    except Exception as e:
        Logger.warning(f"Imported settings, but failed to delete old config dir '{old_dir}': {e}")

    return True, f"Import complete. Settings restored into: {target_dir}"


def _iter_settings_state_entries(root: Path) -> list[Path]:
    try:
        entries = [p for p in root.iterdir() if p.exists()]
    except Exception:
        return []

    result: list[Path] = []
    for entry in entries:
        name = entry.name
        if name == _BUG_REPORTS_ROOT:
            continue
        if name == _PROFILES_ROOT:
            continue
        if name == _SETTINGS_KEY_FILENAME:
            continue
        if name in _CREDENTIALS_ROOTS:
            continue
        result.append(entry)
    return result


def _missing_selected_backup_categories(root: Path, options: ConfigBackupOptions) -> list[str]:
    missing: list[str] = []

    if options.settings_state and not _iter_settings_state_entries(root):
        missing.append("Settings & State")

    if options.profiles and not (root / _PROFILES_ROOT).exists():
        missing.append("Profiles")

    if options.credentials and not any((root / name).exists() for name in _CREDENTIALS_ROOTS):
        missing.append("Credentials")

    return missing


def _restore_moved_paths(moved_paths: list[tuple[Path, Path]]) -> None:
    for target_path, rollback_path in reversed(moved_paths):
        try:
            if target_path.exists():
                _remove_path(target_path)
            if rollback_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(rollback_path), str(target_path))
        except Exception as e:
            Logger.warning(f"Selective import rollback failed for '{target_path}': {e}")


def _import_selected_config_data(
    root: Path,
    target_dir: Path,
    options: ConfigBackupOptions,
) -> tuple[bool, str]:
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # even shorter names (wtf was I thinking)
    (rollback_dir,) = _make_unique_import_dirs(
        parent,
        ts,
        "__is",
    )
    rollback_dir.mkdir(parents=True, exist_ok=True)

    source_key: bytes | None = None
    target_key: bytes | None = None
    moved_paths: list[tuple[Path, Path]] = []
    used_labels: list[str] = []
    missing_labels: list[str] = []

    def get_source_key() -> bytes:
        nonlocal source_key
        if source_key is not None:
            return source_key
        ok, reason, key = _read_key_file(root)
        if not ok or key is None:
            raise ValueError(reason)
        source_key = key
        return source_key

    def get_target_key() -> bytes:
        nonlocal target_key
        if target_key is not None:
            return target_key
        ok, reason, key = _load_or_create_target_key(target_dir)
        if not ok or key is None:
            raise ValueError(reason)
        target_key = key
        return target_key

    def move_existing_to_rollback(rel_path: Path) -> None:
        target_path = target_dir / rel_path
        if not target_path.exists():
            return

        rollback_path = rollback_dir / rel_path
        if rollback_path.exists():
            _remove_path(rollback_path)
        rollback_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target_path), str(rollback_path))
        moved_paths.append((target_path, rollback_path))

    def replace_raw(src: Path, rel_path: Path) -> None:
        move_existing_to_rollback(rel_path)
        _copy_path_raw(src, target_dir / rel_path)

    def replace_reencrypting(src: Path, rel_path: Path) -> None:
        source_key_for_path: bytes | None = None
        target_key_for_path: bytes | None = None
        if _path_contains_encrypted_json(src):
            source_key_for_path = get_source_key()
            target_key_for_path = get_target_key()
        move_existing_to_rollback(rel_path)
        _copy_path_with_reencrypted_json(
            src,
            target_dir / rel_path,
            source_key_for_path,
            target_key_for_path,
        )

    try:
        if options.settings_state:
            settings_entries = _iter_settings_state_entries(root)
            if settings_entries:
                for entry in settings_entries:
                    replace_reencrypting(entry, Path(entry.name))
                used_labels.append("Settings & State")
            else:
                missing_labels.append("Settings & State")

        if options.profiles:
            profiles_root = root / _PROFILES_ROOT
            if profiles_root.exists():
                replace_raw(profiles_root, Path(_PROFILES_ROOT))
                used_labels.append("Profiles")
            else:
                missing_labels.append("Profiles")

        if options.credentials:
            credentials_found = False
            for name in sorted(_CREDENTIALS_ROOTS):
                credentials_root = root / name
                if not credentials_root.exists():
                    continue
                replace_reencrypting(credentials_root, Path(name))
                credentials_found = True
            if credentials_found:
                used_labels.append("Credentials")
            else:
                missing_labels.append("Credentials")
    except Exception as e:
        _restore_moved_paths(moved_paths)
        try:
            shutil.rmtree(rollback_dir)
        except Exception:
            pass
        return False, f"Failed to import selected backup data: {e}"

    if not used_labels:
        try:
            shutil.rmtree(rollback_dir)
        except Exception:
            pass
        return False, "No selected data was found in the backup."

    try:
        shutil.rmtree(rollback_dir)
    except Exception as e:
        Logger.warning(f"Selective import completed, but failed to delete rollback dir '{rollback_dir}': {e}")

    message = f"Import complete. Used: {', '.join(used_labels)}.\n\nActive config directory: {target_dir}"
    if missing_labels:
        message += f"\n\nNot found in backup: {', '.join(missing_labels)}"
    return True, message


def import_config_backup_zip(
    zip_file: str | Path,
    target_config_dir: str | Path,
    options: ConfigBackupOptions | None = None,
) -> tuple[bool, str]:
    options = _normalize_options(options)
    if not options.any_enabled():
        return False, "Select at least one import category."

    zip_path = _safe_resolve(Path(zip_file))
    target_dir = _safe_resolve(Path(target_config_dir))

    if not zip_path.is_file():
        return False, f"Zip file does not exist: {zip_path}"

    ok, reason = _ensure_safe_target_config_dir(target_dir)
    if not ok:
        return False, reason

    with tempfile.TemporaryDirectory(prefix="irpnext-import-") as tmp:
        extract_dir = Path(tmp)

        ok, reason = _safe_extract_zip(zip_path, extract_dir)
        if not ok:
            return False, reason

        root = _find_backup_root(extract_dir)
        if root is None:
            return False, "Zip does not look like an IntenseRP Next config backup (missing settings/key)."

        if options.all_enabled():
            ok, reason = _validate_decryptable_settings(root)
            if not ok:
                return False, reason
            missing_categories = _missing_selected_backup_categories(root, options)
            if not missing_categories:
                return _replace_entire_config_dir(root, target_dir)

            Logger.info(
                "Full config import requested, but the backup is missing selected "
                f"data ({', '.join(missing_categories)}). Using selective import."
            )

        return _import_selected_config_data(root, target_dir, options)

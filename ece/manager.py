from __future__ import annotations

import hashlib
import random
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config.validators import validate_email
from drivers.providers import DriverProvider
from utils.logger import Logger

from .models import CredentialPair
from .storage import EncryptedJsonFile, load_or_create_settings_key


def _provider_key(provider: DriverProvider | str) -> str:
    if isinstance(provider, DriverProvider):
        return provider.key
    return str(provider or "").strip().lower().replace(" ", "_")


def _provider_requires_password(provider: DriverProvider | str) -> bool:
    normalized = provider if isinstance(provider, DriverProvider) else DriverProvider.from_setting(str(provider or ""))
    return normalized is not DriverProvider.PERPLEXITY


def _provider_accepts_username_identity(provider: DriverProvider | str) -> bool:
    normalized = provider if isinstance(provider, DriverProvider) else DriverProvider.from_setting(str(provider or ""))
    return normalized is DriverProvider.HUGGINGCHAT


def _validate_provider_identity(provider: DriverProvider | str, identity: str) -> None:
    normalized = str(identity or "").strip()
    if _provider_accepts_username_identity(provider):
        if not normalized:
            raise ValueError("username/email is empty.")
        if any(ch.isspace() for ch in normalized):
            raise ValueError("username/email cannot contain whitespace.")
        if "@" in normalized:
            validate_email(normalized)
        return
    validate_email(normalized)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_email(email: str) -> str:
    normalized = _normalize_email(email)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


class EceManager:
    """
    Stores provider accounts + usage metadata in encrypted files under the config directory.
    """

    CREDENTIALS_VERSION = 1
    USAGE_VERSION = 1
    _usage_write_lock = threading.RLock()

    def __init__(self, config_dir: str | Path):
        self.config_dir = Path(config_dir).resolve()
        key = load_or_create_settings_key(self.config_dir)

        storage_dir = self._resolve_storage_dir()
        self._profile_namespace = self._resolve_profile_namespace()

        self._credentials_file = EncryptedJsonFile(storage_dir / "credentials.json.enc", key)
        self._usage_file = EncryptedJsonFile(storage_dir / "usage.json.enc", key)

    def _resolve_storage_dir(self) -> Path:
        """
        Prefer the new accounts/ storage directory.

        If an older config uses ece/, attempt a best-effort rename/copy.
        Falls back to the legacy directory when migration fails.
        """
        legacy_dir = (self.config_dir / "ece").resolve()
        accounts_dir = (self.config_dir / "accounts").resolve()

        legacy_creds = legacy_dir / "credentials.json.enc"
        legacy_usage = legacy_dir / "usage.json.enc"
        accounts_creds = accounts_dir / "credentials.json.enc"
        accounts_usage = accounts_dir / "usage.json.enc"

        def _has_data_file(path: Path) -> bool:
            try:
                return path.exists() and path.is_file() and path.stat().st_size > 0
            except Exception:
                return path.exists()

        legacy_has_data = _has_data_file(legacy_creds) or _has_data_file(legacy_usage)
        accounts_has_data = _has_data_file(accounts_creds) or _has_data_file(accounts_usage)

        if legacy_has_data and (not accounts_has_data):
            # Prefer a straight rename when possible
            if legacy_dir.exists() and (not accounts_dir.exists()):
                try:
                    legacy_dir.rename(accounts_dir)
                    return accounts_dir
                except Exception:
                    pass

            # Fallback: copy only the encrypted data files (best-effort)
            try:
                accounts_dir.mkdir(parents=True, exist_ok=True)
                for name in ("credentials.json.enc", "usage.json.enc"):
                    src = legacy_dir / name
                    dst = accounts_dir / name
                    if _has_data_file(src) and (not _has_data_file(dst)):
                        dst.write_bytes(src.read_bytes())
            except Exception:
                return legacy_dir

            accounts_has_data = _has_data_file(accounts_creds) or _has_data_file(accounts_usage)
            return accounts_dir if accounts_has_data else legacy_dir

        return accounts_dir

    def _resolve_profile_namespace(self) -> str:
        """
        Prefer playwright_profiles/accounts.

        If an older config uses playwright_profiles/ece, attempt a best-effort migration.
        Falls back to the legacy namespace when migration fails.
        """
        profiles_root = (self.config_dir / "playwright_profiles").resolve()
        legacy_root = (profiles_root / "ece").resolve()
        accounts_root = (profiles_root / "accounts").resolve()

        def _has_any_profile_dirs(root: Path) -> bool:
            try:
                if (not root.exists()) or (not root.is_dir()):
                    return False
                for child in root.iterdir():
                    if child.is_dir():
                        return True
            except Exception:
                return False
            return False

        legacy_has_profiles = _has_any_profile_dirs(legacy_root)
        accounts_has_profiles = _has_any_profile_dirs(accounts_root)

        if legacy_has_profiles and (not accounts_has_profiles):
            try:
                if not accounts_root.exists():
                    legacy_root.rename(accounts_root)
                    return "accounts"
            except Exception:
                pass

            try:
                accounts_root.mkdir(parents=True, exist_ok=True)
                for provider_dir in legacy_root.iterdir():
                    if not provider_dir.is_dir():
                        continue

                    target_provider = accounts_root / provider_dir.name
                    if not target_provider.exists():
                        provider_dir.rename(target_provider)
                        continue

                    # Merge identities without overwriting existing destinations.
                    for ident_dir in provider_dir.iterdir():
                        if not ident_dir.is_dir():
                            continue
                        target_ident = target_provider / ident_dir.name
                        if target_ident.exists():
                            continue
                        try:
                            ident_dir.rename(target_ident)
                        except Exception:
                            continue
                return "accounts"
            except Exception:
                return "ece"

        if accounts_has_profiles:
            return "accounts"
        if legacy_has_profiles:
            return "ece"
        return "accounts"

    def _read_credentials_payload(self) -> Dict[str, Any]:
        payload = self._credentials_file.read() or {}
        if not isinstance(payload, dict):
            return {"version": self.CREDENTIALS_VERSION, "providers": {}}

        version = payload.get("version")
        providers = payload.get("providers")
        if not isinstance(version, int) or not isinstance(providers, dict):
            return {"version": self.CREDENTIALS_VERSION, "providers": {}}
        return payload

    def _write_credentials_payload(self, providers: Dict[str, List[Dict[str, Any]]]) -> bool:
        payload: Dict[str, Any] = {
            "version": self.CREDENTIALS_VERSION,
            "providers": providers,
        }
        return self._credentials_file.write(payload)

    def _read_usage_payload(self) -> Dict[str, Any]:
        payload = self._usage_file.read() or {}
        if not isinstance(payload, dict):
            return {"version": self.USAGE_VERSION, "providers": {}}

        version = payload.get("version")
        providers = payload.get("providers")
        if not isinstance(version, int) or not isinstance(providers, dict):
            return {"version": self.USAGE_VERSION, "providers": {}}
        return payload

    def _write_usage_payload(self, providers: Dict[str, Dict[str, float]]) -> bool:
        payload: Dict[str, Any] = {
            "version": self.USAGE_VERSION,
            "providers": providers,
        }
        return self._usage_file.write(payload)

    def get_provider_pairs(self, provider: DriverProvider | str) -> List[CredentialPair]:
        key = _provider_key(provider)
        payload = self._read_credentials_payload()
        providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}

        raw_items = providers.get(key, [])
        if not isinstance(raw_items, list):
            return []

        pairs: List[CredentialPair] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            email = str(item.get("email", "") or "")
            password = str(item.get("password", "") or "")
            pinned = bool(item.get("pinned"))
            disabled = bool(item.get("disabled"))
            pairs.append(CredentialPair(email=email, password=password, pinned=pinned, disabled=disabled))
        return pairs

    def set_provider_pairs(self, provider: DriverProvider | str, pairs: List[CredentialPair]) -> Tuple[bool, List[str]]:
        """
        Persist pairs for a provider.

        Returns (ok, errors).
        """
        key = _provider_key(provider)
        requires_password = _provider_requires_password(provider)
        errors: List[str] = []

        cleaned: List[Dict[str, Any]] = []
        pinned_rows = 0
        enabled_rows = 0
        for idx, pair in enumerate(pairs, start=1):
            email_raw = str(pair.email or "")
            password_raw = str(pair.password or "")
            email = email_raw.strip()
            password = password_raw
            disabled = bool(getattr(pair, "disabled", False))
            pinned = bool(getattr(pair, "pinned", False)) and not disabled

            # no point in empty entries
            if not email and not password.strip():
                continue

            if not email:
                if _provider_accepts_username_identity(provider):
                    errors.append(f"Row {idx}: username/email is empty.")
                else:
                    errors.append(f"Row {idx}: email is empty.")
                continue

            try:
                _validate_provider_identity(provider, email)
            except ValueError as exc:
                errors.append(f"Row {idx}: {exc}")
                continue

            if requires_password and not password:
                errors.append(f"Row {idx}: password is empty.")
                continue

            if pinned:
                pinned_rows += 1
                if pinned_rows > 1:
                    errors.append("Only one row can be pinned at a time.")
                    continue

            item: Dict[str, Any] = {"email": email, "password": password}
            if pinned:
                item["pinned"] = True
            if disabled:
                item["disabled"] = True
            else:
                enabled_rows += 1
            cleaned.append(item)

        if cleaned and enabled_rows <= 0:
            errors.append("At least one saved account must stay enabled.")

        if errors:
            return False, errors

        payload = self._read_credentials_payload()
        providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
        providers = dict(providers)
        providers[key] = cleaned

        ok = self._write_credentials_payload(providers)
        return ok, ([] if ok else ["Failed to write encrypted credentials file."])

    def get_last_used_map(self, provider: DriverProvider | str) -> Dict[str, float]:
        key = _provider_key(provider)
        payload = self._read_usage_payload()
        providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}

        raw = providers.get(key, {})
        if not isinstance(raw, dict):
            return {}

        cleaned: Dict[str, float] = {}
        for email, ts in raw.items():
            try:
                email_norm = _normalize_email(str(email or ""))
                ts_val = float(ts)
            except Exception:
                continue
            if not email_norm:
                continue
            cleaned[email_norm] = ts_val
        return cleaned

    def mark_used(self, provider: DriverProvider | str, email: str) -> bool:
        provider_id = _provider_key(provider)
        email_norm = _normalize_email(email)
        if not email_norm:
            return False

        with EceManager._usage_write_lock:
            payload = self._read_usage_payload()
            providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
            providers = dict(providers)

            usage = providers.get(provider_id, {})
            if not isinstance(usage, dict):
                usage = {}

            usage = dict(usage)
            usage[email_norm] = float(time.time())
            providers[provider_id] = usage

            ok = self._write_usage_payload(providers)
            return ok

    def set_pair_disabled(
        self,
        provider: DriverProvider | str,
        email: str,
        *,
        disabled: bool = True,
        allow_disable_last: bool = False,
    ) -> bool:
        provider_id = _provider_key(provider)
        email_norm = _normalize_email(email)
        if not email_norm:
            return False

        payload = self._read_credentials_payload()
        providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
        raw_items = providers.get(provider_id, [])
        if not isinstance(raw_items, list):
            return False

        updated_items: list[dict[str, Any]] = []
        matched = False
        enabled_rows = 0

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item_email = _normalize_email(str(item.get("email", "") or ""))
            if item_email == email_norm:
                matched = True
                if disabled:
                    item["disabled"] = True
                    item.pop("pinned", None)
                else:
                    item.pop("disabled", None)

            if not bool(item.get("disabled")):
                enabled_rows += 1
            updated_items.append(item)

        if not matched:
            return False
        if disabled and enabled_rows <= 0 and not allow_disable_last:
            return False

        providers = dict(providers)
        providers[provider_id] = updated_items
        return self._write_credentials_payload(providers)

    def _eligible_pairs(
        self,
        provider: DriverProvider | str,
        *,
        exclude_emails: Iterable[str] | None = None,
    ) -> List[CredentialPair]:
        requires_password = _provider_requires_password(provider)
        excluded = {
            _normalize_email(str(email or ""))
            for email in (exclude_emails or [])
            if _normalize_email(str(email or ""))
        }

        candidates: List[CredentialPair] = []
        seen_emails: set[str] = set()
        for pair in self.get_provider_pairs(provider):
            if bool(getattr(pair, "disabled", False)):
                continue
            email = (pair.email or "").strip()
            email_norm = _normalize_email(email)
            password = pair.password or ""
            if not email_norm or (requires_password and not password):
                continue
            if email_norm in excluded or email_norm in seen_emails:
                continue
            seen_emails.add(email_norm)
            candidates.append(
                CredentialPair(
                    email=email,
                    password=password,
                    pinned=bool(getattr(pair, "pinned", False)),
                    disabled=False,
                )
            )

        return candidates

    def get_selectable_pair_count(self, provider: DriverProvider | str) -> int:
        return len(self._eligible_pairs(provider))

    def select_pair(
        self,
        provider: DriverProvider | str,
        *,
        least_used: bool,
        exclude_email: Optional[str] = None,
        exclude_emails: Iterable[str] | None = None,
        prefer_pinned: bool = False,
    ) -> Optional[CredentialPair]:
        excluded = {
            _normalize_email(str(email or ""))
            for email in (exclude_emails or [])
            if _normalize_email(str(email or ""))
        }
        exclude_norm = _normalize_email(exclude_email or "")
        if exclude_norm:
            excluded.add(exclude_norm)

        if prefer_pinned:
            pinned_pair = self.get_pinned_pair(provider, exclude_emails=excluded)
            if pinned_pair is not None:
                return pinned_pair

        candidates = self._eligible_pairs(provider, exclude_emails=excluded)
        if not candidates:
            return None

        if not least_used:
            return random.choice(candidates)

        usage = self.get_last_used_map(provider)

        def sort_key(pair: CredentialPair) -> Tuple[int, float]:
            ts = usage.get(_normalize_email(pair.email))
            if ts is None:
                return (0, 0.0)
            return (1, float(ts))

        candidates_sorted = sorted(candidates, key=sort_key)
        return candidates_sorted[0] if candidates_sorted else None

    def select_parallel_pairs(
        self,
        provider: DriverProvider | str,
        *,
        desired_count: int,
        least_used: bool,
        prefer_pinned: bool = True,
    ) -> List[CredentialPair]:
        try:
            count = max(0, int(desired_count))
        except Exception:
            count = 0
        if count <= 0:
            return []

        candidates = self._eligible_pairs(provider)
        if not candidates:
            return []

        selected: List[CredentialPair] = []
        remaining = list(candidates)

        if prefer_pinned:
            pinned = next((pair for pair in remaining if bool(getattr(pair, "pinned", False))), None)
            if pinned is not None:
                selected.append(pinned)
                pinned_norm = _normalize_email(pinned.email)
                remaining = [
                    pair for pair in remaining if _normalize_email(pair.email) != pinned_norm
                ]

        if least_used:
            usage = self.get_last_used_map(provider)
            random.shuffle(remaining)

            def sort_key(pair: CredentialPair) -> Tuple[int, float]:
                ts = usage.get(_normalize_email(pair.email))
                if ts is None:
                    return (0, 0.0)
                return (1, float(ts))

            remaining = sorted(remaining, key=sort_key)
        else:
            random.shuffle(remaining)

        open_slots = max(0, count - len(selected))
        selected.extend(remaining[:open_slots])
        return selected[:count]

    def get_pinned_pair(
        self,
        provider: DriverProvider | str,
        *,
        exclude_email: Optional[str] = None,
        exclude_emails: Iterable[str] | None = None,
    ) -> Optional[CredentialPair]:
        excluded = {
            _normalize_email(str(email or ""))
            for email in (exclude_emails or [])
            if _normalize_email(str(email or ""))
        }
        exclude_norm = _normalize_email(exclude_email or "")
        if exclude_norm:
            excluded.add(exclude_norm)

        for pair in self._eligible_pairs(provider, exclude_emails=excluded):
            if not bool(getattr(pair, "pinned", False)):
                continue
            return CredentialPair(email=pair.email, password=pair.password, pinned=True, disabled=False)
        return None

    def is_email_pinned(self, provider: DriverProvider | str, email: Optional[str]) -> bool:
        email_norm = _normalize_email(email or "")
        if not email_norm:
            return False

        pinned_pair = self.get_pinned_pair(provider)
        if pinned_pair is None:
            return False
        return _normalize_email(pinned_pair.email) == email_norm

    def get_profile_dir(
        self,
        provider: DriverProvider | str,
        *,
        email: Optional[str],
        slot: int = 0,
    ) -> Path:
        provider_id = _provider_key(provider)
        base = (self.config_dir / "playwright_profiles" / str(self._profile_namespace) / provider_id).resolve()
        ident = "manual"
        if email:
            email_norm = _normalize_email(email)
            if email_norm:
                ident = _hash_email(email_norm)

        suffix = "" if int(slot) <= 0 else f"_{int(slot)}"
        return base / f"{ident}{suffix}"

    def find_next_profile_slot(self, provider: DriverProvider | str, email: str) -> int:
        provider_id = _provider_key(provider)
        base = (self.config_dir / "playwright_profiles" / str(self._profile_namespace) / provider_id).resolve()
        ident = _hash_email(email)

        try:
            if not base.exists():
                return 0
            if not base.is_dir():
                return 0
        except Exception:
            return 0

        used_slots = set()
        try:
            for entry in base.iterdir():
                if not entry.is_dir():
                    continue
                name = entry.name
                if name == ident:
                    used_slots.add(0)
                    continue
                if not name.startswith(f"{ident}_"):
                    continue
                suffix = name[len(ident) + 1 :]
                try:
                    used_slots.add(int(suffix))
                except ValueError:
                    continue
        except Exception:
            return 0

        slot = 0
        while slot in used_slots:
            slot += 1
        return slot

    def rotate_profile_slot(self, provider: DriverProvider | str, email: str, current_slot: int) -> int:
        """
        Pick a different profile slot for the same email (best-effort).
        """
        if not email:
            return 0

        next_slot = self.find_next_profile_slot(provider, email)
        if next_slot != current_slot:
            return next_slot

        # If all existing slots collide, just bump
        try:
            return int(current_slot) + 1
        except Exception:
            return 1

    def prune_usage(self, provider: DriverProvider | str) -> None:
        """
        Best-effort cleanup: remove usage entries that no longer exist in credentials.
        """
        provider_id = _provider_key(provider)
        pairs = self.get_provider_pairs(provider_id)
        allowed = {_normalize_email(p.email) for p in pairs if p.email}

        payload = self._read_usage_payload()
        providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
        usage = providers.get(provider_id, {})
        if not isinstance(usage, dict):
            return

        updated = {k: v for k, v in usage.items() if _normalize_email(str(k)) in allowed}
        if updated == usage:
            return

        providers = dict(providers)
        providers[provider_id] = updated
        ok = self._write_usage_payload(providers)
        if not ok:
            Logger.debug("Accounts: failed to prune usage file.")

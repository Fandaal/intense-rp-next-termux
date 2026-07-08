import copy
import json
from pathlib import Path
from typing import Any, Dict
from cryptography.fernet import Fernet
from drivers.providers import DriverProvider
from .loadouts import (
    LOADOUTS_DEFINITIONS_KEY,
    LOADOUTS_LEGACY_MIGRATION_FLAG,
    LOADOUTS_SETTINGS_KEY,
    LoadoutDefinition,
    deserialize_settings_loadouts,
    get_behavior_category_for_provider,
    get_loadouts_path,
    group_by_provider,
    load_legacy_loadouts_from_file,
    serialize_settings_loadouts,
)
from .schema import SCHEMA, SettingType
from .migrator import SettingsMigrator
from .app_flags import AppFlagsStore
from .location import get_active_config_dir
from utils.logger import Logger


_MISSING = object()
_WELCOME_DISMISSED_FLAG_KEY = "welcome_screen_dismissed"

class ConfigManager:
    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir is not None else get_active_config_dir()
        self.config_dir = self.config_dir.resolve()
        self.settings_file = self.config_dir / "settings.json.enc"
        self.key_file = self.config_dir / "settings.key"
        self.settings_file_existed_on_startup = self.settings_file.exists()
        self.is_first_run = not self.settings_file_existed_on_startup
        self.app_flags = AppFlagsStore(self.config_dir)
        self.settings: Dict[str, Any] = {}
        self._runtime_loadouts_by_provider: dict[DriverProvider, list[LoadoutDefinition]] = {}
        self._runtime_active_loadout_names: dict[DriverProvider, str] = {}
        
        self._ensure_dir()
        self._load_key()
        self.load_settings()

    def reload_from_disk(self) -> None:
        """
        Reload the encryption key and settings data from disk.

        This is useful after external changes to the config directory contents
        (e.g., restoring settings from a backup zip).
        """
        self.config_dir = self.config_dir.resolve()
        self.settings_file = self.config_dir / "settings.json.enc"
        self.key_file = self.config_dir / "settings.key"
        self.app_flags = AppFlagsStore(self.config_dir)
        self._ensure_dir()
        self._load_key()
        self.load_settings()
        self.clear_runtime_loadouts()

    def should_show_welcome(self) -> bool:
        if not self.is_first_run:
            return False
        return not self.app_flags.get_bool(_WELCOME_DISMISSED_FLAG_KEY, default=False)

    def mark_welcome_dismissed(self) -> bool:
        ok = self.app_flags.set(_WELCOME_DISMISSED_FLAG_KEY, True)
        if ok:
            self.is_first_run = False
        return ok

    def _ensure_dir(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_key(self):
        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(self.key)
        self.cipher = Fernet(self.key)

    def load_settings(self):
        if not self.settings_file.exists():
            self._init_default_settings()
            return

        try:
            with open(self.settings_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            self.settings = json.loads(decrypted_data.decode("utf-8"))
            original_settings_json = json.dumps(self.settings, sort_keys=True)
            
            # Migrate settings
            self.settings = SettingsMigrator.migrate(self.settings)
            settings_migrated = json.dumps(self.settings, sort_keys=True) != original_settings_json
            
            # Validate/Merge with schema to ensure all fields exist
            self._merge_defaults()
            loadouts_store_updated = self._ensure_loadouts_store()

            # Best-effort one-time migration helpers
            try:
                from utils.account_migration import migrate_legacy_credentials_to_accounts

                migrate_legacy_credentials_to_accounts(self)
            except Exception as exc:
                Logger.debug(f"Legacy credential import: skipped due to error: {exc}")

            try:
                migrated = self._migrate_legacy_loadouts_from_disk_if_needed()
                loadouts_store_updated = loadouts_store_updated or migrated
            except Exception as exc:
                Logger.warning(f"Legacy loadouts migration: skipped due to error: {exc}")

            if settings_migrated or loadouts_store_updated:
                self.save_settings()
            
        except Exception as e:
            Logger.error(f"Error loading settings: {e}")
            self._init_default_settings()
        finally:
            self.clear_runtime_loadouts()

    def _init_default_settings(self):
        self.settings = {}
        for category in SCHEMA:
            if category.key not in self.settings:
                self.settings[category.key] = {}
            for field in self._iter_default_fields(category.fields):
                self.settings[category.key][field.key] = copy.deepcopy(field.default)
        self._ensure_loadouts_store()
        self.save_settings()

    def _merge_defaults(self):
        updated = False
        for category in SCHEMA:
            if category.key not in self.settings:
                self.settings[category.key] = {}
                updated = True
            for field in self._iter_default_fields(category.fields):
                if field.key not in self.settings[category.key]:
                    self.settings[category.key][field.key] = copy.deepcopy(field.default)
                    updated = True
        if updated:
            self.save_settings()

    def _iter_default_fields(self, fields):
        for field in fields:
            if field.type == SettingType.ROW and field.sub_fields:
                yield from self._iter_default_fields(field.sub_fields)
                continue

            if getattr(field, "transient", False):
                continue

            if field.type in {
                SettingType.BUTTON,
                SettingType.DESCRIPTION,
                SettingType.DIVIDER,
                SettingType.HINT,
                SettingType.REDIRECT,
                SettingType.ROW,
            }:
                continue

            yield field

    def save_settings(self):
        try:
            json_data = json.dumps(self.settings).encode("utf-8")
            encrypted_data = self.cipher.encrypt(json_data)
            
            with open(self.settings_file, "wb") as f:
                f.write(encrypted_data)
        except Exception as e:
            Logger.error(f"Error saving settings: {e}")

    def get_setting(self, category_key: str, field_key: str) -> Any:
        return self.settings.get(category_key, {}).get(field_key)

    def _iter_schema_fields(self, fields):
        for field in fields:
            yield field
            if field.type == SettingType.ROW and field.sub_fields:
                yield from self._iter_schema_fields(field.sub_fields)

    def _get_schema_field(self, category_key: str, field_key: str):
        for category in SCHEMA:
            if category.key != category_key:
                continue
            for field in self._iter_schema_fields(category.fields):
                if field.key == field_key:
                    return field
        return None

    def get_effective_setting(self, category_key: str, field_key: str) -> Any:
        """
        Returns the effective value for a setting, applying schema-driven rules
        such as forced values when dependencies are unmet.
        """
        value = self.get_setting(category_key, field_key)
        field_def = self._get_schema_field(category_key, field_key)
        if not field_def:
            return value

        depends = getattr(field_def, "depends", None)
        if not depends:
            return value

        def _get_setting_value(full_key: str) -> Any:
            try:
                dep_category, dep_field = full_key.split(".", 1)
            except ValueError:
                return None
            return self.get_setting(dep_category, dep_field)

        def _eval_dep_expr(expr: str) -> bool:
            parts = [part.strip() for part in str(expr).split("&&")]
            for part in parts:
                if not part:
                    continue

                if "==" in part:
                    left, right = part.split("==", 1)
                    dep_key = left.strip()
                    expected = right.strip()
                    value = _get_setting_value(dep_key)
                    if isinstance(value, bool):
                        expected_bool = expected.lower() in {"1", "true", "yes", "on"}
                        if value != expected_bool:
                            return False
                    else:
                        if str(value or "").strip() != expected:
                            return False
                    continue

                if "!=" in part:
                    left, right = part.split("!=", 1)
                    dep_key = left.strip()
                    expected = right.strip()
                    value = _get_setting_value(dep_key)
                    if isinstance(value, bool):
                        expected_bool = expected.lower() in {"1", "true", "yes", "on"}
                        if value == expected_bool:
                            return False
                    else:
                        if str(value or "").strip() == expected:
                            return False
                    continue

                value = _get_setting_value(part)
                if not value:
                    return False

            return True

        is_met = _eval_dep_expr(depends)
        forced_value = getattr(field_def, "force_when_dep_unmet", None)
        if (not is_met) and (forced_value is not None):
            return forced_value

        return value

    def set_setting(self, category_key: str, field_key: str, value: Any):
        if category_key not in self.settings:
            self.settings[category_key] = {}
        self.settings[category_key][field_key] = value

    def _ensure_loadouts_store(self) -> bool:
        updated = False

        loadouts_root = self.settings.get(LOADOUTS_SETTINGS_KEY)
        if not isinstance(loadouts_root, dict):
            loadouts_root = {}
            self.settings[LOADOUTS_SETTINGS_KEY] = loadouts_root
            updated = True

        if not isinstance(loadouts_root.get(LOADOUTS_DEFINITIONS_KEY), list):
            loadouts_root[LOADOUTS_DEFINITIONS_KEY] = []
            updated = True

        return updated

    def _migrate_legacy_loadouts_from_disk_if_needed(self) -> bool:
        flag_key = LOADOUTS_LEGACY_MIGRATION_FLAG
        if self.app_flags.get_bool(flag_key, default=False):
            return False

        legacy_path = self.get_loadouts_path()
        if not legacy_path.exists():
            return False

        if self.get_loadouts():
            Logger.info(
                "Loadouts migration: GUI-backed loadouts already exist; "
                "marking legacy loadouts.json migration as complete."
            )
            self.app_flags.set(flag_key, True)
            return False

        legacy_loadouts = load_legacy_loadouts_from_file(legacy_path)
        self.set_loadouts(legacy_loadouts)
        self.app_flags.set(flag_key, True)

        try:
            legacy_path.unlink()
            Logger.success(
                "Loadouts migration: imported legacy loadouts.json into Settings "
                "and deleted the old file."
            )
        except Exception as exc:
            Logger.warning(
                f"Loadouts migration: imported legacy loadouts.json but could not delete it: {exc}"
            )

        return True

    # ------------------------------------------------------------------
    # Loadouts
    # ------------------------------------------------------------------

    def clear_runtime_loadouts(self) -> None:
        self._runtime_loadouts_by_provider = {}
        self._runtime_active_loadout_names = {}

    def has_runtime_loadouts(self) -> bool:
        return bool(self._runtime_loadouts_by_provider)

    def is_loadouts_feature_enabled(self) -> bool:
        return bool(self.settings.get("experimental", {}).get("enable_loadouts"))

    def get_loadouts_path(self) -> Path:
        return get_loadouts_path()

    def get_loadouts(
        self,
        provider: DriverProvider | str | None = None,
    ) -> list[LoadoutDefinition]:
        loadouts_root = self.settings.get(LOADOUTS_SETTINGS_KEY, {})
        raw_definitions = (
            loadouts_root.get(LOADOUTS_DEFINITIONS_KEY, [])
            if isinstance(loadouts_root, dict)
            else []
        )
        loadouts = deserialize_settings_loadouts(raw_definitions)
        normalized_provider = self._normalize_provider(provider)
        if normalized_provider is None:
            return loadouts
        return [loadout for loadout in loadouts if loadout.provider == normalized_provider]

    def set_loadouts(self, loadouts: list[LoadoutDefinition]) -> None:
        self._ensure_loadouts_store()
        loadouts_root = self.settings.setdefault(LOADOUTS_SETTINGS_KEY, {})
        if not isinstance(loadouts_root, dict):
            loadouts_root = {}
            self.settings[LOADOUTS_SETTINGS_KEY] = loadouts_root
        loadouts_root[LOADOUTS_DEFINITIONS_KEY] = serialize_settings_loadouts(loadouts)

    def _normalize_provider(self, provider: DriverProvider | str | None) -> DriverProvider | None:
        if isinstance(provider, DriverProvider):
            return provider
        if provider is None:
            return None
        return DriverProvider.from_setting(provider)

    def _loadout_flag_key(self) -> str:
        return "loadouts_active_by_provider"

    def _get_persisted_active_loadout_names(self) -> dict[str, str]:
        raw_value = self.app_flags.get(self._loadout_flag_key(), {})
        if not isinstance(raw_value, dict):
            return {}

        normalized: dict[str, str] = {}
        for raw_provider_key, raw_name in raw_value.items():
            provider_key = str(raw_provider_key or "").strip()
            loadout_name = str(raw_name or "").strip()
            if provider_key and loadout_name:
                normalized[provider_key] = loadout_name
        return normalized

    def _persist_active_loadout_names(self, names_by_provider: dict[DriverProvider, str]) -> None:
        payload = {
            provider.key: str(name).strip()
            for provider, name in names_by_provider.items()
            if str(name or "").strip()
        }
        self.app_flags.set(self._loadout_flag_key(), payload)

    def get_preferred_loadout_name(
        self,
        provider: DriverProvider | str,
        available_loadouts: list[LoadoutDefinition] | None = None,
    ) -> str | None:
        normalized_provider = self._normalize_provider(provider)
        if normalized_provider is None:
            return None

        candidates = available_loadouts
        if candidates is None:
            try:
                candidates = self.get_loadouts(normalized_provider)
            except Exception:
                candidates = []

        persisted = self._get_persisted_active_loadout_names().get(normalized_provider.key)
        if persisted:
            for loadout in candidates:
                if loadout.name == persisted:
                    return loadout.name

        if candidates:
            return candidates[0].name
        return persisted

    def set_preferred_loadout_name(self, provider: DriverProvider | str, loadout_name: str) -> None:
        normalized_provider = self._normalize_provider(provider)
        normalized_name = str(loadout_name or "").strip()
        if normalized_provider is None or not normalized_name:
            raise ValueError("A valid provider and loadout name are required.")

        available = self.get_loadouts(normalized_provider)
        if not any(loadout.name == normalized_name for loadout in available):
            raise ValueError(
                f"Loadout '{normalized_name}' is not available for provider '{normalized_provider.value}'."
            )

        persisted = self._get_persisted_active_loadout_names()
        persisted[normalized_provider.key] = normalized_name
        payload = {
            provider_key: value
            for provider_key, value in persisted.items()
            if provider_key and str(value or "").strip()
        }
        self.app_flags.set(self._loadout_flag_key(), payload)

    def prepare_runtime_loadouts(
        self,
        *,
        required_providers: list[DriverProvider] | tuple[DriverProvider, ...] | None = None,
    ) -> None:
        self.clear_runtime_loadouts()
        if not self.is_loadouts_feature_enabled():
            return

        loadouts_by_provider = group_by_provider(self.get_loadouts())

        active_names: dict[DriverProvider, str] = {}
        persisted = self._get_persisted_active_loadout_names()
        updated = False

        for provider, provider_loadouts in loadouts_by_provider.items():
            preferred_name = persisted.get(provider.key, "")
            selected_name = next(
                (loadout.name for loadout in provider_loadouts if loadout.name == preferred_name),
                None,
            )
            if selected_name is None and provider_loadouts:
                selected_name = provider_loadouts[0].name
                if preferred_name != selected_name:
                    updated = True
            if selected_name:
                active_names[provider] = selected_name

        required = [provider for provider in (required_providers or []) if isinstance(provider, DriverProvider)]
        for provider in required:
            if not loadouts_by_provider.get(provider):
                raise ValueError(
                    f"Loadouts are enabled, but no loadouts were defined for '{provider.value}'."
                )

        self._runtime_loadouts_by_provider = loadouts_by_provider
        self._runtime_active_loadout_names = active_names

        if updated:
            self._persist_active_loadout_names(active_names)

    def get_runtime_active_loadout(self, provider: DriverProvider | str | None) -> LoadoutDefinition | None:
        normalized_provider = self._normalize_provider(provider)
        if normalized_provider is None:
            return None

        provider_loadouts = self._runtime_loadouts_by_provider.get(normalized_provider) or []
        if not provider_loadouts:
            return None

        active_name = self._runtime_active_loadout_names.get(normalized_provider)
        if active_name:
            for loadout in provider_loadouts:
                if loadout.name == active_name:
                    return loadout

        fallback = provider_loadouts[0]
        self._runtime_active_loadout_names[normalized_provider] = fallback.name
        return fallback

    def get_runtime_active_loadout_name(self, provider: DriverProvider | str | None) -> str | None:
        loadout = self.get_runtime_active_loadout(provider)
        return loadout.name if loadout is not None else None

    def get_runtime_loadout_setting(
        self,
        provider: DriverProvider | str | None,
        category_key: str,
        field_key: str,
    ) -> Any:
        normalized_provider = self._normalize_provider(provider)
        if normalized_provider is None:
            return _MISSING

        loadout = self.get_runtime_active_loadout(normalized_provider)
        if loadout is None:
            return _MISSING

        if category_key == "formatting":
            return loadout.settings.get(field_key, _MISSING)

        behavior_category = get_behavior_category_for_provider(normalized_provider)
        if behavior_category and category_key == behavior_category:
            return loadout.settings.get(field_key, _MISSING)

        return _MISSING

    def for_provider(self, provider: DriverProvider | str) -> "ProviderScopedConfigView":
        normalized_provider = self._normalize_provider(provider)
        if normalized_provider is None:
            raise ValueError(f"Unknown provider: {provider}")
        return ProviderScopedConfigView(self, normalized_provider)


class ProviderScopedConfigView:
    """
    Provider-bound config view used by runtime drivers.

    The base ConfigManager continues to expose the raw saved visual settings.
    Runtime drivers read through this proxy instead, so loadouts only affect the
    active provider runtime and never overwrite what the Settings UI restores.
    """

    def __init__(self, manager: ConfigManager, provider: DriverProvider):
        self._manager = manager
        self._provider = provider

    @property
    def bound_provider(self) -> DriverProvider:
        return self._provider

    @property
    def config_dir(self):
        return self._manager.config_dir

    @property
    def app_flags(self):
        return self._manager.app_flags

    def get_setting(self, category_key: str, field_key: str) -> Any:
        override = self._manager.get_runtime_loadout_setting(self._provider, category_key, field_key)
        if override is not _MISSING:
            return override
        return self._manager.get_setting(category_key, field_key)

    def get_effective_setting(self, category_key: str, field_key: str) -> Any:
        override = self._manager.get_runtime_loadout_setting(self._provider, category_key, field_key)
        if override is not _MISSING:
            return override
        return self._manager.get_effective_setting(category_key, field_key)

    def get_active_loadout_name(self, *, runtime: bool = True) -> str | None:
        if runtime:
            return self._manager.get_runtime_active_loadout_name(self._provider)
        return self._manager.get_preferred_loadout_name(self._provider)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._manager, name)

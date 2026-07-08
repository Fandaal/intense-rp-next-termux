from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from config.location import get_local_anchor_dir
from config.migrator import migrate_glm_model_value
from config.schema import SCHEMA, SettingField, SettingType
from drivers.providers import (
    DriverProvider,
    get_provider_behavior_category_key,
    provider_options,
)
from utils.ip_utils import normalize_ip_list


LOADOUTS_FILENAME = "loadouts.json"
LOADOUTS_SETTINGS_KEY = "loadouts"
LOADOUTS_DEFINITIONS_KEY = "definitions"
LOADOUTS_LEGACY_MIGRATION_FLAG = "loadouts.legacy_json_migrated"

LOADOUT_META_KEY = "Meta"
LOADOUT_META_COMMENT_KEY = "_Comment"

@dataclass(frozen=True)
class LoadoutDefinition:
    name: str
    provider: DriverProvider
    settings: dict[str, Any]
    meta_comment: str | None = None


class LoadoutValidationError(ValueError):
    """Raised when a legacy loadouts.json file is missing or invalid."""


def get_loadouts_path() -> Path:
    return get_local_anchor_dir().resolve() / LOADOUTS_FILENAME


def _iter_persisted_fields(fields: Iterable[SettingField]) -> Iterable[SettingField]:
    for field in fields:
        if field.type == SettingType.ROW and field.sub_fields:
            yield from _iter_persisted_fields(field.sub_fields)
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


def _get_category_fields(category_key: str) -> dict[str, SettingField]:
    for category in SCHEMA:
        if category.key != category_key:
            continue
        return {field.key: field for field in _iter_persisted_fields(category.fields)}
    return {}


def get_behavior_category_for_provider(provider: DriverProvider) -> str | None:
    return get_provider_behavior_category_key(provider)


def get_loadout_field_defs(provider: DriverProvider) -> dict[str, SettingField]:
    return {
        field_key: field_def
        for field_key, (_category_key, field_def) in get_loadout_field_bindings(provider).items()
    }


def get_loadout_field_bindings(provider: DriverProvider) -> dict[str, tuple[str, SettingField]]:
    bindings: dict[str, tuple[str, SettingField]] = {}

    for field_key, field_def in _get_category_fields("formatting").items():
        bindings[field_key] = ("formatting", field_def)

    behavior_category = get_behavior_category_for_provider(provider)
    if behavior_category:
        for field_key, field_def in _get_category_fields(behavior_category).items():
            bindings[field_key] = (behavior_category, field_def)

    return bindings


def _normalize_provider(value: Any) -> DriverProvider | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    return DriverProvider.from_setting(raw)


def _clone_value(value: Any) -> Any:
    return copy.deepcopy(value)


def build_default_loadout_settings(provider: DriverProvider) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for field_key, (_category_key, field_def) in get_loadout_field_bindings(provider).items():
        settings[field_key] = _clone_value(field_def.default)
    return settings


def build_visual_loadout_settings(config_manager: Any, provider: DriverProvider) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for field_key, (category_key, field_def) in get_loadout_field_bindings(provider).items():
        value = None
        try:
            value = config_manager.get_setting(category_key, field_key)
        except Exception:
            value = None
        if value is None and not getattr(field_def, "nullable", False):
            value = field_def.default
        settings[field_key] = _clone_value(value)
    return settings


def deserialize_settings_loadouts(raw_value: Any) -> list[LoadoutDefinition]:
    if not isinstance(raw_value, list):
        return []

    loadouts: list[LoadoutDefinition] = []
    seen_names: set[tuple[DriverProvider, str]] = set()

    for item in raw_value:
        if not isinstance(item, dict):
            continue

        provider = _normalize_provider(item.get("provider"))
        name = str(item.get("name") or "").strip()
        settings_payload = item.get("settings")
        meta_comment = item.get("meta_comment")

        if provider is None or not name or not isinstance(settings_payload, dict):
            continue
        if (meta_comment is not None) and (not isinstance(meta_comment, str)):
            meta_comment = None

        dedupe_key = (provider, name.casefold())
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)

        normalized_settings = build_default_loadout_settings(provider)
        for field_key in normalized_settings:
            if field_key in settings_payload:
                normalized_settings[field_key] = _clone_value(settings_payload.get(field_key))

        loadouts.append(
            LoadoutDefinition(
                name=name,
                provider=provider,
                settings=normalized_settings,
                meta_comment=meta_comment,
            )
        )

    return loadouts


def serialize_settings_loadouts(loadouts: Iterable[LoadoutDefinition]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for loadout in loadouts:
        if not isinstance(loadout, LoadoutDefinition):
            continue
        payload.append(
            {
                "name": loadout.name,
                "provider": loadout.provider.value,
                "settings": _clone_value(loadout.settings),
                "meta_comment": loadout.meta_comment,
            }
        )
    return payload


def group_by_provider(loadouts: Iterable[LoadoutDefinition]) -> dict[DriverProvider, list[LoadoutDefinition]]:
    grouped: dict[DriverProvider, list[LoadoutDefinition]] = {}
    for loadout in loadouts:
        grouped.setdefault(loadout.provider, []).append(loadout)
    return grouped


def _validation_prefix(index: int, provider: DriverProvider | None = None, name: str | None = None) -> str:
    parts = [f"Loadout #{index}"]
    if provider is not None:
        parts.append(provider.value)
    if name:
        parts.append(name)
    return " / ".join(parts)


def _validate_meta(index: int, item: dict[str, Any]) -> tuple[DriverProvider, str, str | None]:
    meta = item.get(LOADOUT_META_KEY)
    if not isinstance(meta, dict):
        raise LoadoutValidationError(f"Loadout #{index}: missing or invalid '{LOADOUT_META_KEY}' object.")

    allowed_meta_keys = {"Name", "Provider", LOADOUT_META_COMMENT_KEY}
    extra_meta_keys = sorted(set(meta.keys()) - allowed_meta_keys)
    if extra_meta_keys:
        raise LoadoutValidationError(
            f"Loadout #{index}: unknown Meta field(s): {', '.join(extra_meta_keys)}."
        )

    raw_name = meta.get("Name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise LoadoutValidationError(f"Loadout #{index}: Meta.Name must be a non-empty string.")
    name = raw_name.strip()

    provider = _normalize_provider(meta.get("Provider"))
    if provider is None:
        valid_names = ", ".join(provider_options())
        raise LoadoutValidationError(
            f"{_validation_prefix(index, name=name)}: Meta.Provider must be one of: {valid_names}."
        )

    raw_comment = meta.get(LOADOUT_META_COMMENT_KEY)
    if (raw_comment is not None) and (not isinstance(raw_comment, str)):
        raise LoadoutValidationError(
            f"{_validation_prefix(index, provider, name)}: Meta.{LOADOUT_META_COMMENT_KEY} must be a string."
        )

    return provider, name, raw_comment


def _validate_field_type(prefix: str, field: SettingField, value: Any) -> Any:
    if value is None:
        if getattr(field, "nullable", False):
            return None
        raise LoadoutValidationError(f"{prefix}: '{field.key}' cannot be null.")

    if field.type == SettingType.BOOLEAN:
        if not isinstance(value, bool):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be true or false.")
        return value

    if field.type == SettingType.INTEGER:
        if isinstance(value, bool) or (not isinstance(value, int)):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be an integer.")
        return value

    if field.type in {
        SettingType.STRING,
        SettingType.PASSWORD,
        SettingType.TEXTAREA,
        SettingType.DIRECTORY,
    }:
        if not isinstance(value, str):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be a string.")
        return value

    if field.type == SettingType.DROPDOWN:
        if not isinstance(value, str):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be a string.")
        options = [str(option) for option in (field.options or [])]
        if options and value not in options:
            raise LoadoutValidationError(
                f"{prefix}: '{field.key}' must be one of: {', '.join(options)}."
            )
        return value

    if field.type == SettingType.SWITCHER:
        if not isinstance(value, str):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be a string.")
        options: list[str] = []
        disabled_options: set[str] = set()
        for option in field.options or []:
            if isinstance(option, dict):
                option_value = str(option.get("value") or option.get("key") or option.get("id") or "").strip()
                if not option_value:
                    option_value = str(option.get("label") or option.get("name") or option.get("display") or "").strip()
                is_enabled = bool(option.get("enabled", True))
            elif isinstance(option, (tuple, list)):
                option_value = str(option[1] if len(option) >= 2 else option[0]).strip()
                is_enabled = bool(option[2]) if len(option) >= 3 else True
            else:
                option_value = str(option or "").strip()
                is_enabled = True
            if not option_value:
                continue
            if is_enabled:
                options.append(option_value)
            else:
                disabled_options.add(option_value)
        if value in disabled_options:
            raise LoadoutValidationError(f"{prefix}: '{field.key}' option '{value}' is disabled.")
        if options and value not in options:
            raise LoadoutValidationError(
                f"{prefix}: '{field.key}' must be one of: {', '.join(options)}."
            )
        return value

    if field.type == SettingType.INPUT_PAIR:
        if not isinstance(value, list):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be a list of [name, value] pairs.")
        normalized_pairs: list[list[str]] = []
        for pair_index, pair in enumerate(value, start=1):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise LoadoutValidationError(
                    f"{prefix}: '{field.key}' pair #{pair_index} must contain exactly 2 items."
                )
            left, right = pair
            if not isinstance(left, str) or not isinstance(right, str):
                raise LoadoutValidationError(
                    f"{prefix}: '{field.key}' pair #{pair_index} must contain only strings."
                )
            normalized_pairs.append([left, right])
        return normalized_pairs

    if field.type == SettingType.INPUT_LIST:
        if not isinstance(value, list):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must be a list.")
        if any(not isinstance(item, str) for item in value):
            raise LoadoutValidationError(f"{prefix}: '{field.key}' must contain only strings.")
        return list(value)

    raise LoadoutValidationError(
        f"{prefix}: '{field.key}' uses unsupported field type '{field.type.value}'."
    )


def _validate_field_value(prefix: str, field: SettingField, value: Any) -> Any:
    normalized = _validate_field_type(prefix, field, value)

    try:
        if field.validator:
            field.validator(normalized)
        if field.type == SettingType.INPUT_LIST and field.key == "ip_whitelist":
            normalized = normalize_ip_list(normalized)
    except ValueError as exc:
        raise LoadoutValidationError(f"{prefix}: '{field.key}' is invalid: {exc}") from exc

    return normalized


def load_legacy_loadouts_from_file(path: Path) -> list[LoadoutDefinition]:
    target = Path(path).resolve()
    if not target.exists():
        raise LoadoutValidationError(f"Legacy loadouts file does not exist: {target}")

    try:
        raw_text = target.read_text(encoding="utf-8")
    except Exception as exc:
        raise LoadoutValidationError(f"Failed to read '{target}': {exc}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LoadoutValidationError(
            f"Invalid JSON in '{target.name}' at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, list):
        raise LoadoutValidationError(f"'{target.name}' must contain a top-level JSON list.")

    seen_names: set[tuple[DriverProvider, str]] = set()
    loadouts: list[LoadoutDefinition] = []

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise LoadoutValidationError(f"Loadout #{index}: each entry must be a JSON object.")

        provider, name, meta_comment = _validate_meta(index, item)
        prefix = _validation_prefix(index, provider, name)
        field_defs = get_loadout_field_defs(provider)

        actual_keys = set(item.keys()) - {LOADOUT_META_KEY}
        expected_keys = set(field_defs.keys())

        missing_keys = sorted(expected_keys - actual_keys)
        extra_keys = sorted(actual_keys - expected_keys)
        if missing_keys:
            raise LoadoutValidationError(f"{prefix}: missing field(s): {', '.join(missing_keys)}.")
        if extra_keys:
            raise LoadoutValidationError(f"{prefix}: unknown field(s): {', '.join(extra_keys)}.")

        dedupe_key = (provider, name.casefold())
        if dedupe_key in seen_names:
            raise LoadoutValidationError(
                f"{prefix}: duplicate Meta.Name for provider '{provider.value}'. Names must be unique per provider."
            )
        seen_names.add(dedupe_key)

        settings: dict[str, Any] = {}
        for field_key, field in field_defs.items():
            value = item.get(field_key)
            if provider is DriverProvider.GLM_CHAT and field_key == "model":
                value = migrate_glm_model_value(value)
            settings[field_key] = _validate_field_value(prefix, field, value)

        loadouts.append(
            LoadoutDefinition(
                name=name,
                provider=provider,
                settings=settings,
                meta_comment=meta_comment,
            )
        )

    return loadouts

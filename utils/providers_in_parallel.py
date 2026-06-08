from __future__ import annotations

from typing import Any

from drivers.providers import DriverProvider, is_provider_locked


PARALLEL_PROVIDER_FIELD_BY_PROVIDER: dict[DriverProvider, str] = {
    DriverProvider.DEEPSEEK: "parallel_enable_deepseek",
    DriverProvider.GLM_CHAT: "parallel_enable_glm",
    DriverProvider.MOONSHOT: "parallel_enable_moonshot",
    DriverProvider.QWEN_LM: "parallel_enable_qwen",
    DriverProvider.PERPLEXITY: "parallel_enable_perplexity",
    DriverProvider.HUGGINGCHAT: "parallel_enable_huggingchat",
    DriverProvider.AI_STUDIO: "parallel_enable_aistudio",
}

PARALLEL_PROVIDER_INSTANCE_FIELD_BY_PROVIDER: dict[DriverProvider, str] = {
    DriverProvider.DEEPSEEK: "parallel_instances_deepseek",
    DriverProvider.GLM_CHAT: "parallel_instances_glm",
    DriverProvider.MOONSHOT: "parallel_instances_moonshot",
    DriverProvider.QWEN_LM: "parallel_instances_qwen",
    DriverProvider.PERPLEXITY: "parallel_instances_perplexity",
    DriverProvider.HUGGINGCHAT: "parallel_instances_huggingchat",
    DriverProvider.AI_STUDIO: "parallel_instances_aistudio",
}

MAX_FULL_PARALLEL_PROVIDER_INSTANCES = 32


def get_current_provider(config_manager: Any) -> DriverProvider:
    try:
        provider_setting = config_manager.get_setting("providers_credentials", "provider")
    except Exception:
        provider_setting = None

    provider = DriverProvider.from_setting(provider_setting)
    return provider if provider is not None else DriverProvider.DEEPSEEK


def is_parallel_feature_enabled(config_manager: Any) -> bool:
    try:
        return bool(config_manager.get_setting("experimental", "providers_in_parallel"))
    except Exception:
        return False


def is_parallel_request_queue_feature_enabled(config_manager: Any) -> bool:
    try:
        return bool(config_manager.get_setting("experimental", "parallelize_request_queue"))
    except Exception:
        return False


def _get_effective_bool_setting(config_manager: Any, category: str, field: str) -> bool:
    getter = getattr(config_manager, "get_effective_setting", None)
    try:
        if callable(getter):
            return bool(getter(category, field))
        return bool(config_manager.get_setting(category, field))
    except Exception:
        return False


def is_full_parallelization_feature_enabled(config_manager: Any) -> bool:
    try:
        return bool(config_manager.get_setting("experimental", "full_parallelization"))
    except Exception:
        return False


def is_full_parallelization_active(config_manager: Any) -> bool:
    return (
        is_parallel_feature_enabled(config_manager)
        and is_parallel_request_queue_feature_enabled(config_manager)
        and is_full_parallelization_feature_enabled(config_manager)
    )


def get_parallel_selected_providers(config_manager: Any) -> list[DriverProvider]:
    current_provider = get_current_provider(config_manager)
    selected: list[DriverProvider] = [current_provider]

    for provider in DriverProvider:
        if provider == current_provider:
            continue

        field_key = PARALLEL_PROVIDER_FIELD_BY_PROVIDER.get(provider)
        if not field_key:
            continue

        enabled = _get_effective_bool_setting(config_manager, "experimental", field_key)

        if enabled and not is_provider_locked(provider, config_manager):
            selected.append(provider)

    return selected


def get_parallel_provider_instance_count(config_manager: Any, provider: DriverProvider) -> int:
    if not is_full_parallelization_active(config_manager):
        return 1

    field_key = PARALLEL_PROVIDER_INSTANCE_FIELD_BY_PROVIDER.get(provider)
    if not field_key:
        return 1

    try:
        raw_value = config_manager.get_setting("experimental", field_key)
    except Exception:
        raw_value = None

    try:
        count = int(raw_value)
    except (TypeError, ValueError):
        count = 1

    return max(1, min(MAX_FULL_PARALLEL_PROVIDER_INSTANCES, count))


def get_parallel_provider_instance_counts(config_manager: Any) -> dict[DriverProvider, int]:
    return {
        provider: get_parallel_provider_instance_count(config_manager, provider)
        for provider in get_parallel_selected_providers(config_manager)
    }


def get_parallel_total_instance_count(config_manager: Any) -> int:
    return sum(get_parallel_provider_instance_counts(config_manager).values())


def is_parallel_runtime_active(config_manager: Any) -> bool:
    if not is_parallel_feature_enabled(config_manager):
        return False

    selected_providers = get_parallel_selected_providers(config_manager)
    if len(selected_providers) >= 2:
        return True

    return is_full_parallelization_active(config_manager) and (
        get_parallel_total_instance_count(config_manager) >= 2
    )


def is_parallel_request_queue_active(config_manager: Any) -> bool:
    return is_parallel_runtime_active(config_manager) and is_parallel_request_queue_feature_enabled(
        config_manager
    )

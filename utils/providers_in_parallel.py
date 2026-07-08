from __future__ import annotations

from typing import Any

from drivers.providers import DriverProvider, is_provider_locked


PARALLEL_MODE_PROVIDER_LANES = "provider_lanes"
PARALLEL_MODE_CONCURRENT_PROVIDER_LANES = "concurrent_provider_lanes"
PARALLEL_MODE_FULL_PARALLEL_LANES = "full_parallel_lanes"

PARALLEL_MODE_LABEL_BY_KEY = {
    PARALLEL_MODE_PROVIDER_LANES: "One Instance per Provider",
    PARALLEL_MODE_CONCURRENT_PROVIDER_LANES: "One Instance per Provider + Concurrent Requests",
    PARALLEL_MODE_FULL_PARALLEL_LANES: "Multiple Instances per Provider + Concurrent Requests",
}

MAX_FULL_PARALLEL_PROVIDER_INSTANCES = 32


def _all_parallel_providers() -> list[DriverProvider]:
    return [
        DriverProvider.DEEPSEEK,
        DriverProvider.GLM_CHAT,
        DriverProvider.MOONSHOT,
        DriverProvider.QWEN_LM,
        DriverProvider.PERPLEXITY,
        DriverProvider.HUGGINGCHAT,
        DriverProvider.AI_STUDIO,
        DriverProvider.MIMO,
    ]


def get_current_provider(config_manager: Any) -> DriverProvider:
    try:
        provider_setting = config_manager.get_setting("providers_credentials", "provider")
    except Exception:
        provider_setting = None

    provider = DriverProvider.from_setting(provider_setting)
    return provider if provider is not None else DriverProvider.DEEPSEEK


def _get_effective_setting(config_manager: Any, category: str, field: str) -> Any:
    getter = getattr(config_manager, "get_effective_setting", None)
    try:
        if callable(getter):
            return getter(category, field)
        return config_manager.get_setting(category, field)
    except Exception:
        return None


def _get_effective_bool_setting(config_manager: Any, category: str, field: str) -> bool:
    return bool(_get_effective_setting(config_manager, category, field))


def is_parallel_feature_enabled(config_manager: Any) -> bool:
    return _get_effective_bool_setting(config_manager, "runtime", "providers_in_parallel")


def get_parallelization_mode(config_manager: Any) -> str:
    raw_mode = str(_get_effective_setting(config_manager, "runtime", "parallelization_mode") or "").strip()
    if raw_mode in PARALLEL_MODE_LABEL_BY_KEY:
        return raw_mode
    for key, label in PARALLEL_MODE_LABEL_BY_KEY.items():
        if raw_mode == label:
            return key
    return PARALLEL_MODE_PROVIDER_LANES


def is_parallel_request_queue_feature_enabled(config_manager: Any) -> bool:
    return get_parallelization_mode(config_manager) in {
        PARALLEL_MODE_CONCURRENT_PROVIDER_LANES,
        PARALLEL_MODE_FULL_PARALLEL_LANES,
    }


def is_parallel_concurrent_launch_enabled(config_manager: Any) -> bool:
    return _get_effective_bool_setting(
        config_manager,
        "runtime",
        "parallel_concurrent_launch",
    )


def is_parallel_launch_batching_enabled(config_manager: Any) -> bool:
    return (
        is_parallel_concurrent_launch_enabled(config_manager)
        and _get_effective_bool_setting(
            config_manager,
            "runtime",
            "parallel_launch_in_batches",
        )
    )


def get_parallel_launch_batch_size(config_manager: Any) -> int:
    raw_value = _get_effective_setting(
        config_manager,
        "runtime",
        "parallel_launch_batch_size",
    )

    try:
        count = int(raw_value)
    except (TypeError, ValueError):
        count = 2

    return max(1, min(MAX_FULL_PARALLEL_PROVIDER_INSTANCES, count))


def is_full_parallelization_feature_enabled(config_manager: Any) -> bool:
    return get_parallelization_mode(config_manager) == PARALLEL_MODE_FULL_PARALLEL_LANES


def is_full_parallelization_active(config_manager: Any) -> bool:
    return (
        is_parallel_feature_enabled(config_manager)
        and is_parallel_request_queue_feature_enabled(config_manager)
        and is_full_parallelization_feature_enabled(config_manager)
    )


def _normalize_lane_settings(value: Any) -> tuple[list[DriverProvider], dict[DriverProvider, int]]:
    if not isinstance(value, dict):
        value = {}

    raw_providers = value.get("providers")
    if not isinstance(raw_providers, list):
        raw_providers = []

    raw_instances = value.get("instances")
    if not isinstance(raw_instances, dict):
        raw_instances = {}

    selected_set: set[DriverProvider] = set()
    for raw_provider in raw_providers:
        provider = DriverProvider.from_setting(raw_provider)
        if provider is not None:
            selected_set.add(provider)

    selected = [provider for provider in _all_parallel_providers() if provider in selected_set]

    counts: dict[DriverProvider, int] = {}
    for provider in _all_parallel_providers():
        raw_count = raw_instances.get(provider.value, raw_instances.get(provider.name, 1))
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 1
        counts[provider] = max(1, min(MAX_FULL_PARALLEL_PROVIDER_INSTANCES, count))

    return selected, counts


def get_parallel_lane_settings(config_manager: Any) -> tuple[list[DriverProvider], dict[DriverProvider, int]]:
    return _normalize_lane_settings(
        _get_effective_setting(config_manager, "runtime", "parallel_provider_lanes")
    )


def get_parallel_selected_providers(config_manager: Any) -> list[DriverProvider]:
    current_provider = get_current_provider(config_manager)
    selected, _counts = get_parallel_lane_settings(config_manager)
    resolved: list[DriverProvider] = [current_provider]

    for provider in selected:
        if provider == current_provider:
            continue
        if is_provider_locked(provider, config_manager):
            continue
        resolved.append(provider)

    return resolved


def get_parallel_provider_instance_count(config_manager: Any, provider: DriverProvider) -> int:
    if not is_full_parallelization_active(config_manager):
        return 1

    _selected, counts = get_parallel_lane_settings(config_manager)
    return counts.get(provider, 1)


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

from __future__ import annotations

from typing import Any

from aistudio_driver import AIStudioDriver
from deepseek_driver import DeepSeekDriver
from glm_driver import GLMDriver
from huggingchat_driver import HuggingChatDriver
from moonshot_driver import MoonshotDriver
from perplexity_driver import PerplexityDriver
from qwen_driver import QwenLMDriver
from drivers.base_driver import BaseDriver
from drivers.providers import DriverProvider, is_provider_locked, provider_lock_reason
from utils.logger import Logger


def _provider_scoped_config(config_manager: Any, provider: DriverProvider) -> Any:
    scoped_factory = getattr(config_manager, "for_provider", None)
    if callable(scoped_factory):
        try:
            return scoped_factory(provider)
        except Exception:
            return config_manager
    return config_manager


def create_driver_for_provider(config_manager: Any, provider: DriverProvider) -> BaseDriver:
    scoped_config = _provider_scoped_config(config_manager, provider)
    if provider == DriverProvider.DEEPSEEK:
        return DeepSeekDriver(scoped_config)
    if provider == DriverProvider.GLM_CHAT:
        return GLMDriver(scoped_config)
    if provider == DriverProvider.MOONSHOT:
        return MoonshotDriver(scoped_config)
    if provider == DriverProvider.QWEN_LM:
        return QwenLMDriver(scoped_config)
    if provider == DriverProvider.PERPLEXITY:
        return PerplexityDriver(scoped_config)
    if provider == DriverProvider.HUGGINGCHAT:
        return HuggingChatDriver(scoped_config)
    if provider == DriverProvider.AI_STUDIO:
        return AIStudioDriver(scoped_config)

    return DeepSeekDriver(scoped_config)


def create_driver(config_manager: Any) -> BaseDriver:
    provider_setting = None
    try:
        provider_setting = config_manager.get_setting("providers_credentials", "provider")
    except Exception:
        provider_setting = None

    provider = DriverProvider.from_setting(provider_setting)
    if provider is None:
        Logger.warning(f"Unknown driver provider '{provider_setting}', falling back to DeepSeek.")
        provider = DriverProvider.DEEPSEEK
    elif is_provider_locked(provider, config_manager):
        reason = provider_lock_reason(provider) or f"{provider.value} is currently locked."
        Logger.warning(f"Selected provider is locked: {reason}")
        raise RuntimeError(reason)

    Logger.info(f"Selected driver provider: {provider.value}")
    return create_driver_for_provider(config_manager, provider)

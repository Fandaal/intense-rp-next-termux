from __future__ import annotations

import asyncio
import inspect
from collections import Counter
from dataclasses import dataclass
from typing import Any

from drivers.base_driver import BaseDriver
from drivers.factory import create_driver_for_provider
from drivers.providers import DriverProvider
from ece.manager import EceManager
from ece.models import CredentialPair
from utils.logger import Logger
from utils.providers_in_parallel import (
    get_current_provider,
    get_parallel_launch_batch_size,
    get_parallel_provider_instance_count,
    get_parallel_selected_providers,
    is_parallel_concurrent_launch_enabled,
    is_parallel_launch_batching_enabled,
    is_full_parallelization_active,
)


def _normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


@dataclass(frozen=True)
class _StartupResult:
    provider: DriverProvider
    driver: BaseDriver
    label: str
    error: Exception | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class ParallelDriversManager:
    def __init__(self, config_manager: Any):
        self.config_manager = config_manager
        self.current_provider = get_current_provider(config_manager)
        self.providers = get_parallel_selected_providers(config_manager)
        self._full_parallelization_active = is_full_parallelization_active(config_manager)
        self._driver_entries: list[tuple[DriverProvider, BaseDriver]] = []
        self._driver_labels_by_id: dict[int, str] = {}
        self.drivers: dict[DriverProvider, BaseDriver] = {}
        self._build_driver_entries()
        self._rebuild_driver_indexes()

        self.is_running = False
        self.notify_user_callback = None
        self.request_user_text_callback = None
        self.profile_compatibility_warning_callback = None
        self.on_crash_callback = None
        self._crash_notified = False

    def _select_least_used_enabled(self) -> bool:
        try:
            return bool(self.config_manager.get_setting("providers_credentials", "select_least_used"))
        except Exception:
            return False

    def _get_ece_manager(self) -> EceManager:
        config_dir = getattr(self.config_manager, "config_dir", None) or "config_data"
        return EceManager(config_dir)

    def _startup_pairs_for_provider(self, provider: DriverProvider) -> list[CredentialPair | None]:
        if not self._full_parallelization_active:
            return [None]

        desired_count = get_parallel_provider_instance_count(self.config_manager, provider)
        if desired_count <= 1:
            return [None]

        try:
            ece_manager = self._get_ece_manager()
            selectable_count = ece_manager.get_selectable_pair_count(provider)
        except Exception as exc:
            Logger.warning(
                f"Full Parallelization: unable to inspect saved accounts for {provider.value}: {exc}"
            )
            return [None]

        if selectable_count <= 0:
            Logger.warning(
                f"Full Parallelization: {provider.value} has no saved accounts, so it will use "
                "one normal manual lane."
            )
            return [None]

        effective_count = min(desired_count, selectable_count)
        if effective_count < desired_count:
            Logger.warning(
                f"Full Parallelization: {provider.value} requested {desired_count} instances, "
                f"but only {selectable_count} saved account(s) are available. Launching {effective_count}."
            )

        try:
            pairs = ece_manager.select_parallel_pairs(
                provider,
                desired_count=effective_count,
                least_used=self._select_least_used_enabled(),
                prefer_pinned=True,
            )
        except Exception as exc:
            Logger.warning(
                f"Full Parallelization: failed to select accounts for {provider.value}: {exc}"
            )
            return [None]

        return list(pairs) or [None]

    def _active_emails_for_provider(
        self,
        provider: DriverProvider,
        *,
        excluding_driver: BaseDriver | None = None,
    ) -> set[str]:
        emails: set[str] = set()
        for entry_provider, driver in self._driver_entries:
            if entry_provider != provider or driver is excluding_driver:
                continue
            try:
                pair = driver.ece_active_pair()
            except Exception:
                pair = None
            email = _normalize_email(getattr(pair, "email", None) if pair else None)
            if email:
                emails.add(email)
        return emails

    def _build_driver_entries(self) -> None:
        for provider in self.providers:
            startup_pairs = self._startup_pairs_for_provider(provider)
            for pair in startup_pairs:
                driver = create_driver_for_provider(self.config_manager, provider)
                if pair is not None:
                    configure_identity = getattr(driver, "configure_parallel_ece_identity", None)
                    if callable(configure_identity):
                        configure_identity(
                            pair=pair,
                            disable_profile_slot_rotation=True,
                            die_on_failed_rotation=True,
                            rotation_exclude_emails_callback=(
                                lambda current_provider=provider, current_driver=driver: (
                                    self._active_emails_for_provider(
                                        current_provider,
                                        excluding_driver=current_driver,
                                    )
                                )
                            ),
                        )

                self._driver_entries.append((provider, driver))

    def _rebuild_driver_indexes(self) -> None:
        self.drivers = {}
        self._driver_labels_by_id = {}
        self.providers = []

        counts = Counter(provider for provider, _driver in self._driver_entries)
        seen: dict[DriverProvider, int] = {}
        for provider, driver in self._driver_entries:
            if provider not in self.providers:
                self.providers.append(provider)
            self.drivers.setdefault(provider, driver)
            seen[provider] = seen.get(provider, 0) + 1
            index = seen[provider]
            label = provider.value if counts[provider] <= 1 else f"{provider.value} {index}"
            self._driver_labels_by_id[id(driver)] = label

    @property
    def provider(self) -> DriverProvider:
        return self.current_provider

    @property
    def provider_label(self) -> str:
        return "Providers in Parallel"

    def iter_drivers(self) -> list[tuple[DriverProvider, BaseDriver]]:
        return list(self._driver_entries)

    def get_driver(self, provider: DriverProvider) -> BaseDriver | None:
        return self.drivers.get(provider)

    def get_current_driver(self) -> BaseDriver | None:
        return self.get_driver(self.current_provider) or next(iter(self.drivers.values()), None)

    def _attach_callbacks(self) -> None:
        for provider, driver in self._driver_entries:
            driver.notify_user_callback = self.notify_user_callback
            driver.request_user_text_callback = self.request_user_text_callback
            driver.profile_compatibility_warning_callback = self.profile_compatibility_warning_callback

            async def _handle_provider_crash(current_provider: DriverProvider = provider) -> None:
                await self._handle_driver_crash(current_provider)

            driver.on_crash_callback = _handle_provider_crash

    def _make_driver_status_callback(self, label: str, status_callback=None):
        if status_callback is None:
            return None

        return lambda message, current_label=label: status_callback(
            f"{current_label}: {message}"
        )

    async def _start_driver_entry(
        self,
        provider: DriverProvider,
        driver: BaseDriver,
        *,
        status_callback=None,
    ) -> _StartupResult:
        label = self._driver_labels_by_id.get(id(driver), provider.value)
        try:
            await driver.start(
                status_callback=self._make_driver_status_callback(
                    label,
                    status_callback=status_callback,
                )
            )
            if not bool(getattr(driver, "is_running", False)):
                raise RuntimeError("driver finished startup but did not report as running")
            return _StartupResult(provider=provider, driver=driver, label=label)
        except Exception as exc:
            Logger.warning(
                f"Providers in Parallel: {label} failed to start and will be disabled: {exc}"
            )
            try:
                await driver.close()
            except Exception as close_error:
                Logger.debug(
                    f"Providers in Parallel: cleanup for failed {label} raised: {close_error}"
                )
            return _StartupResult(provider=provider, driver=driver, label=label, error=exc)

    async def _start_entries_sequentially(self, status_callback=None) -> list[_StartupResult]:
        results: list[_StartupResult] = []
        for provider, driver in self._driver_entries:
            results.append(
                await self._start_driver_entry(
                    provider,
                    driver,
                    status_callback=status_callback,
                )
            )
        return results

    async def _start_entries_concurrently(self, status_callback=None) -> list[_StartupResult]:
        entries = list(self._driver_entries)
        if not entries:
            return []

        batch_size = len(entries)
        batching_enabled = is_parallel_launch_batching_enabled(self.config_manager)
        if batching_enabled:
            batch_size = get_parallel_launch_batch_size(self.config_manager)

        total_batches = (len(entries) + batch_size - 1) // batch_size
        results: list[_StartupResult] = []
        for index in range(0, len(entries), batch_size):
            batch = entries[index : index + batch_size]
            batch_number = (index // batch_size) + 1
            labels = [
                self._driver_labels_by_id.get(id(driver), provider.value)
                for provider, driver in batch
            ]

            if batching_enabled:
                labels_text = ", ".join(labels)
                Logger.info(
                    f"Providers in Parallel: launching batch {batch_number}/{total_batches}: "
                    f"{labels_text}"
                )
                if status_callback is not None:
                    status_callback(
                        f"Launching batch {batch_number}/{total_batches}: {labels_text}"
                    )

            batch_results = await asyncio.gather(
                *(
                    self._start_driver_entry(
                        provider,
                        driver,
                        status_callback=status_callback,
                    )
                    for provider, driver in batch
                )
            )
            results.extend(batch_results)

        return results

    @staticmethod
    def _format_startup_failures(failures: list[_StartupResult]) -> str:
        parts: list[str] = []
        for result in failures:
            message = str(result.error or "").strip()
            parts.append(f"{result.label}: {message or 'unknown startup error'}")
        return "; ".join(parts)

    def _apply_startup_results(self, results: list[_StartupResult]) -> tuple[int, int]:
        successful_entries = [
            (result.provider, result.driver)
            for result in results
            if result.succeeded and bool(getattr(result.driver, "is_running", False))
        ]

        self._driver_entries = successful_entries
        self._rebuild_driver_indexes()

        return len(successful_entries), sum(1 for result in results if not result.succeeded)

    async def _handle_driver_crash(self, provider: DriverProvider) -> None:
        if self._crash_notified or (not self.is_running):
            return

        self._crash_notified = True
        Logger.warning(
            f"Providers in Parallel: {provider.value} browser crashed or was closed. Stopping all providers."
        )

        callback = getattr(self, "on_crash_callback", None)
        if not callback:
            return

        if inspect.iscoroutinefunction(callback):
            await callback()
            return

        callback()

    async def start(self, status_callback=None) -> None:
        self.current_provider = get_current_provider(self.config_manager)
        self._crash_notified = False
        self._attach_callbacks()

        providers_text = ", ".join(
            self._driver_labels_by_id.get(id(driver), provider.value)
            for provider, driver in self._driver_entries
        )
        Logger.info(f"Starting Providers in Parallel runtime for: {providers_text}")

        concurrent_launch = is_parallel_concurrent_launch_enabled(self.config_manager)
        if concurrent_launch:
            batch_size = (
                get_parallel_launch_batch_size(self.config_manager)
                if is_parallel_launch_batching_enabled(self.config_manager)
                else len(self._driver_entries)
            )
            Logger.info(
                "Providers in Parallel: concurrent launch enabled "
                f"(max {max(1, batch_size)} lane(s) at a time)."
            )

        if concurrent_launch:
            results = await self._start_entries_concurrently(status_callback=status_callback)
        else:
            results = await self._start_entries_sequentially(status_callback=status_callback)

        started_count, failed_count = self._apply_startup_results(results)
        failures = [result for result in results if not result.succeeded]

        if started_count <= 0:
            self.is_running = False
            detail = self._format_startup_failures(failures)
            message = "Providers in Parallel runtime failed: no provider lanes started."
            if detail:
                message = f"{message} {detail}"
            Logger.error(message)
            raise RuntimeError(message)

        self.is_running = True
        if failed_count:
            detail = self._format_startup_failures(failures)
            Logger.warning(
                "Providers in Parallel runtime started with "
                f"{started_count}/{len(results)} lane(s). Disabled failed lane(s): {detail}"
            )
        else:
            Logger.success("Providers in Parallel runtime started successfully.")

    async def close(self) -> None:
        Logger.info("Closing Providers in Parallel runtime...")
        self.is_running = False
        self._crash_notified = True

        for provider, driver in reversed(self.iter_drivers()):
            try:
                await driver.close()
            except Exception as exc:
                Logger.warning(f"Providers in Parallel: failed to close {provider.value}: {exc}")

        Logger.info("Providers in Parallel runtime closed.")

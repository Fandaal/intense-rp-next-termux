from enum import Enum
from dataclasses import dataclass, field
from typing import List, Any, Optional, Callable, Dict
from .validators import (
    validate_port,
    validate_directory_path,
    validate_ip_address_list,
    validate_email_list,
    validate_float_range,
    validate_integer_range,
)
from .formatting_presets import FORMATTING_PRESET_OPTIONS
from .location import get_config_storage_options
from drivers.providers import provider_options

DOCS_ACCOUNTS = "features/accounts/"
DOCS_AISTUDIO = "providers/aistudio-behavior/"
DOCS_API_BEHAVIOR = "advanced/api-behavior/"
DOCS_CHAT_AUTO_DELETE = "features/chat-auto-deletion/"
DOCS_CONSOLE = "features/console-logging/"
DOCS_DEEPSEEK = "providers/deepseek-behavior/"
DOCS_FORMATTING = "features/formatting/"
DOCS_GLM = "providers/glm-behavior/"
DOCS_GLM_QUIRKS = "advanced/glm-quirks/"
DOCS_HUGGINGCHAT = "providers/huggingchat-behavior/"
DOCS_HOTSWAPS = "features/hotswaps/"
DOCS_IP_WHITELIST = "advanced/ip-whitelist/"
DOCS_LOGIN = "features/login-sessions/"
DOCS_LOADOUTS = "experimental/loadouts/"
DOCS_FULL_PARALLELIZATION = "experimental/full-parallelization/"
DOCS_MOONSHOT = "providers/moonshot-behavior/"
DOCS_MULTI_SLOT_CACHE = "features/multi-slot-cache/"
DOCS_NETWORK = "features/network-api/"
DOCS_PERPLEXITY = "providers/perplexity-behavior/"
DOCS_PROVIDER_SUPPORT = "advanced/provider-support/"
DOCS_QWEN = "providers/qwen-behavior/"
DOCS_PARALLEL_REQUEST_QUEUE = "experimental/parallel-request-queue/"
DOCS_REMOTE_CONTROL = "experimental/remote-control/"
DOCS_PROVIDERS_IN_PARALLEL = "experimental/providers-in-parallel/"
DOCS_SYSTEM = "features/system/"
DOCS_UNIVERSAL_MODEL_NAMES = "features/universal-model-names/"

class SettingType(Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    DIRECTORY = "directory"
    INTEGER = "integer"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    DROPDOWN = "dropdown"
    DIVIDER = "divider"
    DESCRIPTION = "description"
    HINT = "hint"
    BUTTON = "button"
    ROW = "row"
    INPUT_PAIR = "input_pair"
    INPUT_LIST = "input_list"
    MULTI_SELECT_DROPDOWN = "multi_select_dropdown"
    REDIRECT = "redirect"

@dataclass
class AlternativeAction:
    name: str
    action: str
    icon: Optional[str] = None

@dataclass
class SettingField:
    key: str
    label: str
    type: SettingType
    default: Any
    tooltip: Optional[str] = None
    front_tooltip: Optional[str] = None
    validator: Optional[Callable[[Any], None]] = None
    required: bool = False
    nullable: bool = False
    depends: Optional[str] = None
    options: Optional[List[str]] = None # For dropdowns
    transient: bool = False # For UI-only fields (not persisted)
    action: Optional[str] = None # For buttons (function name to call)
    sub_fields: Optional[List["SettingField"]] = None # For ROW type
    ratios: Optional[List[int]] = None # For ROW type (e.g. [70, 30])
    force_when_dep_unmet: Optional[Any] = None
    visible_depends: Optional[str] = None
    affects: Optional[List[str]] = None # UI components to refresh when this field changes
    alternative_actions: Optional[List[AlternativeAction]] = None # For INPUT_PAIR-style fields
    docs_path: Optional[str] = None
    docs_anchor: Optional[str] = None
    hint_variant: Optional[str] = None
    button_height: Optional[str] = None

@dataclass
class SettingCategory:
    name: str
    key: str
    fields: List[SettingField] = field(default_factory=list)


@dataclass(frozen=True)
class SettingCard:
    key: str
    title: str
    field_refs: List[tuple[str, str]] = field(default_factory=list)
    description: Optional[str] = None
    special: Optional[str] = None


@dataclass(frozen=True)
class SettingSection:
    key: str
    label: str
    icon: str
    card_keys: List[str] = field(default_factory=list)

# Define the schema
SCHEMA = [
    SettingCategory(
        name="Providers & Credentials",
        key="providers_credentials",
        fields=[
            SettingField(
                key="provider",
                label="Current Provider",
                type=SettingType.DROPDOWN,
                default="DeepSeek",
                options=provider_options(),
                tooltip=(
                    "Choose which provider web app IntenseRP should drive. "
                    "This takes effect the next time the browser is started."
                ),
                affects=["hotswap_button"],
                docs_path=DOCS_PROVIDER_SUPPORT,
                docs_anchor="how-providers-work-in-v2",
            ),
            SettingField(
                key="auto_login",
                label="Sign In Automatically",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Try to sign in with one of your saved accounts automatically.",
                docs_path=DOCS_LOGIN,
                docs_anchor="auto-login",
            ),
            SettingField(
                key="select_least_used",
                label="Prefer the Least Used Account",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Spread usage across saved accounts instead of picking one at random when nothing is pinned.",
                docs_path=DOCS_ACCOUNTS,
                docs_anchor="how-account-selection-works",
            ),
            SettingField(
                key="reload_on_failure",
                label="Retry With Another Account",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="If a response is empty or rate-limited, try again with another saved account or profile.",
                docs_path=DOCS_ACCOUNTS,
                docs_anchor="reload-on-failure-auto-retry",
            ),
            SettingField(
                key="credential_manager",
                label="Saved Accounts",
                type=SettingType.REDIRECT,
                default="Open Manager",
                tooltip="Add, edit, pin, or remove saved provider accounts for automatic sign-in.",
                action="open_credential_manager",
                docs_path=DOCS_ACCOUNTS,
                docs_anchor="quick-setup",
            )
        ]
    ),
    SettingCategory(
        name="Formatting",
        key="formatting",
        fields=[
            SettingField(
                key="formatting_divider_1",
                label="Formatting Template",
                type=SettingType.DIVIDER,
                default=None
            ),
            SettingField(
                key="formatting_preset",
                label="Message Style",
                type=SettingType.DROPDOWN,
                default="Classic - Name",
                options=FORMATTING_PRESET_OPTIONS,
                tooltip="Start from a built-in style or switch to Custom and write your own.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="presets",
            ),
            SettingField(
                key="formatting_template",
                label="Template",
                type=SettingType.TEXTAREA,
                default="{{name}}: {{content}}",
                tooltip="Define how messages are formatted. Use {{name}}, {{role}}, and {{content}} placeholders.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="templates",
            ),
            SettingField(
                key="reset_formatting_btn",
                label="Reset Message Style",
                type=SettingType.BUTTON,
                default="Reset",
                action="reset_formatting",
                tooltip="Reset formatting template to Classic - Name.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="presets",
            ),
            SettingField(
                key="formatting_divider",
                label="Between Messages",
                type=SettingType.TEXTAREA,
                default="\\n",
                tooltip="String to insert between messages. Default is a newline.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="message-divider",
            ),
            SettingField(
                key="apply_formatting",
                label="Format Messages Before Sending",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Toggle whether to apply the formatting rules.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="disabling-formatting",
            ),
            SettingField(
                key="formatting_divider_2",
                label="Name Behavior",
                type=SettingType.DIVIDER,
                default=None
            ),
            SettingField(
                key="name_behavior_desc",
                label="Description",
                type=SettingType.DESCRIPTION,
                default="Toggle methods for fetching names. If all fail or are disabled, role names are used. Methods run in order.",
                tooltip=None
            ),
            SettingField(
                key="enable_msg_objects",
                label="Read Names from Message Objects",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Scan for 'name' parameter in message objects (or 'irp-next' for RossAscends's STMP patcher compat).",
                docs_path=DOCS_FORMATTING,
                docs_anchor="message-objects",
            ),
            SettingField(
                key="enable_ir2",
                label="Read Names from IR2 Blocks",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Parse [[IR2u]]username[[/IR2u]]-[[IR2a]]charname[[/IR2a]] blocks.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="ir2-blocks",
            ),
            SettingField(
                key="enable_classic_irp",
                label="Read Names from Classic IntenseRP Blocks",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Parse DATA1: \"{{char}}\" DATA2: \"{{user}}\" blocks.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="classic-intenserp",
            ),
            SettingField(
                key="formatting_divider_3",
                label="Injection",
                type=SettingType.DIVIDER,
                default=None
            ),
            SettingField(
                key="injection_desc",
                label="Description",
                type=SettingType.DESCRIPTION,
                default="Insert a small instruction before or after all other messages. Supports {{user}} and {{char}} placeholders.",
                tooltip=None
            ),
            SettingField(
                key="injection_position",
                label="Place Extra Instruction",
                type=SettingType.DROPDOWN,
                default="Before",
                options=["Before", "After"],
                tooltip="Where to place the injected content.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="injection",
            ),
            SettingField(
                key="injection_content",
                label="Extra Instruction",
                type=SettingType.TEXTAREA,
                default="",
                tooltip="Content to inject. Supports {{user}} and {{char}} placeholders.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="injection",
            ),
            SettingField(
                key="reset_injection_btn",
                label="Reset Extra Instruction",
                type=SettingType.BUTTON,
                default="Reset",
                action="reset_injection",
                tooltip="Reset injection settings to default.",
                docs_path=DOCS_FORMATTING,
                docs_anchor="injection",
            ),
        ]
    ),
    SettingCategory(
        name="DeepSeek Behavior",
        key="deepseek_behavior",
        fields=[
            SettingField(
                key="enable_deepthink",
                label="Enable DeepThink",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle the DeepThink button on the DeepSeek interface.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="enable-deepthink",
            ),
            SettingField(
                key="send_deepthink",
                label="Send DeepThink",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include the thinking process in the response sent to the API.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="send-deepthink",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle the Search button on the DeepSeek interface.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="search",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload message as a text file instead of typing it.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=15,
                tooltip="Max seconds to wait for the send button to become enabled after file upload.",
                depends="deepseek_behavior.send_as_text_file",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="first_chunk_timeout",
                label="First Chunk Timeout (s)",
                type=SettingType.INTEGER,
                default=45,
                tooltip="Max seconds to wait for the response stream to start before timing out.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="first-chunk-timeout",
            ),
            SettingField(
                key="anti_censorship",
                label="Anti-Censorship",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Suppress the refusal message when content filtering is triggered.",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="anti-censorship",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt is identical.",
                depends="deepseek_behavior.auto_delete_chats!=true",
                docs_path=DOCS_DEEPSEEK,
                docs_anchor="clean-regeneration",
            ),
            SettingField(
                key="auto_delete_chats",
                label="Delete Chat After Reply",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Delete the provider chat after a successful reply finishes. "
                    "This cannot be used together with Reuse Matching Chat."
                ),
                depends="deepseek_behavior.clean_regeneration!=true",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="auto_delete_chats_warning",
                label="Delete Chat After Reply",
                type=SettingType.HINT,
                default=(
                    "This adds extra cleanup work after each request, so it can slow requests down quite a bit."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="deepseek_behavior.auto_delete_chats",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="multi_slot_cache",
                label="Search Older Matching Chats",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Reuse up to 7 older cached chats for duplicate prompts instead of only the most recent one.",
                depends="deepseek_behavior.clean_regeneration",
                force_when_dep_unmet=False,
                docs_path=DOCS_MULTI_SLOT_CACHE,
                docs_anchor="how-it-works",
            ),
        ]
    ),
    SettingCategory(
        name="GLM Behavior",
        key="glm_behavior",
        fields=[
            SettingField(
                key="model",
                label="Model",
                type=SettingType.DROPDOWN,
                default="GLM-5",
                options=["GLM-5.1", "GLM-5-Turbo", "GLM-5V-Turbo", "GLM-5", "GLM-4.7"],
                tooltip="Select which GLM model to use in the web UI. Not related to the API model IDs.",
                docs_path=DOCS_GLM,
                docs_anchor="modes-model-ids",
            ),
            SettingField(
                key="enable_deepthink",
                label="Enable Deep Think",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle the Deep Think button on the GLM interface.",
                docs_path=DOCS_GLM,
                docs_anchor="enable-deep-think",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Deep Think",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include the thinking process in the response sent to the API.",
                docs_path=DOCS_GLM,
                docs_anchor="send-deep-think",
            ),
            SettingField(
                key="count_tokens",
                label="Count Tokens",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip=(
                    "Include a token count in the response metadata for each message."
                ),
                docs_path=DOCS_GLM,
                docs_anchor="count-tokens",
            ),
            SettingField(
                key="search_forced_off_note",
                label="Search",
                type=SettingType.HINT,
                default=(
                    "GLM Search results are not forwarded to the client for stability reasons. "
                    "You may still see citations in the response."
                ),
                tooltip=None,
                hint_variant="info",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Toggle the Search button on the GLM interface. "
                    "Search results are not forwarded to the client."
                ),
                docs_path=DOCS_GLM,
                docs_anchor="search",
            ),
            SettingField(
                key="enable_advanced_search",
                label="Enable Advanced Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Toggle GLM's Advanced Search mode. Requires Deep Think and Search; "
                    "search results are not forwarded to the client."
                ),
                depends="glm_behavior.enable_deepthink&&glm_behavior.enable_search",
                force_when_dep_unmet=False,
                docs_path=DOCS_GLM,
                docs_anchor="advanced-search",
            ),
            SettingField(
                key="enable_tools",
                label="Enable Tools",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Toggle the Tools button on the GLM interface. "
                    "Very heavily recommended to leave this off: GLM's Tools UI is unstable, "
                    "IntenseRP does not support those tools yet, and this only works on GLM-5V-Turbo."
                ),
                front_tooltip="Experimental GLM-5V-Turbo-only Tools toggle. Best left off unless needed.",
                depends="glm_behavior.model==GLM-5V-Turbo",
                force_when_dep_unmet=False,
                docs_path=DOCS_GLM,
                docs_anchor="tools",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload message as a text file instead of typing it.",
                docs_path=DOCS_GLM,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=15,
                tooltip="Max seconds to wait for the send button to become enabled after file upload.",
                depends="glm_behavior.send_as_text_file",
                docs_path=DOCS_GLM,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="text_file_filler",
                label="Text File Filler",
                type=SettingType.TEXTAREA,
                default=".",
                tooltip="Text sent alongside the uploaded file. Required because GLM won't send a file-only message.",
                depends="glm_behavior.send_as_text_file",
                docs_path=DOCS_GLM,
                docs_anchor="text-file-filler",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt is identical.",
                depends="glm_behavior.repetition_buster!=true&&glm_behavior.auto_delete_chats!=true",
                docs_path=DOCS_GLM,
                docs_anchor="clean-regeneration-known-issues",
            ),
            SettingField(
                key="auto_delete_chats",
                label="Delete Chat After Reply",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Delete the provider chat after a successful reply finishes. "
                    "This cannot be used together with Reuse Matching Chat."
                ),
                depends="glm_behavior.clean_regeneration!=true",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="auto_delete_chats_warning",
                label="Delete Chat After Reply",
                type=SettingType.HINT,
                default=(
                    "This adds extra cleanup work after each request, so it can slow requests down quite a bit."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="glm_behavior.auto_delete_chats",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="repetition_buster",
                label="Repetition Buster",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "The opposite of Reuse Matching Chat. "
                    "On duplicate prompts, send a throwaway random cache-buster prompt first, "
                    "then open another fresh chat for the real request."
                ),
                depends="glm_behavior.clean_regeneration!=true",
                docs_path=DOCS_GLM,
                docs_anchor="repetition-buster",
            ),
            SettingField(
                key="multi_slot_cache",
                label="Search Older Matching Chats",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Reuse up to 7 older cached chats for duplicate prompts instead of only the most recent one.",
                depends="glm_behavior.clean_regeneration",
                force_when_dep_unmet=False,
                docs_path=DOCS_MULTI_SLOT_CACHE,
                docs_anchor="how-it-works",
            ),
            SettingField(
                key="quirks_divider",
                label="Quirks",
                type=SettingType.DIVIDER,
                default=None
            ),
            SettingField(
                key="quirks_desc",
                label="Description",
                type=SettingType.DESCRIPTION,
                default="Timing and interaction tweaks for slower machines or flaky UI behavior.",
                tooltip=None
            ),
            SettingField(
                key="ui_click_timeout",
                label="UI Click Timeout (ms)",
                type=SettingType.INTEGER,
                default=3000,
                tooltip="Timeout in milliseconds for UI element clicks (buttons, dropdowns, etc.).",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="ui-click-timeout",
            ),
            SettingField(
                key="post_action_delay",
                label="Post-Action Delay (ms)",
                type=SettingType.INTEGER,
                default=500,
                tooltip="Delay in milliseconds after UI actions (new chat, model switch) to let the interface settle.",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="post-action-delay",
            ),
            SettingField(
                key="message_send_timeout",
                label="Message Send Timeout (s)",
                type=SettingType.INTEGER,
                default=5,
                tooltip="Max seconds to wait for the send button to become enabled after text entry (non-file mode).",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="message-send-timeout",
            ),
            SettingField(
                key="completion_request_timeout",
                label="Completion Request Timeout (s)",
                type=SettingType.INTEGER,
                default=150,
                tooltip="Max seconds to wait after clicking Send or Regenerate for GLM's completion request to appear.",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="completion-request-timeout",
            ),
            SettingField(
                key="first_chunk_timeout",
                label="First Chunk Timeout (s)",
                type=SettingType.INTEGER,
                default=45,
                tooltip="Max seconds to wait for the response stream to start before timing out.",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="first-chunk-timeout",
            ),
            SettingField(
                key="refresh_after_generation",
                label="Refresh After Generation",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Refresh the page after a response finishes. Can help restore UI state and improve Clean Regeneration.",
                docs_path=DOCS_GLM_QUIRKS,
                docs_anchor="refresh-after-generation",
            ),
        ]
    ),
    SettingCategory(
        name="Moonshot Behavior",
        key="moonshot_behavior",
        fields=[
            SettingField(
                key="enable_deepthink",
                label="Enable Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Switch Kimi between K2.6 Instant and K2.6 Thinking before sending.",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="enable-thinking",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include Kimi's thinking content in the response sent to the API.",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="send-thinking",
            ),
            SettingField(
                key="search_and_think_note",
                label="Search + Thinking",
                type=SettingType.HINT,
                default=(
                    "Kimi can emit multi-stage reasoning when Search and Thinking are both enabled. "
                    "Some clients (including SillyTavern) may not parse this cleanly, avoid using both at the same time if you see weird formatting or missing content in the responses."
                ),
                tooltip=None,
                hint_variant="warn",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle Kimi's internet search tool in the web UI.",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="search",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload message as a text file instead of typing it.",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=15,
                tooltip="Max seconds to wait for the send button to become enabled after file upload.",
                depends="moonshot_behavior.send_as_text_file",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="text_file_filler",
                label="Text File Filler",
                type=SettingType.TEXTAREA,
                default=".",
                tooltip="Text sent alongside the uploaded file. Required because Kimi won't send a file-only message.",
                depends="moonshot_behavior.send_as_text_file",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="text-file-filler",
            ),
            SettingField(
                key="anti_censorship",
                label="Anti-Censorship",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Suppress refusal-like messages in the stream when a content-filter-style event is detected.",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="anti-censorship",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt is identical.",
                depends="moonshot_behavior.auto_delete_chats!=true",
                docs_path=DOCS_MOONSHOT,
                docs_anchor="clean-regeneration",
            ),
            SettingField(
                key="auto_delete_chats",
                label="Delete Chat After Reply",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Delete the provider chat after a successful reply finishes. "
                    "This cannot be used together with Reuse Matching Chat."
                ),
                depends="moonshot_behavior.clean_regeneration!=true",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="auto_delete_chats_warning",
                label="Delete Chat After Reply",
                type=SettingType.HINT,
                default=(
                    "This adds extra cleanup work after each request, so it can slow requests down quite a bit."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="moonshot_behavior.auto_delete_chats",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="multi_slot_cache",
                label="Search Older Matching Chats",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Reuse up to 7 older cached chats for duplicate prompts instead of only the most recent one.",
                depends="moonshot_behavior.clean_regeneration",
                force_when_dep_unmet=False,
                docs_path=DOCS_MULTI_SLOT_CACHE,
                docs_anchor="how-it-works",
            ),
        ],
    ),
    SettingCategory(
        name="QwenLM Behavior",
        key="qwen_behavior",
        fields=[
            SettingField(
                key="model",
                label="Model",
                type=SettingType.DROPDOWN,
                default="Qwen3.5-Plus",
                options=[
                    "Qwen3.6-Plus",
                    "Qwen3.7-Max",
                    "Qwen3.6-Max-Preview",
                    "Qwen3.6-27B",
                    "Qwen3.7-Max-Preview",
                    "Qwen3.7-Plus-Preview",
                    "Qwen3.5-Plus",
                    "Qwen3.5-Omni-Plus",
                    "Qwen3.6-35B-A3B",
                    "Qwen3.5-Flash",
                    "Qwen3.5-Max-Preview",
                    "Qwen3.6-Plus-Preview",
                    "Qwen3.5-397B-A17B",
                    "Qwen3.5-122B-A10B",
                    "Qwen3.5-Omni-Flash",
                    "Qwen3.5-27B",
                    "Qwen3.5-35B-A3B",
                    "Qwen3-Max",
                    "Qwen3-235B-A22B-2507",
                    "Qwen3-Coder",
                    "Qwen3-VL-235B-A22B",
                    "Qwen3-Omni-Flash",
                    "Qwen2.5-Max",
                ],
                tooltip="Select which Qwen model to use in the web UI. Not related to the API model IDs.",
                docs_path=DOCS_QWEN,
                docs_anchor="real-qwen-model-selection-web-ui",
            ),
            SettingField(
                key="enable_deepthink",
                label="Enable Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Switch QwenLM into Thinking mode before sending.",
                docs_path=DOCS_QWEN,
                docs_anchor="enable-thinking",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include QwenLM thinking summaries in the response sent to the API.",
                docs_path=DOCS_QWEN,
                docs_anchor="send-thinking",
            ),
            SettingField(
                key="count_tokens",
                label="Count Tokens",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Include a token count in the response metadata for each message.",
                docs_path=DOCS_QWEN,
                docs_anchor="count-tokens",
            ),
            SettingField(
                key="search_forced_off_note",
                label="Search",
                type=SettingType.HINT,
                default=(
                    "QwenLM Search results are not forwarded to the client for stability reasons. "
                    "You may still see citations in the response."
                ),
                tooltip=None,
                hint_variant="info",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle QwenLM Web search in the web UI. Search results are not forwarded to the client.",
                docs_path=DOCS_QWEN,
                docs_anchor="search",
            ),
            SettingField(
                key="enable_tools",
                label="Enable Tools",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Toggle QwenLM's Tools switch in the + menu when available. "
                    "Experimental; leave this off unless you are intentionally testing it."
                ),
                front_tooltip="Experimental QwenLM Tools toggle. Best left off unless needed.",
                docs_path=DOCS_QWEN,
                docs_anchor="tools",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload message as a text file instead of typing it.",
                docs_path=DOCS_QWEN,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="text_file_message",
                label="Text File Message",
                type=SettingType.TEXTAREA,
                default="",
                tooltip="Optional text pasted alongside the uploaded file. Leave empty to send file-only.",
                depends="qwen_behavior.send_as_text_file",
                docs_path=DOCS_QWEN,
                docs_anchor="text-file-message",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=20,
                tooltip="Max seconds to wait for the send button to become available after file upload.",
                depends="qwen_behavior.send_as_text_file",
                docs_path=DOCS_QWEN,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="message_send_timeout",
                label="Message Send Timeout (s)",
                type=SettingType.INTEGER,
                default=8,
                tooltip="Max seconds to wait for the send button to appear after text entry (non-file mode).",
                docs_path=DOCS_QWEN,
                docs_anchor="message-send-timeout",
            ),
            SettingField(
                key="completion_request_timeout",
                label="Completion Request Timeout (s)",
                type=SettingType.INTEGER,
                default=150,
                tooltip="Max seconds to wait after clicking Send or Regenerate for QwenLM's completion request to appear.",
                docs_path=DOCS_QWEN,
                docs_anchor="completion-request-timeout",
            ),
            SettingField(
                key="first_chunk_timeout",
                label="First Chunk Timeout (s)",
                type=SettingType.INTEGER,
                default=150,
                tooltip="Max seconds to wait for QwenLM's response stream to start before timing out.",
                docs_path=DOCS_QWEN,
                docs_anchor="first-chunk-timeout",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt is identical.",
                depends="qwen_behavior.auto_delete_chats!=true",
                docs_path=DOCS_QWEN,
                docs_anchor="clean-regeneration",
            ),
            SettingField(
                key="auto_delete_chats",
                label="Delete Chat After Reply",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Delete the provider chat after a successful reply finishes. "
                    "This cannot be used together with Reuse Matching Chat."
                ),
                depends="qwen_behavior.clean_regeneration!=true",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="auto_delete_chats_warning",
                label="Delete Chat After Reply",
                type=SettingType.HINT,
                default=(
                    "This adds extra cleanup work after each request, so it can slow requests down quite a bit."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="qwen_behavior.auto_delete_chats",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="multi_slot_cache",
                label="Search Older Matching Chats",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Reuse up to 7 older cached chats for duplicate prompts instead of only the most recent one.",
                depends="qwen_behavior.clean_regeneration",
                force_when_dep_unmet=False,
                docs_path=DOCS_MULTI_SLOT_CACHE,
                docs_anchor="how-it-works",
            ),
        ],
    ),
    SettingCategory(
        name="Perplexity Behavior",
        key="perplexity_behavior",
        fields=[
            SettingField(
                key="model",
                label="Model",
                type=SettingType.DROPDOWN,
                default="Best (Auto)",
                options=[
                    "Best (Auto)",
                    "Sonar 2",
                    "GPT-5.4",
                    "GPT-5.5",
                    "Gemini 3.1 Pro",
                    "Claude Sonnet 4.6",
                    "Claude Opus 4.7",
                    "Kimi K2.6",
                    "Nemotron 3 Super",
                ],
                tooltip="Select which Perplexity model to use in the web UI. Requires a Pro or Max account.",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="real-perplexity-model-selection-web-ui",
            ),
            SettingField(
                key="subscription_note",
                label="Model Selection",
                type=SettingType.HINT,
                default=(
                    "Perplexity only exposes model and Thinking controls on paid accounts. "
                    "Free accounts can still send prompts, but IntenseRP will skip those toggles."
                ),
                tooltip=None,
                hint_variant="info",
            ),
            SettingField(
                key="use_spaces",
                label="Use Perplexity Spaces",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Use an IntenseRP-managed Perplexity Space instead of the normal "
                    "chat page. This is experimental, but usually handles custom "
                    "instructions better."
                ),
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="spaces-mode",
            ),
            SettingField(
                key="paste_system_instructions_into_space",
                label="Paste System Instructions Into Space Instructions",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Move leading system messages into the Space instructions field "
                    "when Spaces mode is enabled. Perplexity limits that field to "
                    "8000 characters; anything beyond the limit stays in the prompt."
                ),
                depends="perplexity_behavior.use_spaces",
                visible_depends="perplexity_behavior.use_spaces",
                force_when_dep_unmet=False,
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="space-instructions",
            ),
            SettingField(
                key="enable_deepthink",
                label="Enable Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle Perplexity Thinking for models/accounts that expose it.",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="enable-thinking",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Reserved for API mode consistency. Perplexity does not currently expose "
                    "thinking traces in the intercepted stream, so no <think> content is forwarded."
                ),
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="send-thinking",
            ),
            SettingField(
                key="search_forced_off_note",
                label="Search",
                type=SettingType.HINT,
                default=(
                    "Perplexity search/source payloads are not forwarded to the client for stability. "
                    "Only the assistant answer text is streamed."
                ),
                tooltip=None,
                hint_variant="info",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle Perplexity Web search in the web UI.",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="search",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload message as a text file instead of pasting it into Perplexity.",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="text_file_message",
                label="Text File Message",
                type=SettingType.TEXTAREA,
                default="",
                tooltip="Optional text pasted alongside the uploaded file. Leave empty to send file-only.",
                depends="perplexity_behavior.send_as_text_file",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="text-file-message",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=20,
                tooltip="Max seconds to wait for the send button to become available after file upload.",
                depends="perplexity_behavior.send_as_text_file",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="message_send_timeout",
                label="Message Send Timeout (s)",
                type=SettingType.INTEGER,
                default=8,
                tooltip="Max seconds to wait for the send button to appear after text entry.",
                docs_path=DOCS_PERPLEXITY,
                docs_anchor="message-send-timeout",
            ),
        ],
    ),
    SettingCategory(
        name="HuggingChat Behavior",
        key="huggingchat_behavior",
        fields=[
            SettingField(
                key="model",
                label="Model",
                type=SettingType.DROPDOWN,
                default="Current HuggingChat selection",
                options=[
                    "Current HuggingChat selection",
                    "Model list unavailable, please successfully log into HuggingChat at least once",
                ],
                tooltip=(
                    "Select which HuggingChat model to use in the web UI. "
                    "The live model list is cached after a successful HuggingChat login."
                ),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="real-huggingchat-model-selection-web-ui",
            ),
            SettingField(
                key="inference_provider",
                label="Inference Provider",
                type=SettingType.STRING,
                default="auto",
                tooltip=(
                    "Optional HuggingChat provider value, such as auto, together, fireworks-ai, etc. "
                    "If HuggingChat does not expose the selector for a model, IntenseRP skips it."
                ),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="inference-provider",
            ),
            SettingField(
                key="subscription_note",
                label="Monthly Credits",
                type=SettingType.HINT,
                default=(
                    "HuggingChat has small monthly model credits: free accounts get $0.1/month "
                    "and Pro accounts get $2/month. Disable spent accounts in Credential Manager "
                    "until they reset."
                ),
                tooltip=None,
                hint_variant="warn",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="limits-and-account-rotation",
            ),
            SettingField(
                key="auto_disable_ratelimited_accounts",
                label="Auto-Disable Rate-Limited Accounts",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "When HuggingChat shows Upgrade Required, disable the current saved account "
                    "so account rotation can skip it until you re-enable it."
                ),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="limits-and-account-rotation",
            ),
            SettingField(
                key="enable_deepthink",
                label="Enable Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Use HuggingChat's thinking effort selector on models that expose it.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="thinking-effort",
            ),
            SettingField(
                key="thinking_effort",
                label="Thinking Effort",
                type=SettingType.DROPDOWN,
                default="auto",
                options=["auto", "default", "low", "medium", "high"],
                tooltip="Thinking effort to select when Thinking is enabled and the model exposes the control.",
                depends="huggingchat_behavior.enable_deepthink",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="thinking-effort",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Forward <think>...</think> text from HuggingChat streams to the API client.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="send-thinking",
            ),
            SettingField(
                key="search_forced_off_note",
                label="Search",
                type=SettingType.HINT,
                default=(
                    "HuggingChat search/tool payloads are not forwarded to the client for stability. "
                    "Only the final assistant text is streamed."
                ),
                tooltip=None,
                hint_variant="info",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="search",
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Enable HuggingChat's Exa MCP web search before sending.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="search",
            ),
            SettingField(
                key="use_system_prompt_field",
                label="Use System Prompt Field",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Move configured and leading system messages into HuggingChat's custom "
                    "system prompt field instead of the main chat prompt."
                ),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="system-prompt-field",
            ),
            SettingField(
                key="paste_leading_system_messages",
                label="Paste Leading System Messages",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Move leading API system messages into the HuggingChat custom system prompt field.",
                depends="huggingchat_behavior.use_system_prompt_field",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="system-prompt-field",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Upload the prompt as a text file instead of typing it into HuggingChat.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="text_file_message",
                label="Text File Message",
                type=SettingType.TEXTAREA,
                default="Please read the attached file and respond to it.",
                tooltip="Text pasted alongside the uploaded file. HuggingChat requires text with file uploads.",
                depends="huggingchat_behavior.send_as_text_file",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="text-file-message",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=20,
                tooltip="Max seconds to wait for the send button to become available after file upload.",
                depends="huggingchat_behavior.send_as_text_file",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="file_upload_settle_delay",
                label="File Upload Settle Delay (s)",
                type=SettingType.STRING,
                default="3.0",
                tooltip=(
                    "Seconds to wait after HuggingChat accepts the file before pasting "
                    "the companion message."
                ),
                depends="huggingchat_behavior.send_as_text_file",
                validator=validate_float_range(0.0, 30.0, label="File upload settle delay"),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="file-upload-settle-delay",
            ),
            SettingField(
                key="message_send_timeout",
                label="Message Send Timeout (s)",
                type=SettingType.INTEGER,
                default=8,
                tooltip="Max seconds to wait for the send button to appear after text entry.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="message-send-timeout",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt and settings match.",
                depends="huggingchat_behavior.auto_delete_chats!=true",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="clean-regeneration",
            ),
            SettingField(
                key="auto_delete_chats",
                label="Delete Chat After Reply",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Delete the provider chat after a successful reply finishes. "
                    "This cannot be used together with Reuse Matching Chat."
                ),
                depends="huggingchat_behavior.clean_regeneration!=true",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="auto_delete_chats_warning",
                label="Delete Chat After Reply",
                type=SettingType.HINT,
                default=(
                    "This adds extra cleanup work after each request, so it can slow requests down quite a bit."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="huggingchat_behavior.auto_delete_chats",
                docs_path=DOCS_CHAT_AUTO_DELETE,
                docs_anchor="delete-chat-after-reply",
            ),
            SettingField(
                key="multi_slot_cache",
                label="Search Older Matching Chats",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Reuse up to 7 older cached chats for duplicate prompts instead of only the most recent one.",
                depends="huggingchat_behavior.clean_regeneration",
                force_when_dep_unmet=False,
                docs_path=DOCS_MULTI_SLOT_CACHE,
                docs_anchor="how-it-works",
            ),
            SettingField(
                key="completion_request_timeout",
                label="Completion Request Timeout (s)",
                type=SettingType.INTEGER,
                default=150,
                tooltip="Max seconds to wait after clicking Send or Regenerate for HuggingChat's conversation request.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="quirks",
            ),
            SettingField(
                key="first_chunk_timeout",
                label="First Chunk Timeout (s)",
                type=SettingType.INTEGER,
                default=150,
                tooltip="Max seconds to wait for HuggingChat's response stream to produce answer text.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="quirks",
            ),
            SettingField(
                key="model_apply_timeout",
                label="Model Apply Timeout (s)",
                type=SettingType.INTEGER,
                default=20,
                tooltip="Max seconds to wait while applying HuggingChat model settings.",
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="quirks",
            ),
            SettingField(
                key="post_action_delay",
                label="Post-Action Delay (s)",
                type=SettingType.STRING,
                default="0.35",
                tooltip="Small pause after HuggingChat UI actions so its menus and toggles can settle.",
                validator=validate_float_range(0.0, 5.0, label="Post-action delay"),
                docs_path=DOCS_HUGGINGCHAT,
                docs_anchor="quirks",
            ),
        ],
    ),
    SettingCategory(
        name="Google AI Studio Behavior",
        key="aistudio_behavior",
        fields=[
            SettingField(
                key="model_divider",
                label="Model & Thinking",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="provider_lock_warning",
                label="AI Studio is temporarily locked",
                type=SettingType.HINT,
                default=(
                    "AI Studio currently detects Patchright/automated browsers and blocks "
                    "automated message sends. You can still configure these settings, but "
                    "IntenseRP will not launch or route to AI Studio unless Advanced -> "
                    "Provider Stability -> Ignore Provider Locks is enabled."
                ),
                tooltip=None,
                hint_variant="warn",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="temporary-provider-lock",
            ),
            SettingField(
                key="model",
                label="Model",
                type=SettingType.DROPDOWN,
                default="Gemini 3.1 Pro",
                options=[
                    "Gemini 3.5 Flash",
                    "Gemini 3.1 Pro",
                    "Gemini 3.1 Flash Lite",
                    "Gemini 3 Flash",
                    "Gemini 2.5 Pro",
                    "Gemini 2.5 Flash",
                    "Gemini 2.5 Flash Lite",
                    "Gemma 4 26B-A4B",
                    "Gemma 4 31B",
                ],
                tooltip="Select which model to use in the Google AI Studio web UI.",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="real-ai-studio-model-selection-web-ui",
            ),
            SettingField(
                key="enable_deepthink",
                label="Enable Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Use the configured Thinking Level on supported AI Studio models. "
                    "When disabled, IntenseRP falls back to the lowest available level instead."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="enable-thinking",
            ),
            SettingField(
                key="thinking_level",
                label="Thinking Level",
                type=SettingType.DROPDOWN,
                default="Medium",
                options=["Minimal", "Low", "Medium", "High"],
                tooltip=(
                    "Thinking level for supported AI Studio models. "
                    "Gemini 2.5 Flash, Flash Lite, and Pro map this to the thinking budget."
                ),
                depends="aistudio_behavior.enable_deepthink",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="thinking-level",
            ),
            SettingField(
                key="send_deepthink",
                label="Send Thinking",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include AI Studio thinking summaries in the response sent to the API.",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="send-thinking",
            ),
            SettingField(
                key="tools_divider",
                label="Tools & Uploads",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="enable_search",
                label="Enable Search",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle Google Search grounding in the AI Studio web UI.",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="enable-search",
            ),
            SettingField(
                key="enable_url_context",
                label="Enable URL Context",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Toggle AI Studio's URL Context browsing mode in the web UI.",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="enable-url-context",
            ),
            SettingField(
                key="use_system_prompt_field",
                label="Use System Prompt Field",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Move leading system messages into AI Studio's System Instructions UI instead "
                    "of sending them in the main chat prompt."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="system-prompt-field",
            ),
            SettingField(
                key="send_as_text_file",
                label="Send As Text File",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Upload the prompt as a text file through AI Studio's media picker instead of "
                    "typing the whole message into the textarea."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="file-upload-mode",
            ),
            SettingField(
                key="text_file_message",
                label="Text File Message",
                type=SettingType.TEXTAREA,
                default="",
                tooltip=(
                    "Optional text to send alongside the uploaded prompt file. Leave empty to try "
                    "file-only requests."
                ),
                depends="aistudio_behavior.send_as_text_file",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="text-file-message",
            ),
            SettingField(
                key="file_upload_timeout",
                label="File Upload Timeout",
                type=SettingType.INTEGER,
                default=20,
                tooltip=(
                    "Max seconds to wait for the send button to become available after selecting "
                    "a prompt file."
                ),
                depends="aistudio_behavior.send_as_text_file",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="file-upload-timeout",
            ),
            SettingField(
                key="anti_censorship",
                label="Anti-Censorship",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Detect AI Studio hard-censorship, replace the blocked assistant turn, "
                    "and send up to 3 continue nudges automatically."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="anti-censorship",
            ),
            SettingField(
                key="caars_enabled",
                label="CAARS",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Run a cheap savior model first, replace its assistant turn, "
                    "then switch back and continue with the real model."
                ),
                depends="aistudio_behavior.anti_censorship",
                visible_depends="aistudio_behavior.anti_censorship",
                force_when_dep_unmet=False,
                docs_path=DOCS_AISTUDIO,
                docs_anchor="caars",
            ),
            SettingField(
                key="caars_savior_model",
                label="Savior Model",
                type=SettingType.DROPDOWN,
                default="Gemini 3.1 Flash Lite",
                options=[
                    "Gemini 3.5 Flash",
                    "Gemini 3.1 Pro",
                    "Gemini 3.1 Flash Lite",
                    "Gemini 3 Flash",
                    "Gemini 2.5 Pro",
                    "Gemini 2.5 Flash",
                    "Gemini 2.5 Flash Lite",
                    "Gemma 4 26B-A4B",
                    "Gemma 4 31B",
                ],
                tooltip="Cheap/secondary AI Studio model used for the CAARS prelude.",
                depends="aistudio_behavior.anti_censorship&&aistudio_behavior.caars_enabled",
                visible_depends="aistudio_behavior.anti_censorship&&aistudio_behavior.caars_enabled",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="savior-model",
            ),
            SettingField(
                key="anti_censorship_replacement_message",
                label="Replacement Message",
                type=SettingType.TEXTAREA,
                default=".",
                tooltip="Text used to replace the blocked assistant message before retrying.",
                depends="aistudio_behavior.anti_censorship",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="replacement-message",
            ),
            SettingField(
                key="anti_censorship_continue_nudge",
                label="Continue Nudge",
                type=SettingType.TEXTAREA,
                default="Continue.",
                tooltip="Text sent as the follow-up user message after a blocked AI Studio turn.",
                depends="aistudio_behavior.anti_censorship",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="continue-nudge",
            ),
            SettingField(
                key="sampling_divider",
                label="Sampling",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="temperature",
                label="Temperature",
                type=SettingType.STRING,
                default="1.0",
                tooltip=(
                    "Default temperature for AI Studio requests when the selected model exposes it. "
                    "Request-level overrides still win."
                ),
                validator=validate_float_range(0.0, 2.0, label="Temperature"),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="temperature",
            ),
            SettingField(
                key="top_p",
                label="Top P",
                type=SettingType.STRING,
                default="0.95",
                tooltip=(
                    "Default top-p value for AI Studio requests when the selected model exposes it. "
                    "Request-level overrides still win."
                ),
                validator=validate_float_range(0.0, 1.0, label="Top P"),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="top-p",
            ),
            SettingField(
                key="max_output_tokens",
                label="Max Output Tokens",
                type=SettingType.INTEGER,
                default=65536,
                tooltip=(
                    "Default output token budget for AI Studio requests. "
                    "This maps to the web UI's maxOutputTokens control; model-specific caps still apply."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="max-output-tokens",
            ),
            SettingField(
                key="automation_divider",
                label="Automation",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="auto_login_redirect_timeout",
                label="Auto Login Redirect Timeout (s)",
                type=SettingType.INTEGER,
                default=15,
                tooltip=(
                    "How long to wait for Google to return to AI Studio after auto-filling "
                    "credentials before falling back to manual completion."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="auto-login-redirect-timeout",
            ),
            SettingField(
                key="assume_english_ui",
                label="Assume English UI",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Ignore AI Studio's <html lang> value and treat "
                    "the visible UI as English. Only enable this when you are absolutely "
                    "sure the AI Studio page itself is in English."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="assume-english-ui",
            ),
            SettingField(
                key="assume_english_ui_warning",
                label="This is a last-resort override!",
                type=SettingType.HINT,
                default=(
                    "Only use this when the visible AI Studio page is actually English. "
                    "It skips the <html lang> safety check, so a genuinely non-English UI "
                    "can still break automation."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="aistudio_behavior.assume_english_ui",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="assume-english-ui",
            ),
            SettingField(
                key="assume_paid_model_access",
                label="Assume Paid Model Access",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Allow Gemini 2.5 models in Google AI Studio. Only enable this when you are "
                    "absolutely sure the active AI Studio account has paid model access."
                ),
                docs_path=DOCS_AISTUDIO,
                docs_anchor="assume-paid-model-access",
            ),
            SettingField(
                key="assume_paid_model_access_warning",
                label="Only for accounts you know can use Gemini 2.5",
                type=SettingType.HINT,
                default=(
                    "This does not buy access or bypass AI Studio account limits. If the email list "
                    "below is empty, IntenseRP assumes every AI Studio account has access. If you add "
                    "emails, only those accounts are treated as paid-access accounts."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="aistudio_behavior.assume_paid_model_access",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="assume-paid-model-access",
            ),
            SettingField(
                key="paid_model_access_emails",
                label="Paid Model Access Emails",
                type=SettingType.INPUT_LIST,
                default=[],
                tooltip=(
                    "Optional list of Google account emails that can use paid Gemini 2.5 models "
                    "in AI Studio. Leave empty to assume all AI Studio accounts have access."
                ),
                validator=validate_email_list,
                depends="aistudio_behavior.assume_paid_model_access",
                visible_depends="aistudio_behavior.assume_paid_model_access",
                docs_path=DOCS_AISTUDIO,
                docs_anchor="assume-paid-model-access",
            ),
            SettingField(
                key="clean_regeneration",
                label="Reuse Matching Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Regenerate the last message instead of creating a new chat when the prompt is identical.",
                depends="aistudio_behavior.preflight_next_chat!=true",
                force_when_dep_unmet=False,
                docs_path=DOCS_AISTUDIO,
                docs_anchor="clean-regeneration",
            ),
            SettingField(
                key="preflight_next_chat",
                label="Preflight Next Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "After a successful AI Studio response, prepare a fresh blank chat with "
                    "the same controls so the next prompt can send a little faster."
                ),
                depends="aistudio_behavior.clean_regeneration!=true",
                force_when_dep_unmet=False,
                docs_path=DOCS_AISTUDIO,
                docs_anchor="preflight-next-chat",
            ),
        ],
    ),
    SettingCategory(
        name="Diagnostics",
        key="diagnostics",
        fields=[
            SettingField(
                key="bug_reports_warning",
                label="Bug Reports",
                type=SettingType.HINT,
                default=(
                    "These diagnostics can include sensitive data, including prompt text and redacted "
                    "account/session details. Only share a bug-report bundle if you are comfortable with that."
                ),
                tooltip=None,
                hint_variant="warn",
            ),
            SettingField(
                key="keep_internal_log",
                label="Keep an Internal Log",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Write a private diagnostics log in the config directory, even if the console and public "
                    "log files are disabled."
                ),
                docs_path=DOCS_CONSOLE,
                docs_anchor="file-logging",
            ),
            SettingField(
                key="save_last_prompt",
                label="Also Save the Last Prompt",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Keep the latest provider-ready prompt per provider for bug-report bundles. "
                    "Google AI Studio also stores the separate system prompt field when used."
                ),
                docs_path=DOCS_CONSOLE,
                docs_anchor="file-logging",
            ),
        ],
    ),
    SettingCategory(
        name="Logfiles",
        key="logfiles",
        fields=[
            SettingField(
                key="enable_logfiles",
                label="Log to Files",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Save logs to rotating files on disk.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="file-logging",
            ),
            SettingField(
                key="log_dir",
                label="Folder",
                type=SettingType.DIRECTORY,
                default="logs",
                tooltip="Directory to store log files.",
                validator=validate_directory_path,
                nullable=True,
                docs_path=DOCS_CONSOLE,
                docs_anchor="configuration",
            ),
            SettingField(
                key="max_files",
                label="Files to Keep",
                type=SettingType.INTEGER,
                default=5,
                tooltip="Maximum number of log files to keep (before rotation). 0 for unlimited.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="configuration",
            ),
            SettingField(
                key="max_file_size",
                label="Max File Size",
                type=SettingType.ROW,
                default=None,
                ratios=[70, 30],
                docs_path=DOCS_CONSOLE,
                docs_anchor="configuration",
                sub_fields=[
                     SettingField(
                        key="size_val",
                        label="Size Value",
                        type=SettingType.INTEGER,
                        default=10,
                        tooltip="Max file size value. 0 for unlimited."
                    ),
                    SettingField(
                        key="size_unit",
                        label="Unit",
                        type=SettingType.DROPDOWN,
                        default="MB",
                        options=["KB", "MB", "GB"],
                        tooltip="Unit for max file size."
                    ),
                ]
            ),
        ]
    ),
    SettingCategory(
        name="System Settings",
        key="system_settings",
        fields=[
            SettingField(
                key="persistent_sessions",
                label="Keep Provider Sessions Signed In",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Reuse a persistent Playwright browser profile so logins persist between restarts.",
                docs_path=DOCS_SYSTEM,
                docs_anchor="persistent-sessions",
            ),
            SettingField(
                key="profile_compatibility_warnings",
                label="Profile Compatibility Warnings",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip=(
                    "Warn after login failures when a saved browser profile was created "
                    "with a different Chromium/Chrome for Testing major version."
                ),
                docs_path=DOCS_SYSTEM,
                docs_anchor="profile-compatibility-warnings",
            ),
            SettingField(
                key="browser_locale",
                label="Preferred Browser Locale",
                type=SettingType.DROPDOWN,
                default="English (en-US)",
                options=["System Default", "English (en-US)"],
                tooltip=(
                    "Best-effort browser locale override for provider pages. "
                    "English helps with providers that expect English UI text, "
                    "but saved site/account language can still win."
                ),
                docs_path=DOCS_SYSTEM,
                docs_anchor="browser-locale-and-timezone",
            ),
            SettingField(
                key="browser_timezone",
                label="Browser Timezone",
                type=SettingType.DROPDOWN,
                default="System Default",
                options=["System Default", "New York (America/New_York)"],
                tooltip=(
                    "Optional browser timezone override. Leave this on System Default "
                    "unless you specifically want provider pages to report New York time."
                ),
                docs_path=DOCS_SYSTEM,
                docs_anchor="browser-locale-and-timezone",
            ),
            SettingField(
                key="delete_persistent_profile_row",
                label="Delete Profile",
                type=SettingType.ROW,
                default=None,
                ratios=[80, 20],
                tooltip="Delete a specific saved browser profile used for Persistent Sessions (logs you out).",
                docs_path=DOCS_SYSTEM,
                docs_anchor="delete-profile",
                sub_fields=[
                    SettingField(
                        key="persistent_profile_to_delete",
                        label="Profile",
                        type=SettingType.DROPDOWN,
                        default="",
                        options=[],
                        transient=True,
                        tooltip="Choose which saved profile to delete.",
                    ),
                    SettingField(
                        key="delete_persistent_profile_btn",
                        label="Delete",
                        type=SettingType.BUTTON,
                        default="Delete",
                        action="delete_selected_persistent_profile",
                        tooltip="Delete the selected profile.",
                    ),
                ],
            ),
            SettingField(
                key="clear_persistent_profiles_row",
                label="Clear Profiles",
                type=SettingType.ROW,
                default=None,
                ratios=[64, 36],
                tooltip="Delete saved browser profiles for selected providers (logs you out).",
                docs_path=DOCS_SYSTEM,
                docs_anchor="clear-profiles",
                sub_fields=[
                    SettingField(
                        key="clear_persistent_profiles_btn",
                        label="Clear All",
                        type=SettingType.BUTTON,
                        default="Clear All",
                        action="clear_selected_persistent_profiles",
                        tooltip="Delete saved browser profiles for the selected providers.",
                        button_height="row",
                    ),
                    SettingField(
                        key="clear_persistent_profile_providers",
                        label="Providers",
                        type=SettingType.MULTI_SELECT_DROPDOWN,
                        default=provider_options(),
                        options=provider_options(),
                        transient=True,
                        tooltip="Choose which providers should have saved browser profiles cleared.",
                    ),
                ],
            ),
            SettingField(
                key="notify_on_driver_crash",
                label="Warn if the Provider Window Closes",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Show a notification when the provider browser is closed or crashes unexpectedly.",
            ),
            SettingField(
                key="ignore_provider_locks",
                label="Ignore Provider Locks",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Allow temporarily locked providers to appear in provider selectors "
                    "and launch anyway. Only enable this if you are sure your setup can "
                    "use the locked provider without breaking requests."
                ),
                docs_path=DOCS_SYSTEM,
                docs_anchor="provider-locks",
            ),
            SettingField(
                key="ignore_provider_locks_warning",
                label="Locked providers may fail hard",
                type=SettingType.HINT,
                default=(
                    "This bypasses provider safety locks. Right now that mainly means "
                    "Google AI Studio, which may detect automated browsers and prevent "
                    "messages from sending at all."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="system_settings.ignore_provider_locks",
                docs_path=DOCS_SYSTEM,
                docs_anchor="provider-locks",
            ),
            SettingField(
                key="config_storage_divider",
                label="Config Storage",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="config_storage_location",
                label="Config Storage Location",
                type=SettingType.DROPDOWN,
                default="Relative",
                options=get_config_storage_options(),
                tooltip=(
                    "Choose where to store configuration data (settings/key/profiles). "
                    "Changing this will migrate the config directory and restart the app."
                ),
                docs_path=DOCS_SYSTEM,
                docs_anchor="config-storage-location-presets",
            ),
            SettingField(
                key="config_storage_custom_path",
                label="Custom Config Directory",
                type=SettingType.DIRECTORY,
                default="",
                tooltip="Absolute paths recommended. Relative paths resolve from the app folder.",
                validator=validate_directory_path,
                docs_path=DOCS_SYSTEM,
                docs_anchor="migrating-config-storage",
            ),
            SettingField(
                key="ui_divider",
                label="Main Window",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="show_request_queue_preview",
                label="Show the Request Queue Panel",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Show an optional Request Queue panel in the main window.",
                docs_path=DOCS_API_BEHAVIOR,
                docs_anchor="request-queue-preview",
            ),
            SettingField(
                key="logging_levels_divider",
                label="Logging Levels",
                type=SettingType.DIVIDER,
                default=None,
            ),
            SettingField(
                key="stdout_log_level",
                label="Terminal",
                type=SettingType.DROPDOWN,
                default="Debug",
                options=["Debug", "Success", "Info", "Warning", "Error"],
                tooltip="Minimum severity for messages printed to the terminal (stdout).",
                docs_path=DOCS_CONSOLE,
                docs_anchor="logging-levels",
            ),
            SettingField(
                key="console_log_level",
                label="Console Window",
                type=SettingType.DROPDOWN,
                default="Debug",
                options=["Debug", "Success", "Info", "Warning", "Error"],
                tooltip="Minimum severity for messages shown in the Console Window.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="logging-levels",
            ),
            SettingField(
                key="mini_console_log_level",
                label="Activity Log",
                type=SettingType.DROPDOWN,
                default="Success",
                options=["Debug", "Success", "Info", "Warning", "Error"],
                tooltip="Minimum severity for messages shown in the Activity Log (main window).",
                docs_path=DOCS_CONSOLE,
                docs_anchor="logging-levels",
            ),
            SettingField(
                key="logfile_log_level",
                label="Logfiles",
                type=SettingType.DROPDOWN,
                default="Debug",
                options=["Debug", "Success", "Info", "Warning", "Error"],
                tooltip="Minimum severity for messages written to log files.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="logging-levels",
            ),
        ]
    ),
    SettingCategory(
        name="Experimental",
        key="experimental",
        fields=[
            SettingField(
                key="enable_loadouts",
                label="Enable Loadouts",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Experimental. Edit provider-specific Formatting and Provider Behavior "
                    "loadouts directly in Settings and switch them per provider."
                ),
                affects=["chevron_dropdown"],
                docs_path=DOCS_LOADOUTS,
            ),
            SettingField(
                key="providers_in_parallel",
                label="Run Providers in Parallel",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Experimental. Launch one browser per selected provider and route requests by "
                    "their model IDs. Applies on the next browser start and can use a lot of RAM."
                ),
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="providers_in_parallel_note",
                label="Providers in Parallel",
                type=SettingType.HINT,
                default=(
                    "This opens extra browser windows, keeps them idle in memory, and routes by "
                    "model IDs while active. Change the selection here, then restart the browser for it to take effect."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="experimental.providers_in_parallel",
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallelize_request_queue",
                label="Parallelize API Request Queue",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Very experimental. Allow multiple queued API requests to run at the same time "
                    "across different active provider lanes. Requires Providers in Parallel and "
                    "applies on the next browser start."
                ),
                front_tooltip="Run queued API requests concurrently across active parallel provider lanes.",
                visible_depends="experimental.providers_in_parallel",
                depends="experimental.providers_in_parallel",
                force_when_dep_unmet=True,
                docs_path=DOCS_PARALLEL_REQUEST_QUEUE,
            ),
            SettingField(
                key="parallelize_request_queue_note",
                label="Parallel Request Queue",
                type=SettingType.HINT,
                default=(
                    "This is intentionally extra experimental. Today it runs one request per active "
                    "provider lane, but it still depends on Providers in Parallel and may use more "
                    "RAM and CPU than the normal setup."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="experimental.providers_in_parallel&&experimental.parallelize_request_queue",
                docs_path=DOCS_PARALLEL_REQUEST_QUEUE,
            ),
            SettingField(
                key="full_parallelization",
                label="Full Parallelization",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Extremely experimental. Launch multiple account-backed browser "
                    "instances per enabled parallel provider. Requires the parallelized API queue."
                ),
                front_tooltip="Launch multiple account-backed browser lanes per enabled parallel provider.",
                visible_depends="experimental.providers_in_parallel&&experimental.parallelize_request_queue",
                depends="experimental.providers_in_parallel&&experimental.parallelize_request_queue",
                force_when_dep_unmet=False,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="full_parallelization_note",
                label="Full Parallelization",
                type=SettingType.HINT,
                default=(
                    "This is heavier than the other parallel features combined. Each extra lane "
                    "launches another provider browser/profile and uses saved accounts when available."
                ),
                tooltip=None,
                hint_variant="warn",
                visible_depends="experimental.full_parallelization",
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_deepseek",
                label="DeepSeek",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include DeepSeek in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=DeepSeek",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_deepseek",
                label="DeepSeek Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many DeepSeek account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="DeepSeek instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_deepseek",
                depends="experimental.full_parallelization&&experimental.parallel_enable_deepseek",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_glm",
                label="GLM Chat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include GLM Chat in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=GLM Chat",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_glm",
                label="GLM Chat Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many GLM Chat account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="GLM Chat instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_glm",
                depends="experimental.full_parallelization&&experimental.parallel_enable_glm",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_moonshot",
                label="Moonshot",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include Moonshot in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=Moonshot",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_moonshot",
                label="Moonshot Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many Moonshot account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="Moonshot instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_moonshot",
                depends="experimental.full_parallelization&&experimental.parallel_enable_moonshot",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_qwen",
                label="QwenLM",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include QwenLM in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=QwenLM",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_qwen",
                label="QwenLM Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many QwenLM account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="QwenLM instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_qwen",
                depends="experimental.full_parallelization&&experimental.parallel_enable_qwen",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_perplexity",
                label="Perplexity",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include Perplexity in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=Perplexity",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_perplexity",
                label="Perplexity Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many Perplexity account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="Perplexity instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_perplexity",
                depends="experimental.full_parallelization&&experimental.parallel_enable_perplexity",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_huggingchat",
                label="HuggingChat",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Include HuggingChat in the parallel browser pool.",
                visible_depends="experimental.providers_in_parallel",
                depends="providers_credentials.provider!=HuggingChat",
                force_when_dep_unmet=True,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_huggingchat",
                label="HuggingChat Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many HuggingChat account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="HuggingChat instances"),
                visible_depends="experimental.full_parallelization&&experimental.parallel_enable_huggingchat",
                depends="experimental.full_parallelization&&experimental.parallel_enable_huggingchat",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="parallel_enable_aistudio",
                label="Google AI Studio",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Include Google AI Studio in the parallel browser pool. AI Studio is "
                    "temporarily locked unless Ignore Provider Locks is enabled."
                ),
                visible_depends="experimental.providers_in_parallel",
                depends="system_settings.ignore_provider_locks&&providers_credentials.provider!=Google AI Studio",
                force_when_dep_unmet=False,
                docs_path=DOCS_PROVIDERS_IN_PARALLEL,
            ),
            SettingField(
                key="parallel_instances_aistudio",
                label="Google AI Studio Instances",
                type=SettingType.INTEGER,
                default=1,
                tooltip="How many Google AI Studio account/profile lanes to launch when Full Parallelization is enabled.",
                validator=validate_integer_range(1, 32, label="Google AI Studio instances"),
                visible_depends="system_settings.ignore_provider_locks&&experimental.full_parallelization&&experimental.parallel_enable_aistudio",
                depends="system_settings.ignore_provider_locks&&experimental.full_parallelization&&experimental.parallel_enable_aistudio",
                force_when_dep_unmet=1,
                docs_path=DOCS_FULL_PARALLELIZATION,
            ),
            SettingField(
                key="classic_title",
                label="Use the Classic Title Bar",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Use the classic title layout instead of the new logo + styled title.",
                affects=["title_bar"],
            ),
            SettingField(
                key="changelog_button",
                label="Show the News Button",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip=(
                    "Show the News bell button next to Help. "
                    "The button can show a red dot when new changelog/news items are available."
                ),
                affects=["news_button"],
            ),
            SettingField(
                key="enable_remote_control",
                label="Enable Remote Control",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Expose an opt-in HTML remote-control interface on the running API server. "
                    "Remote routes still respect the IP whitelist when enabled."
                ),
                docs_path=DOCS_REMOTE_CONTROL,
                docs_anchor="enable-it",
            ),
            SettingField(
                key="remote_control_password",
                label="Remote Control Password",
                type=SettingType.PASSWORD,
                default="",
                tooltip=(
                    "Optional password for the Remote Control interface. Leave blank to disable "
                    "password auth and rely on network restrictions only."
                ),
                depends="experimental.enable_remote_control",
                docs_path=DOCS_REMOTE_CONTROL,
                docs_anchor="passwords-and-tokens",
            ),
        ],
    ),
    SettingCategory(
        name="Application Settings",
        key="application_settings",
        fields=[
            SettingField(
                key="current_version_info",
                label="Current Version",
                type=SettingType.DESCRIPTION,
                default="Current version: (loading...)",
                tooltip=None,
            ),
            SettingField(
                key="update_status_info",
                label="Update Status",
                type=SettingType.DESCRIPTION,
                default="Status: Not checked yet.",
                tooltip=None,
            ),
            SettingField(
                key="check_for_updates_btn",
                label="Check For Updates",
                type=SettingType.BUTTON,
                default="Check",
                action="check_for_updates",
                tooltip="Check for available updates on GitHub.",
                docs_path=DOCS_SYSTEM,
                docs_anchor="updates",
            ),
            SettingField(
                key="check_for_updates_on_startup",
                label="Check for Updates on Launch",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Automatically check for updates when the app starts.",
                docs_path=DOCS_SYSTEM,
                docs_anchor="updates",
            ),
            SettingField(
                key="collapse_to_tray_on_close",
                label="Keep Running in the Tray When Closed",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="When enabled, closing the main window hides it to the tray instead of exiting.",
            ),
            SettingField(
                key="open_settings_full_screen",
                label="Open Settings Full-Screen",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Open the Settings window maximized by default.",
            ),
            SettingField(
                key="enable_animations",
                label="Enable Interface Animations",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Enable non-essential UI animations. "
                ),
            ),
            SettingField(
                key="hotswap_experience",
                label="Hotswap Button Style",
                type=SettingType.DROPDOWN,
                default="Discrete",
                options=["Discrete", "Persistent Discrete"],
                tooltip=(
                    "How the Hotswap shortcut appears. "
                    "Discrete: icon next to Help (while running). "
                    "Persistent Discrete: always visible."
                ),
                affects=["hotswap_button"],
                docs_path=DOCS_HOTSWAPS,
                docs_anchor="hotswap-experience",
            ),
        ],
    ),
    SettingCategory(
        name="Console Settings",
        key="console_settings",
        fields=[
            SettingField(
                key="enable_console",
                label="Open a Console Window",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Show a console window for viewing application logs.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="enabling-the-console",
            ),
            SettingField(
                key="log_to_main",
                label="Also Show Logs in the Main Window",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Also log to the Activity Log in the main window. Forced on if the console is disabled.",
                depends="console_settings.enable_console",
                force_when_dep_unmet=True,
                docs_path=DOCS_CONSOLE,
                docs_anchor="log-routing",
            ),
            SettingField(
                key="log_to_stdout",
                label="Also Print Logs to the Terminal",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Also log to stdout/terminal. Forced on if the console is disabled.",
                depends="console_settings.enable_console",
                force_when_dep_unmet=True,
                docs_path=DOCS_CONSOLE,
                docs_anchor="log-routing",
            ),
            SettingField(
                key="max_lines",
                label="Lines to Keep",
                type=SettingType.INTEGER,
                default=500,
                tooltip="Maximum number of lines to keep in the console history.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="console-appearance",
            ),
            SettingField(
                key="font_size",
                label="Text Size",
                type=SettingType.INTEGER,
                default=10,
                tooltip="Font size for the console text.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="console-appearance",
            ),
            SettingField(
                key="wrap_lines",
                label="Wrap Long Lines",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Soft-wrap long lines in the console window.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="console-appearance",
            ),
            SettingField(
                key="auto_scroll_mode",
                label="Auto-Scroll",
                type=SettingType.DROPDOWN,
                default="Always",
                options=["Always", "Bottom only", "Never"],
                tooltip="Control how the console view follows new log messages.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="console-appearance",
            ),
            SettingField(
                key="color_palette",
                label="Color Theme",
                type=SettingType.DROPDOWN,
                default="Modern",
                options=["Modern", "Classic", "Bright"],
                tooltip="Choose a color scheme for log levels.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="color-palettes",
            ),
            SettingField(
                key="always_on_top",
                label="Keep the Console on Top",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Keep the console window on top of other windows.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="console-appearance",
            ),
        ]
    ),
    SettingCategory(
        name="Console Dumping",
        key="console_dumping",
        fields=[
            SettingField(
                key="confirm_clear",
                label="Ask Before Clearing the Console",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Ask for confirmation before clearing the console output.",
                docs_path=DOCS_CONSOLE,
                docs_anchor="dump-settings",
            ),
            SettingField(
                key="condump_directory",
                label="Export Folder",
                type=SettingType.DIRECTORY,
                default=None,
                tooltip="Directory to write console dumps to. Leave blank to ask each time.",
                validator=validate_directory_path,
                nullable=True,
                docs_path=DOCS_CONSOLE,
                docs_anchor="dump-settings",
            ),
        ]
    ),
    SettingCategory(
        name="Network Settings",
        key="network_settings",
        fields=[
            SettingField(
                key="port",
                label="Server Port",
                type=SettingType.INTEGER,
                default=7777,
                tooltip="Port for the local API server.",
                validator=validate_port,
                docs_path=DOCS_NETWORK,
                docs_anchor="port",
            ),
            SettingField(
                key="available_on_lan",
                label="Allow Local Network Access",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Make the API server accessible from other devices on the local network.",
                docs_path=DOCS_NETWORK,
                docs_anchor="lan-availability",
            ),
            SettingField(
                key="show_ip",
                label="Show the Server Address in Logs",
                type=SettingType.BOOLEAN,
                default=True,
                tooltip="Print the server address(es) to the console when the API server starts.",
                docs_path=DOCS_NETWORK,
                docs_anchor="show-ip",
            ),
            SettingField(
                key="enable_umm",
                label="Use Universal Model Names",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Show `intenserp-auto`, `intenserp-reasoner`, and `intenserp-chat` from the "
                    "API in normal single-provider mode so you can switch providers without "
                    "changing the model name in your client. DeepSeek also exposes matching "
                    "`intenserp-expert-*` variants. Providers with real model pickers also expose "
                    "per-model variants that override the selected UI model for that request. "
                    "Provider-prefixed IDs still work. In Providers in Parallel, `intenserp-*` "
                    "stays disabled, but UMM real-model IDs are available, with provider prefixes "
                    "only when exact IDs would collide."
                ),
                front_tooltip="Expose stable IntenseRP aliases and real-model IDs through the API.",
                docs_path=DOCS_UNIVERSAL_MODEL_NAMES,
            ),
            SettingField(
                key="accept_reasoning_effort",
                label="Accept API Reasoning Effort",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip=(
                    "Let OpenAI-compatible requests use `reasoning_effort` (or "
                    "`reasoning.effort`) to control provider reasoning for that request. "
                    "No effort, Minimum, and Low map to chat/off for most providers; "
                    "Medium and above map to reasoning/on. Google AI Studio maps efforts "
                    "to its Thinking Level controls."
                ),
                front_tooltip="Allow API requests to set supported providers' reasoning level.",
                docs_path=DOCS_NETWORK,
                docs_anchor="api-reasoning-effort",
            ),
            SettingField(
                key="accept_reasoning_effort_providers",
                label="Reasoning Effort Providers",
                type=SettingType.MULTI_SELECT_DROPDOWN,
                default=provider_options(),
                options=provider_options(),
                tooltip=(
                    "Choose which providers may honor OpenAI-compatible `reasoning_effort` "
                    "requests. Providers left unchecked ignore the request field and keep "
                    "using the model ID suffix, Provider Behavior settings, or loadout values."
                ),
                depends="network_settings.accept_reasoning_effort",
                visible_depends="network_settings.accept_reasoning_effort",
                docs_path=DOCS_NETWORK,
                docs_anchor="api-reasoning-effort",
            ),
            SettingField(
                key="use_api_keys",
                label="Require API Keys",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Require an API key (Bearer) for incoming requests.",
                docs_path=DOCS_NETWORK,
                docs_anchor="api-keys",
            ),
            SettingField(
                key="api_keys",
                label="Allowed API Keys",
                type=SettingType.INPUT_PAIR,
                default=[],
                tooltip="List of API key name/value pairs.",
                alternative_actions=[
                    AlternativeAction(
                        name="Generate Key",
                        icon="dices.svg",
                        action="generate_api_key",
                    ),
                ],
                depends="network_settings.use_api_keys",
                required=True,
                docs_path=DOCS_NETWORK,
                docs_anchor="api-keys",
            ),
            SettingField(
                key="use_ip_whitelist",
                label="Restrict Access by IP Address",
                type=SettingType.BOOLEAN,
                default=False,
                tooltip="Only allow API requests from the listed IP addresses.",
                docs_path=DOCS_IP_WHITELIST,
                docs_anchor="how-to-use-it",
            ),
            SettingField(
                key="ip_whitelist",
                label="Allowed IP Addresses",
                type=SettingType.INPUT_LIST,
                default=[],
                tooltip="List of IP addresses allowed to access the API.",
                validator=validate_ip_address_list,
                depends="network_settings.use_ip_whitelist",
                required=True,
                docs_path=DOCS_IP_WHITELIST,
                docs_anchor="how-to-use-it",
            ),
        ]
    ),
]


SETTINGS_SECTIONS = [
    SettingSection(
        key="provider_login",
        label="Provider and Login",
        icon="key.svg",
        card_keys=["provider_choice", "sign_in_accounts", "saved_sessions", "browser_environment"],
    ),
    SettingSection(
        key="provider_behavior",
        label="Provider Behavior",
        icon="brain.svg",
        card_keys=["provider_defaults"],
    ),
    SettingSection(
        key="api_server",
        label="API Server",
        icon="share-2.svg",
        card_keys=[
            "server_access",
            "server_model_ids",
            "server_request_controls",
            "server_security",
        ],
    ),
    SettingSection(
        key="formatting",
        label="Formatting",
        icon="type.svg",
        card_keys=["loadout_editor", "message_style", "name_detection", "extra_instruction"],
    ),
    SettingSection(
        key="interface",
        label="Interface",
        icon="monitor.svg",
        card_keys=["window_behavior", "main_window", "updates"],
    ),
    SettingSection(
        key="logs_troubleshooting",
        label="Logs and Troubleshooting",
        icon="terminal.svg",
        card_keys=["log_to_files", "console_window", "logging_levels", "export_cleanup", "bug_reports"],
    ),
    SettingSection(
        key="advanced",
        label="Advanced",
        icon="flask-conical.svg",
        card_keys=["provider_stability", "config_storage", "experimental_features"],
    ),
]


SETTINGS_CARDS = {
    "provider_choice": SettingCard(
        key="provider_choice",
        title="Current Provider",
        field_refs=[("providers_credentials", "provider")],
    ),
    "sign_in_accounts": SettingCard(
        key="sign_in_accounts",
        title="Sign-In and Accounts",
        field_refs=[
            ("providers_credentials", "auto_login"),
            ("providers_credentials", "select_least_used"),
            ("providers_credentials", "reload_on_failure"),
            ("providers_credentials", "credential_manager"),
        ],
    ),
    "saved_sessions": SettingCard(
        key="saved_sessions",
        title="Saved Sessions",
        field_refs=[
            ("system_settings", "persistent_sessions"),
            ("system_settings", "profile_compatibility_warnings"),
            ("system_settings", "delete_persistent_profile_row"),
            ("system_settings", "clear_persistent_profiles_row"),
        ],
    ),
    "browser_environment": SettingCard(
        key="browser_environment",
        title="Browser Environment",
        description=(
            "Launch-time browser overrides for provider pages, especially helpful for non-English systems."
        ),
        field_refs=[
            ("system_settings", "browser_locale"),
            ("system_settings", "browser_timezone"),
        ],
    ),
    "provider_defaults": SettingCard(
        key="provider_defaults",
        title="Provider",
        special="provider_behavior",
    ),
    "server_access": SettingCard(
        key="server_access",
        title="Access",
        field_refs=[
            ("network_settings", "port"),
            ("network_settings", "available_on_lan"),
            ("network_settings", "show_ip"),
        ],
    ),
    "server_model_ids": SettingCard(
        key="server_model_ids",
        title="Model IDs",
        field_refs=[("network_settings", "enable_umm")],
    ),
    "server_request_controls": SettingCard(
        key="server_request_controls",
        title="Request Controls",
        field_refs=[
            ("network_settings", "accept_reasoning_effort"),
            ("network_settings", "accept_reasoning_effort_providers"),
        ],
    ),
    "server_security": SettingCard(
        key="server_security",
        title="Security",
        field_refs=[
            ("network_settings", "use_api_keys"),
            ("network_settings", "api_keys"),
            ("network_settings", "use_ip_whitelist"),
            ("network_settings", "ip_whitelist"),
        ],
    ),
    "message_style": SettingCard(
        key="message_style",
        title="Message Style",
        field_refs=[
            ("formatting", "formatting_preset"),
            ("formatting", "formatting_template"),
            ("formatting", "reset_formatting_btn"),
            ("formatting", "formatting_divider"),
            ("formatting", "apply_formatting"),
        ],
    ),
    "loadout_editor": SettingCard(
        key="loadout_editor",
        title="Loadouts",
        special="loadout_editor",
    ),
    "name_detection": SettingCard(
        key="name_detection",
        title="Name Detection",
        description="These methods are checked in order. If none of them works, role names are used instead.",
        field_refs=[
            ("formatting", "enable_msg_objects"),
            ("formatting", "enable_ir2"),
            ("formatting", "enable_classic_irp"),
        ],
    ),
    "extra_instruction": SettingCard(
        key="extra_instruction",
        title="Extra Instruction",
        description="Add a small instruction before or after the formatted chat. Supports {{user}} and {{char}} placeholders.",
        field_refs=[
            ("formatting", "injection_position"),
            ("formatting", "injection_content"),
            ("formatting", "reset_injection_btn"),
        ],
    ),
    "window_behavior": SettingCard(
        key="window_behavior",
        title="Window Behavior",
        field_refs=[
            ("application_settings", "open_settings_full_screen"),
            ("application_settings", "collapse_to_tray_on_close"),
            ("application_settings", "enable_animations"),
            ("experimental", "classic_title"),
        ],
    ),
    "main_window": SettingCard(
        key="main_window",
        title="Main Window",
        field_refs=[
            ("system_settings", "show_request_queue_preview"),
            ("experimental", "changelog_button"),
            ("application_settings", "hotswap_experience"),
        ],
    ),
    "updates": SettingCard(
        key="updates",
        title="Updates",
        field_refs=[
            ("application_settings", "current_version_info"),
            ("application_settings", "update_status_info"),
            ("application_settings", "check_for_updates_btn"),
            ("application_settings", "check_for_updates_on_startup"),
        ],
    ),
    "log_to_files": SettingCard(
        key="log_to_files",
        title="Log to Files",
        field_refs=[
            ("logfiles", "enable_logfiles"),
            ("logfiles", "log_dir"),
            ("logfiles", "max_files"),
            ("logfiles", "max_file_size"),
        ],
    ),
    "bug_reports": SettingCard(
        key="bug_reports",
        title="Bug Reports",
        field_refs=[
            ("diagnostics", "bug_reports_warning"),
            ("diagnostics", "keep_internal_log"),
            ("diagnostics", "save_last_prompt"),
        ],
    ),
    "console_window": SettingCard(
        key="console_window",
        title="Console Window",
        field_refs=[
            ("console_settings", "enable_console"),
            ("console_settings", "log_to_main"),
            ("console_settings", "log_to_stdout"),
            ("console_settings", "max_lines"),
            ("console_settings", "font_size"),
            ("console_settings", "wrap_lines"),
            ("console_settings", "auto_scroll_mode"),
            ("console_settings", "color_palette"),
            ("console_settings", "always_on_top"),
        ],
    ),
    "logging_levels": SettingCard(
        key="logging_levels",
        title="Logging Levels",
        field_refs=[
            ("system_settings", "stdout_log_level"),
            ("system_settings", "console_log_level"),
            ("system_settings", "mini_console_log_level"),
            ("system_settings", "logfile_log_level"),
        ],
    ),
    "export_cleanup": SettingCard(
        key="export_cleanup",
        title="Export and Cleanup",
        field_refs=[
            ("console_dumping", "confirm_clear"),
            ("console_dumping", "condump_directory"),
        ],
    ),
    "provider_stability": SettingCard(
        key="provider_stability",
        title="Provider Stability",
        field_refs=[
            ("system_settings", "notify_on_driver_crash"),
            ("system_settings", "ignore_provider_locks"),
            ("system_settings", "ignore_provider_locks_warning"),
        ],
    ),
    "config_storage": SettingCard(
        key="config_storage",
        title="Config Storage",
        field_refs=[
            ("system_settings", "config_storage_location"),
            ("system_settings", "config_storage_custom_path"),
        ],
    ),
    "experimental_features": SettingCard(
        key="experimental_features",
        title="Experimental Features",
        field_refs=[
            ("experimental", "enable_loadouts"),
            ("experimental", "providers_in_parallel"),
            ("experimental", "providers_in_parallel_note"),
            ("experimental", "parallelize_request_queue"),
            ("experimental", "parallelize_request_queue_note"),
            ("experimental", "full_parallelization"),
            ("experimental", "full_parallelization_note"),
            ("experimental", "parallel_enable_deepseek"),
            ("experimental", "parallel_instances_deepseek"),
            ("experimental", "parallel_enable_glm"),
            ("experimental", "parallel_instances_glm"),
            ("experimental", "parallel_enable_moonshot"),
            ("experimental", "parallel_instances_moonshot"),
            ("experimental", "parallel_enable_qwen"),
            ("experimental", "parallel_instances_qwen"),
            ("experimental", "parallel_enable_perplexity"),
            ("experimental", "parallel_instances_perplexity"),
            ("experimental", "parallel_enable_huggingchat"),
            ("experimental", "parallel_instances_huggingchat"),
            ("experimental", "parallel_enable_aistudio"),
            ("experimental", "parallel_instances_aistudio"),
            ("experimental", "enable_remote_control"),
            ("experimental", "remote_control_password"),
        ],
    ),
}


PROVIDER_BEHAVIOR_GROUPS = {
    "deepseek_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["enable_deepthink", "send_deepthink", "enable_search"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "file_upload_timeout"]},
        {"title": "Retry and Reuse", "icon": "rotate-ccw.svg", "fields": ["clean_regeneration", "auto_delete_chats", "auto_delete_chats_warning", "multi_slot_cache", "first_chunk_timeout"]},
        {"title": "Filtering", "icon": "shield-ban.svg", "fields": ["anti_censorship"]},
    ],
    "glm_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["model", "enable_deepthink", "send_deepthink", "count_tokens", "search_forced_off_note", "enable_search", "enable_advanced_search", "enable_tools"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "file_upload_timeout", "text_file_filler"]},
        {"title": "Retry and Reuse", "icon": "rotate-ccw.svg", "fields": ["clean_regeneration", "auto_delete_chats", "auto_delete_chats_warning", "repetition_buster", "multi_slot_cache"]},
        {"title": "Quirks", "icon": "bug.svg", "fields": ["ui_click_timeout", "post_action_delay", "message_send_timeout", "completion_request_timeout", "first_chunk_timeout", "refresh_after_generation"]},
    ],
    "moonshot_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["enable_deepthink", "send_deepthink", "search_and_think_note", "enable_search"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "file_upload_timeout", "text_file_filler"]},
        {"title": "Retry and Reuse", "icon": "rotate-ccw.svg", "fields": ["clean_regeneration", "auto_delete_chats", "auto_delete_chats_warning", "multi_slot_cache"]},
        {"title": "Filtering", "icon": "shield-ban.svg", "fields": ["anti_censorship"]},
    ],
    "qwen_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["model", "enable_deepthink", "send_deepthink", "count_tokens", "search_forced_off_note", "enable_search", "enable_tools"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "text_file_message", "file_upload_timeout", "message_send_timeout"]},
        {"title": "Retry and Reuse", "icon": "rotate-ccw.svg", "fields": ["clean_regeneration", "auto_delete_chats", "auto_delete_chats_warning", "multi_slot_cache"]},
        {"title": "Quirks", "icon": "bug.svg", "fields": ["completion_request_timeout", "first_chunk_timeout"]},
    ],
    "perplexity_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["model", "subscription_note", "enable_deepthink", "send_deepthink", "search_forced_off_note", "enable_search"]},
        {"title": "Spaces", "icon": "sparkles.svg", "fields": ["use_spaces", "paste_system_instructions_into_space"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "text_file_message", "file_upload_timeout", "message_send_timeout"]},
    ],
    "huggingchat_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["model", "inference_provider", "subscription_note", "auto_disable_ratelimited_accounts", "enable_deepthink", "thinking_effort", "send_deepthink", "search_forced_off_note", "enable_search"]},
        {"title": "System Prompt", "icon": "type.svg", "fields": ["use_system_prompt_field", "paste_leading_system_messages"]},
        {"title": "Uploads", "icon": "upload.svg", "fields": ["send_as_text_file", "text_file_message", "file_upload_timeout", "file_upload_settle_delay", "message_send_timeout"]},
        {"title": "Retry and Reuse", "icon": "rotate-ccw.svg", "fields": ["clean_regeneration", "auto_delete_chats", "auto_delete_chats_warning", "multi_slot_cache"]},
        {"title": "Quirks", "icon": "bug.svg", "fields": ["completion_request_timeout", "first_chunk_timeout", "model_apply_timeout", "post_action_delay"]},
    ],
    "aistudio_behavior": [
        {"title": "Core", "icon": "settings.svg", "fields": ["provider_lock_warning", "model", "enable_deepthink", "thinking_level", "send_deepthink"]},
        {"title": "Tools and Uploads", "icon": "upload.svg", "fields": ["enable_search", "enable_url_context", "use_system_prompt_field", "send_as_text_file", "text_file_message", "file_upload_timeout"]},
        {"title": "Filtering", "icon": "shield-ban.svg", "fields": ["anti_censorship", "caars_enabled", "caars_savior_model", "anti_censorship_replacement_message", "anti_censorship_continue_nudge"]},
        {"title": "Sampling", "icon": "sliders-horizontal.svg", "fields": ["temperature", "top_p", "max_output_tokens"]},
        {"title": "Automation", "icon": "sparkles.svg", "fields": ["auto_login_redirect_timeout", "assume_english_ui", "assume_english_ui_warning", "assume_paid_model_access", "assume_paid_model_access_warning", "paid_model_access_emails", "clean_regeneration", "preflight_next_chat"]},
    ],
}

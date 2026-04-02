import os
import html
import logging
from telegram import Bot, MessageEntity, InlineKeyboardButton, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ExtBot
from telegram._utils.defaultvalue import DefaultValue

_PREMIUM_EMOJI_PREFIX = "PREMIUM_EMOJI_"
_PREMIUM_EMOJI_BTN_PREFIX = "PREMIUM_EMOJI_BTN_"


def _emoji_from_suffix(suffix: str) -> str:
    parts = suffix.split("_")
    codepoints = []
    for part in parts:
        if not part.startswith("U") or len(part) <= 1:
            raise ValueError
        codepoints.append(int(part[1:], 16))
    return "".join(chr(cp) for cp in codepoints)


def _load_premium_emoji_map(prefix: str = _PREMIUM_EMOJI_PREFIX) -> dict:
    mapping = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        if not value:
            continue
        suffix = key[len(prefix):].strip()
        if not suffix:
            continue
        try:
            emoji = _emoji_from_suffix(suffix)
        except Exception:
            continue
        mapping[emoji] = value
    return mapping


_DEBUG = os.getenv("PREMIUM_EMOJI_DEBUG", "").strip() == "1"
_MODE = os.getenv("PREMIUM_EMOJI_MODE", "auto").strip().lower()
_FORCE = os.getenv("PREMIUM_EMOJI_FORCE", "").strip() == "1"
_LOGGER = logging.getLogger("premium-emoji")

_PREMIUM_EMOJI_MAP = _load_premium_emoji_map()
_PREMIUM_EMOJI_KEYS = sorted(_PREMIUM_EMOJI_MAP.keys(), key=len, reverse=True)
_PREMIUM_EMOJI_BTN_MAP = _load_premium_emoji_map(_PREMIUM_EMOJI_BTN_PREFIX)
_PREMIUM_EMOJI_BTN_KEYS = sorted(
    set(_PREMIUM_EMOJI_BTN_MAP.keys()) | set(_PREMIUM_EMOJI_MAP.keys()),
    key=len,
    reverse=True,
)

_ORIG_INLINE_KB = InlineKeyboardButton
_ORIG_KEYBOARD_BTN = KeyboardButton


def reload_premium_emojis() -> int:
    global _PREMIUM_EMOJI_MAP, _PREMIUM_EMOJI_KEYS, _PREMIUM_EMOJI_BTN_MAP, _PREMIUM_EMOJI_BTN_KEYS, _MODE, _FORCE
    _PREMIUM_EMOJI_MAP = _load_premium_emoji_map()
    _PREMIUM_EMOJI_KEYS = sorted(_PREMIUM_EMOJI_MAP.keys(), key=len, reverse=True)
    _PREMIUM_EMOJI_BTN_MAP = _load_premium_emoji_map(_PREMIUM_EMOJI_BTN_PREFIX)
    _PREMIUM_EMOJI_BTN_KEYS = sorted(
        set(_PREMIUM_EMOJI_BTN_MAP.keys()) | set(_PREMIUM_EMOJI_MAP.keys()),
        key=len,
        reverse=True,
    )
    _MODE = os.getenv("PREMIUM_EMOJI_MODE", "auto").strip().lower()
    _FORCE = os.getenv("PREMIUM_EMOJI_FORCE", "").strip() == "1"
    return len(_PREMIUM_EMOJI_MAP)


def render_premium_emojis(text: str) -> str:
    if text is None:
        return text
    safe = html.escape(text, quote=False)
    if not _PREMIUM_EMOJI_KEYS:
        return safe
    replaced = 0
    for emoji in _PREMIUM_EMOJI_KEYS:
        emoji_id = _PREMIUM_EMOJI_MAP.get(emoji)
        if not emoji_id:
            continue
        tag = f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
        # handle variation selector (emoji + U+FE0F)
        with_vs16 = f"{emoji}\ufe0f"
        if with_vs16 in safe:
            safe = safe.replace(with_vs16, tag)
            replaced += 1
        if emoji in safe:
            safe = safe.replace(emoji, tag)
            replaced += 1
    if _DEBUG and replaced:
        _LOGGER.info("premium-emoji replaced=%s", replaced)
    return safe


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _strip_leading_emoji(text: str, keys=None):
    if not text:
        return text, None
    keys = keys if keys is not None else _PREMIUM_EMOJI_KEYS
    if not keys:
        return text, None
    stripped = text.lstrip()
    leading_ws = text[: len(text) - len(stripped)]
    for emoji in keys:
        emoji_vs16 = f"{emoji}\ufe0f"
        if stripped.startswith(emoji_vs16):
            rest = stripped[len(emoji_vs16):].lstrip()
            return leading_ws + rest, emoji
        if stripped.startswith(emoji):
            rest = stripped[len(emoji):].lstrip()
            return leading_ws + rest, emoji
    return text, None


def _merge_api_kwargs(api_kwargs: dict, updates: dict) -> dict:
    merged = dict(api_kwargs) if api_kwargs else {}
    merged.update(updates)
    return merged


def _inline_button_with_premium_icon(text: str, *args, **kwargs):
    api_kwargs = kwargs.pop("api_kwargs", None)
    cleaned, emoji = _strip_leading_emoji(text, _PREMIUM_EMOJI_BTN_KEYS)
    emoji_id = _PREMIUM_EMOJI_BTN_MAP.get(emoji) if emoji else None
    if not emoji_id and emoji:
        emoji_id = _PREMIUM_EMOJI_MAP.get(emoji)
    if emoji_id:
        api_kwargs = _merge_api_kwargs(api_kwargs, {"icon_custom_emoji_id": str(emoji_id)})
        text = cleaned
    return _ORIG_INLINE_KB(text, *args, api_kwargs=api_kwargs, **kwargs)


def _keyboard_button_with_premium_icon(text: str, *args, **kwargs):
    api_kwargs = kwargs.pop("api_kwargs", None)
    cleaned, emoji = _strip_leading_emoji(text, _PREMIUM_EMOJI_BTN_KEYS)
    emoji_id = _PREMIUM_EMOJI_BTN_MAP.get(emoji) if emoji else None
    if not emoji_id and emoji:
        emoji_id = _PREMIUM_EMOJI_MAP.get(emoji)
    if emoji_id:
        api_kwargs = _merge_api_kwargs(api_kwargs, {"icon_custom_emoji_id": str(emoji_id)})
        text = cleaned
    return _ORIG_KEYBOARD_BTN(text, *args, api_kwargs=api_kwargs, **kwargs)


def _build_custom_emoji_entities(text: str):
    if not text or not _PREMIUM_EMOJI_KEYS:
        return []
    entities = []
    for emoji in _PREMIUM_EMOJI_KEYS:
        emoji_id = _PREMIUM_EMOJI_MAP.get(emoji)
        if not emoji_id:
            continue
        # prefer VS16 match if present
        emoji_vs16 = f"{emoji}\ufe0f"
        start = 0
        while True:
            idx = text.find(emoji_vs16, start)
            if idx == -1:
                break
            offset = _utf16_len(text[:idx])
            length = _utf16_len(emoji_vs16)
            entities.append(
                MessageEntity(
                    type=MessageEntity.CUSTOM_EMOJI,
                    offset=offset,
                    length=length,
                    custom_emoji_id=str(emoji_id),
                )
            )
            start = idx + len(emoji_vs16)
        start = 0
        while True:
            idx = text.find(emoji, start)
            if idx == -1:
                break
            # skip if this is the start of emoji+VS16 (already handled)
            if text.startswith(emoji_vs16, idx):
                start = idx + len(emoji_vs16)
                continue
            offset = _utf16_len(text[:idx])
            length = _utf16_len(emoji)
            entities.append(
                MessageEntity(
                    type=MessageEntity.CUSTOM_EMOJI,
                    offset=offset,
                    length=length,
                    custom_emoji_id=str(emoji_id),
                )
            )
            start = idx + len(emoji)
    if entities:
        entities.sort(key=lambda e: (e.offset, e.length))
    return entities


def _prepare_text(text: str, kwargs: dict, entity_key: str = "entities") -> tuple:
    if text is None:
        return text, kwargs
    if kwargs.pop("disable_premium_emoji", False):
        return text, kwargs
    explicit_entities = False
    # Treat DefaultValue/None entities as not provided so we can inject our own
    if entity_key in kwargs:
        ent_val = kwargs.get(entity_key)
        if isinstance(ent_val, DefaultValue) and ent_val.value is None:
            kwargs.pop(entity_key, None)
        elif ent_val is None:
            kwargs.pop(entity_key, None)
        else:
            explicit_entities = True
    if explicit_entities:
        return text, kwargs
    if _MODE == "html":
        kwargs.pop(entity_key, None)
        kwargs["parse_mode"] = ParseMode.HTML
        text = render_premium_emojis(text)
        if _DEBUG:
            _LOGGER.info("premium-emoji html")
        return text, kwargs
    parse_mode = kwargs.get("parse_mode")
    if isinstance(parse_mode, DefaultValue):
        parse_mode = parse_mode.value
    # Try entities approach (more reliable than HTML tag)
    if _MODE in ("auto", "entities") and entity_key not in kwargs:
        has_html = "<" in text or ">" in text
        allow_entities = _FORCE or (not has_html and (parse_mode is None or parse_mode == ParseMode.HTML or parse_mode == "HTML"))
        if allow_entities:
            entities = _build_custom_emoji_entities(text)
            if entities:
                kwargs[entity_key] = entities
                # remove parse_mode to avoid conflict with entities
                if "parse_mode" in kwargs:
                    kwargs.pop("parse_mode", None)
                if _DEBUG:
                    _LOGGER.info("premium-emoji entities=%s", len(entities))
                return text, kwargs
    # Fallback to HTML tags (auto mode only)
    if _MODE == "auto" and (parse_mode is None or parse_mode == ParseMode.HTML or parse_mode == "HTML"):
        kwargs["parse_mode"] = ParseMode.HTML
        text = render_premium_emojis(text)
    return text, kwargs


def _patch_bot_class(cls) -> None:
    if getattr(cls, "_premium_emoji_patched", False):
        return

    orig_send_message = cls.send_message
    orig_edit_message_text = cls.edit_message_text
    orig_send_photo = cls.send_photo
    orig_edit_message_caption = cls.edit_message_caption
    orig_send_document = cls.send_document
    orig_send_video = getattr(cls, "send_video", None)
    orig_send_animation = getattr(cls, "send_animation", None)
    orig_send_audio = getattr(cls, "send_audio", None)
    orig_send_voice = getattr(cls, "send_voice", None)

    def _patched_send_message(self, chat_id, text, *args, **kwargs):
        kwargs.pop("disable_premium_emoji", None)
        text, kwargs = _prepare_text(text, kwargs, "entities")
        return orig_send_message(self, chat_id, text, *args, **kwargs)

    def _patched_edit_message_text(self, text, *args, **kwargs):
        kwargs.pop("disable_premium_emoji", None)
        text, kwargs = _prepare_text(text, kwargs, "entities")
        return orig_edit_message_text(self, text, *args, **kwargs)

    def _patched_send_photo(self, chat_id, photo, *args, **kwargs):
        kwargs.pop("disable_premium_emoji", None)
        if "caption" in kwargs:
            caption, kwargs = _prepare_text(kwargs.get("caption"), kwargs, "caption_entities")
            kwargs["caption"] = caption
        return orig_send_photo(self, chat_id, photo, *args, **kwargs)

    def _patched_edit_message_caption(self, *args, **kwargs):
        kwargs.pop("disable_premium_emoji", None)
        if "caption" in kwargs:
            caption, kwargs = _prepare_text(kwargs.get("caption"), kwargs, "caption_entities")
            kwargs["caption"] = caption
        return orig_edit_message_caption(self, *args, **kwargs)

    def _patched_send_document(self, chat_id, document, *args, **kwargs):
        kwargs.pop("disable_premium_emoji", None)
        if "caption" in kwargs:
            caption, kwargs = _prepare_text(kwargs.get("caption"), kwargs, "caption_entities")
            kwargs["caption"] = caption
        return orig_send_document(self, chat_id, document, *args, **kwargs)

    def _wrap_caption_method(orig_func):
        if orig_func is None:
            return None

        def _patched(self, chat_id, media, *args, **kwargs):
            kwargs.pop("disable_premium_emoji", None)
            if "caption" in kwargs:
                caption, kwargs = _prepare_text(kwargs.get("caption"), kwargs, "caption_entities")
                kwargs["caption"] = caption
            return orig_func(self, chat_id, media, *args, **kwargs)

        return _patched

    cls.send_message = _patched_send_message
    cls.edit_message_text = _patched_edit_message_text
    cls.send_photo = _patched_send_photo
    cls.edit_message_caption = _patched_edit_message_caption
    cls.send_document = _patched_send_document
    if orig_send_video:
        cls.send_video = _wrap_caption_method(orig_send_video)
    if orig_send_animation:
        cls.send_animation = _wrap_caption_method(orig_send_animation)
    if orig_send_audio:
        cls.send_audio = _wrap_caption_method(orig_send_audio)
    if orig_send_voice:
        cls.send_voice = _wrap_caption_method(orig_send_voice)
    cls._premium_emoji_patched = True


_patch_bot_class(Bot)
_patch_bot_class(ExtBot)

# Patch button constructors to inject custom emoji icons when a leading emoji is present.
InlineKeyboardButton = _inline_button_with_premium_icon
KeyboardButton = _keyboard_button_with_premium_icon

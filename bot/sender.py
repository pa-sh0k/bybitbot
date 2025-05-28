import json
import logging
import asyncio
import aiohttp
import requests
from loguru import logger
from io import BytesIO

from aiogram import Bot
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    ForumTopicCreated,
    InputMediaPhoto,
    InputMediaAudio,
    InputMediaVideo,
    InputMediaDocument,
    InputFile,
    ChatInviteLink,
    FSInputFile,
    BufferedInputFile
)
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramBadRequest,
)


def truncate(text, length):
    if not isinstance(text, str):
        return text
    if len(text) <= length:
        return text
    return text[:length]


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = None,
    message_thread_id: int = None,
    disable_web_page_preview: bool = True,
    disable_notification: bool = False,
    reply_to: int = None,
    business_connection_id: str = None
) -> Message | None:
    text = truncate(text, 4096)
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            message_thread_id=message_thread_id,
            disable_web_page_preview=disable_web_page_preview,
            disable_notification=disable_notification,
            reply_to_message_id=reply_to,
            business_connection_id=business_connection_id
        )
    except TelegramRetryAfter as e:
        # Rate limit
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await send_message(
            bot,
            chat_id,
            text,
            reply_markup,
            parse_mode,
            message_thread_id,
            disable_web_page_preview,
            disable_notification,
            reply_to,
            business_connection_id
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await send_message(
                bot,
                chat_id,
                text,
                reply_markup,
                None,
                message_thread_id,
                disable_web_page_preview,
                disable_notification,
                reply_to,
                business_connection_id
            )
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def approve_chat_join_request(bot: Bot, chat_id: int, user_id: int):
    try:
        await bot.approve_chat_join_request(chat_id, user_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        await approve_chat_join_request(bot, chat_id, user_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def ban_chat_member(bot: Bot, chat_id: int, user_id: int):
    try:
        await bot.ban_chat_member(chat_id, user_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        await ban_chat_member(bot, chat_id, user_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def kick_chat_member(bot: Bot, chat_id: int, user_id: int):
    try:
        await bot.ban_chat_member(chat_id, user_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        await kick_chat_member(bot, chat_id, user_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def edit_message_reply_markup(bot: Bot, chat_id: int, message_id: int, reply_markup: InlineKeyboardMarkup):
    try:
        return await bot.edit_message_reply_markup(chat_id=str(chat_id), message_id=message_id, reply_markup=reply_markup)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await edit_message_reply_markup(bot, chat_id, message_id, reply_markup)
    except TelegramBadRequest as e:
        if 'message is not modified' in str(e):
            logging.error("Message markup is identical, skipping update")
        elif 'message to edit not found' in str(e):
            return None
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def edit_message_text(
    bot: Bot,
    text: str,
    chat_id: int,
    message_id: int,
    parse_mode: str = None,
    business_connection_id: str = None,
):
    text = truncate(text, 4096)
    try:
        return await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=parse_mode,
            business_connection_id=business_connection_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await edit_message_text(bot, text, chat_id, message_id, parse_mode, business_connection_id)
    except TelegramBadRequest as e:
        if 'message is not modified' in str(e):
            return None
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def edit_message_caption(
    bot: Bot,
    text: str,
    chat_id: int,
    message_id: int,
    parse_mode: str = None,
    business_connection_id: str = None
):
    text = truncate(text, 4096)
    try:
        return await bot.edit_message_caption(
            caption=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=parse_mode,
            business_connection_id=business_connection_id,
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await edit_message_caption(bot, text, chat_id, message_id, parse_mode, business_connection_id)
    except TelegramBadRequest as e:
        if 'message is not modified' in str(e):
            return None
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def set_chat_photo(bot: Bot, chat_id: int, photo_path: str):
    photo = FSInputFile(photo_path)
    try:
        await bot.set_chat_photo(chat_id=chat_id, photo=photo)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await set_chat_photo(bot, chat_id, photo_path)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def set_chat_title(bot: Bot, chat_id: int, title: str):
    title = truncate(title, 128)
    try:
        await bot.set_chat_title(chat_id, title)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await set_chat_title(bot, chat_id, title)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def promote_chat_member(bot: Bot, chat_id: int, user_id: int, can_pin_messages: bool, can_manage_topics: bool):
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_pin_messages=can_pin_messages,
            can_manage_topics=can_manage_topics
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        await promote_chat_member(bot, chat_id, user_id, can_pin_messages, can_manage_topics)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def send_photo(
    bot: Bot,
    chat_id: int,
    photo: str | bytes,
    caption: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = None,
    message_thread_id: int = None,
    file_path: str = None,
    disable_notification: bool = False,
    reply_to: int = None,
    business_connection_id: str = None
) -> Message | None:
    caption = truncate(caption, 1024) if caption else None

    try:
        if file_path:
            with open(file_path, 'rb') as f:
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=FSInputFile(path=file_path),
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to,
                    message_thread_id=message_thread_id,
                    business_connection_id=business_connection_id
                )
        else:
            # First try sending directly
            try:
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to,
                    message_thread_id=message_thread_id,
                    business_connection_id=business_connection_id
                )
            except TelegramBadRequest as e:
                if isinstance(photo, str) and (
                    "wrong type of the web page content" in str(e) or
                    "wrong file identifier/HTTP URL specified" in str(e) or
                    "failed to get HTTP URL content" in str(e)
                ):
                    # If direct URL fails, try downloading first
                    async with aiohttp.ClientSession() as session:
                        async with session.get(photo) as response:
                            if response.status == 200:
                                photo_data = await response.read()
                                return await bot.send_photo(
                                    chat_id=chat_id,
                                    photo=BufferedInputFile(photo_data, filename="photo.jpg"),
                                    caption=caption,
                                    parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    disable_notification=disable_notification,
                                    reply_to_message_id=reply_to,
                                    message_thread_id=message_thread_id,
                                    business_connection_id=business_connection_id
                                )
                raise  # Re-raise if it's not a URL issue or download failed
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        return await send_photo(
            bot,
            chat_id,
            photo,
            caption,
            reply_markup,
            parse_mode,
            message_thread_id,
            file_path,
            disable_notification,
            reply_to,
            business_connection_id=business_connection_id
        )
    except TelegramBadRequest as e:
        error_str = str(e)
        if "can't parse entities" in error_str:
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await send_photo(
                bot,
                chat_id,
                photo,
                caption,
                reply_markup,
                None,
                message_thread_id,
                file_path,
                disable_notification,
                reply_to,
                business_connection_id=business_connection_id
            )
        elif "wrong file identifier/HTTP URL specified" in error_str or "failed to get HTTP URL content" in error_str:
            logging.warning(f"HTTP URL ERROR: {photo}")
            with requests.get(photo, stream=True) as r:
                r.raise_for_status()
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=r.raw,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=disable_notification,
                    reply_to_message_id=reply_to,
                    message_thread_id=message_thread_id,
                    business_connection_id=business_connection_id
                )
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def edit_message_media(bot: Bot, photo: str | bytes, chat_id: int, message_id: int, business_connection_id: str = None):
    media = InputMediaPhoto(media=photo)
    try:
        return await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, business_connection_id=business_connection_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        return await edit_message_media(bot, photo, chat_id, message_id, business_connection_id)
    except TelegramBadRequest as e:
        if 'message is not modified' in str(e):
            return None
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def send_media_group(
    bot: Bot,
    chat_id: int,
    photos: list[str | bytes],
    parse_mode: str = None,
    message_thread_id: int = None
):
    group = [InputMediaPhoto(media=ph) for ph in photos]

    try:
        return await bot.send_media_group(
            chat_id=chat_id,
            media=group,
            message_thread_id=message_thread_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({"type": "rate_limit_log", "chat_id": chat_id, "wait_time": retry_after}))
        await asyncio.sleep(retry_after)
        return await send_media_group(bot, chat_id, photos, parse_mode, message_thread_id)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await bot.send_media_group(chat_id=chat_id, media=group, message_thread_id=message_thread_id)
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def send_video(
    bot: Bot,
    chat_id: int,
    video: str | bytes,
    height: int = None,
    width: int = None,
    caption: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = None,
    message_thread_id: int = None,
    file_path: str = None
):
    caption = truncate(caption, 1024) if caption else None

    try:
        if file_path:
            return await bot.send_video(
                    chat_id=chat_id,
                    video=FSInputFile(file_path),
                    height=height,
                    width=width,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    message_thread_id=message_thread_id,
                    request_timeout=60
                )
        else:
            return await bot.send_video(
                chat_id=chat_id,
                video=video,
                height=height,
                width=width,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
                request_timeout=60
            )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await send_video(
            bot, chat_id, video, height, width, caption, reply_markup,
            parse_mode, message_thread_id, file_path
        )
    except TelegramBadRequest as e:
        error_str = str(e)
        if "can't parse entities" in error_str:
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await send_video(
                bot, chat_id, video, height, width, caption, reply_markup,
                None, message_thread_id, file_path
            )
        elif "wrong file identifier/HTTP URL specified" in error_str or "failed to get HTTP URL content" in error_str:
            logging.warning(f"HTTP URL ERROR: {video}")
            with requests.get(video, stream=True) as r:
                r.raise_for_status()
                return await bot.send_video(
                    chat_id=chat_id,
                    video=BufferedInputFile(r.raw, filename="video.mp4"),
                    height=height,
                    width=width,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    message_thread_id=message_thread_id,
                    request_timeout=60
                )
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def send_document(
    bot: Bot,
    chat_id: int,
    document: str | FSInputFile,
    visible_file_name: str = None,
    caption: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = None,
    message_thread_id: int = None,
    reply_to: int = None,
    business_connection_id: str = None,
):
    caption = truncate(caption, 1024) if caption else None

    try:
        return await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
            request_timeout=60,
            reply_to_message_id=reply_to,
            business_connection_id =business_connection_id
            # aiogram v3 does not have `visible_file_name`
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await send_document(
            bot, chat_id, document, visible_file_name, caption,
            reply_markup, parse_mode, message_thread_id, reply_to
        )
    except TelegramBadRequest as e:
        error_str = str(e)
        if "can't parse entities" in error_str:
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await send_document(
                bot, chat_id, document, visible_file_name, caption,
                reply_markup, None, message_thread_id, reply_to
            )
        elif ("wrong file identifier/HTTP URL specified" in error_str or
              "failed to get HTTP URL content" in error_str or "invalid file HTTP URL specified" in error_str):
            logging.warning(f"HTTP URL ERROR: {document}")
            with requests.get(document, stream=True) as r:
                r.raise_for_status()
                return await bot.send_document(
                    chat_id=chat_id,
                    document=r.raw,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    message_thread_id=message_thread_id,
                    request_timeout=60,
                    reply_to_message_id=reply_to,
                    business_connection_id=business_connection_id
                )
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def send_audio(
    bot: Bot,
    chat_id: int,
    audio: str | bytes,
    caption: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = None,
    message_thread_id: int = None,
    business_connection_id: str = None,
):
    caption = truncate(caption, 1024) if caption else None

    try:
        return await bot.send_audio(
            chat_id=chat_id,
            audio=audio,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id,
            request_timeout=30,
            business_connection_id=business_connection_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await send_audio(bot, chat_id, audio, caption, reply_markup, parse_mode, message_thread_id)
    except TelegramBadRequest as e:
        error_str = str(e)
        if "can't parse entities" in error_str:
            logging.warning(f"Parse mode failed: {parse_mode}")
            return await send_audio(bot, chat_id, audio, caption, reply_markup, None, message_thread_id)
        elif ("wrong file identifier/HTTP URL specified" in error_str or
              "failed to get HTTP URL content" in error_str):
            logging.warning(f"HTTP URL ERROR: {audio}")
            with requests.get(audio, stream=True) as r:
                r.raise_for_status()
                return await bot.send_audio(
                    chat_id=chat_id,
                    audio=r.raw,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    message_thread_id=message_thread_id,
                    request_timeout=30,
                    business_connection_id=business_connection_id
                )
        else:
            logging.error(f"An error occurred: {e}", exc_info=True)
    return None


async def delete_message(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await delete_message(bot, chat_id, message_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def create_forum_topic(bot: Bot, chat_id: int, name: str, icon_custom_emoji_id: str = None):
    try:
        return await bot.create_forum_topic(
            chat_id=chat_id,
            name=name,
            icon_custom_emoji_id=icon_custom_emoji_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await create_forum_topic(bot, chat_id, name, icon_custom_emoji_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def send_chat_action(
    bot: Bot,
    chat_id: int,
    action: str,
    message_thread_id: int = None
):
    try:
        await bot.send_chat_action(
            chat_id=chat_id,
            action=action,
            message_thread_id=message_thread_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await send_chat_action(bot, chat_id, action, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def unpin_all_forum_topic_messages(bot: Bot, chat_id: int, message_thread_id: int):
    try:
        await bot.unpin_all_forum_topic_messages(
            chat_id=chat_id,
            message_thread_id=message_thread_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await unpin_all_forum_topic_messages(bot, chat_id, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def send_sticker(
    bot: Bot,
    chat_id: int,
    sticker: str | bytes,
    reply_markup: InlineKeyboardMarkup = None,
    message_thread_id: int = None
):
    try:
        await bot.send_sticker(
            chat_id=chat_id,
            sticker=sticker,
            reply_markup=reply_markup,
            message_thread_id=message_thread_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await send_sticker(bot, chat_id, sticker, reply_markup, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def edit_forum_topic(
    bot: Bot,
    chat_id: int,
    message_thread_id: int,
    name: str,
    icon_custom_emoji_id: str = None
) -> bool:
    try:
        await bot.edit_forum_topic(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            name=name,
            icon_custom_emoji_id=icon_custom_emoji_id
        )
        return True
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await edit_forum_topic(bot, chat_id, message_thread_id, name, icon_custom_emoji_id)
        return True
    except TelegramBadRequest as e:
        if 'TOPIC_NOT_MODIFIED' in str(e):
            logging.error('Double click or no changes to apply.')
            return False
        logging.error(f"An error occurred: {e}", exc_info=True)
    return False


async def close_forum_topic(bot: Bot, chat_id: int, message_thread_id: int):
    try:
        await bot.close_forum_topic(chat_id, message_thread_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await close_forum_topic(bot, chat_id, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def reopen_forum_topic(bot: Bot, chat_id: int, message_thread_id: int):
    try:
        await bot.reopen_forum_topic(chat_id, message_thread_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await reopen_forum_topic(bot, chat_id, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def delete_forum_topic(bot: Bot, chat_id: int, message_thread_id: int):
    try:
        await bot.delete_forum_topic(chat_id, message_thread_id)
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        await delete_forum_topic(bot, chat_id, message_thread_id)
    except TelegramBadRequest as e:
        logging.error(f"An error occurred: {e}", exc_info=True)


async def create_chat_invite_link(bot: Bot, chat_id: int, creates_join_request: bool = False) -> str | None:
    try:
        invite: ChatInviteLink = await bot.create_chat_invite_link(
            chat_id=chat_id,
            creates_join_request=creates_join_request
        )
        return invite.invite_link
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": chat_id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        invite: ChatInviteLink = await bot.create_chat_invite_link(
            chat_id=chat_id,
            creates_join_request=creates_join_request
        )
        return invite.invite_link
    except TelegramBadRequest as e:
        logger.error(str(e))
    return None


async def reply_to(
    bot: Bot,
    message: Message,
    text: str,
    parse_mode: str = None,
    business_connection_id: str = None
) -> Message | None:
    try:
        return await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            parse_mode=parse_mode,
            reply_to_message_id=message.message_id,
            business_connection_id=business_connection_id
        )
    except TelegramRetryAfter as e:
        retry_after = e.retry_after + 1
        logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds.")
        logger.info(json.dumps({
            "type": "rate_limit_log",
            "chat_id": message.chat.id,
            "wait_time": retry_after
        }))
        await asyncio.sleep(retry_after)
        return await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            parse_mode=parse_mode,
            reply_to_message_id=message.message_id,
            business_connection_id=business_connection_id
        )
    except TelegramBadRequest as e:
        logging.error(f"ERROR in reply_to: {e}", exc_info=True)
    return None

#!/usr/bin/env python3
from typing import Optional
from collections.abc import Callable

from telegram import Chat, Update, User, Message
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import CallbackContext

def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User):
	return user.mention_markdown_v2()

def filter_chat(chat_id: int, chat: str) -> Callable[[Callable], Callable]:
	'''
	chat_id: id of a chat
	chat: chat handle
	'''
	def decorator(function: Callable) -> Callable:
		async def wrapper(update: Update, context: CallbackContext):
			assert update.message is not None
			if update.message.chat_id != chat_id:
				await update.message.chat.send_message(
					f'''This feature only works in chat @{escape_md(chat)}

If you want to use this bot outside that group, please contact the developer: \
[@RiedleroD](tg://user?id=388037461)''',
					parse_mode=ParseMode.MARKDOWN_V2
				)
			else:
				await function(update, context)
		return wrapper
	return decorator

async def is_admin(chat: Chat, user: User) -> bool:
	# might wanna cache admins
	member = await chat.get_member(user.id)
	return member.status in ('creator', 'administrator')


async def get_reply_target(message: Message, sendback: Optional[str] = None) -> tuple[User, Message | None] | None:
	'''
	Returns the user that is supposed to be warned. It might be a bot.
	Returns None if no warn target.
	'''
	if message.reply_to_message is not None:
		if message.reply_to_message.from_user is None:
			await message.reply_text("somehow we couldn't get the user of the replied message…")
			return None
		else:
			return (message.reply_to_message.from_user, message.reply_to_message)
	if sendback is not None:
		await message.reply_text(
			f'The command /{sendback} only works when replying to someone',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	return None


async def check_admin_to_user_action(message: Message, command: str) -> Optional[User]:
	'''
	It sends message if admin to user action is not possible and returns None
	Returns user if it's possible.
	'''
	if not await is_admin(message.chat, message.from_user):
		await message.reply_text('You are not an admin', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	target = await get_reply_target(message, command)
	if target is None:
		return None
	tuser, tmsg = target
	if tuser.is_bot and tmsg.sender_chat is None:
		await message.reply_text(f'/{command} isn\'t usable on bots', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	return tuser

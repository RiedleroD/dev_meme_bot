#!/usr/bin/env python3
from sys import stderr
from typing import Optional
from collections.abc import Callable
from hashlib import md5

from telegram import Chat, Update, User, Message, Bot, MessageEntity
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import CallbackContext
from telegram.error import BadRequest, TelegramError

import database
from config import CONFIG

recent_message_links: list[tuple[int, bytes, int]] = [] # message_id, link_hash, userid

def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User) -> str:
	return user.mention_markdown_v2()

def hashdigest(text: str) -> bytes:
	return md5(text.encode('utf-8')).digest()

def filter_chat(chat_id: int, chat: str) -> Callable[[Callable], Callable]:
	'''
	chat_id: id of a chat
	chat: chat handle
	'''
	def decorator(function: Callable) -> Callable:
		async def wrapper(update: Update, context: CallbackContext) -> None:
			if update.message is None:
				return
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


async def get_reply_target(message: Message, sendback: Optional[str] = None) -> tuple[User, Message] | None:
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


async def check_admin_to_user_action(message: Message, command: str, usable_on_bots: bool = False) -> Optional[User]:
	'''
	It sends message if admin to user action is not possible and returns None
	Returns user if it's possible.
	'''
	assert message.from_user is not None

	if not await is_admin(message.chat, message.from_user):
		await message.reply_text('You are not an admin', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	target = await get_reply_target(message, command)
	if target is None:
		return None
	tuser, tmsg = target
	if (not usable_on_bots) and tuser.is_bot and tmsg.sender_chat is None:
		await message.reply_text(f'/{command} isn\'t usable on bots', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	return tuser

def remove_from_recent_messages(*args: int) -> None:
	recent_message_links[:] = [link for link in recent_message_links if link[0] not in args]

async def kick_message(
	message: Message,
	context: CallbackContext,
	db: database.UserDB,
	mark_as_spam: bool = False
) -> None:
	'''
	Removes a message, bans the user, and does all the necessary autofiltering stuff
	'''
	assert message.from_user is not None
	users_to_ban = {message.from_user.id}
	messages_to_delete = {message.id}

	# immediately delete any messages associated with this votekick to unclog chat
	messages_to_delete.update(db.pop_vk_messages(message.from_user.id))
	# get rid of deleted messages in memory so we can remember more potentially important messages
	remove_from_recent_messages(*messages_to_delete)
	try:
		if message.text is not None and len(message.text) >= CONFIG['spam_minlength']:
			autofiltered = 0
			message_links: list[str] = get_urls_from_message(message)
			for link in message_links:
				link_hash = hashdigest(link)
				link_badness = db.check_message_badness(link_hash)

				if mark_as_spam:
					link_badness += CONFIG['spam_threshhold']
				else:
					link_badness += 1

				# autofiltering stuff
				if link_badness >= CONFIG['spam_threshhold']:
					kept_links: list[tuple[int, bytes, int]] = []
					for message_id, recent_link_hash, userid in recent_message_links:
						if recent_link_hash == link_hash:
							link_badness += 1
							messages_to_delete.add(message_id)
							users_to_ban.add(userid)
							autofiltered += 1
						else:
							kept_links.append((message_id, recent_link_hash, userid))
					recent_message_links[:] = kept_links

				db.set_message_badness(link_hash, link_badness)
			if autofiltered > 0:
				plural = 's' if autofiltered >= 2 else ''
				await context.bot.send_message(message.chat.id, f"cleared {autofiltered} additional spam message{plural}")
	finally:
		remove_from_recent_messages(*messages_to_delete)
		for userid in users_to_ban:
			await ban_user(context, message.chat.id, userid, message.sender_chat)
		for message_id in messages_to_delete:
			try:
				await context.bot.delete_message(message.chat.id, message_id)
			except BadRequest as e:
				# we couldn't delete this message; no biggie. There's lots of weird restrictions on what messages can be deleted.
				print(f"couldn't delete message {message_id}: {e.message}", file=stderr)

async def ban_user(context: CallbackContext, chatid: int, userid: int, sender_chat: Chat | None) -> None:
	pass # ban_chat_sender_chat
	bot: Bot = context.bot
	if ischannel := (sender_chat is not None):
		banid = sender_chat.id
		ban = bot.ban_chat_sender_chat(chatid, sender_chat.id)
	else:
		banid = userid
		ban = bot.ban_chat_member(chatid, userid)

	try:
		await ban
	except TelegramError as e:
		print(f"couldn't ban {'channel' if ischannel else 'user'} {banid} ({e.message})", file=stderr)

def get_urls_from_message(message: Message) -> list[str]:
	urls: list[str] = []
	if not message.entities or not message.text:
		return urls
	for entity in message.entities:
		if entity.type == MessageEntity.URL:
			urls.append(get_entity_string(message.text, entity))
		if entity.type == MessageEntity.TEXT_LINK and entity.url is not None:
			urls.append(entity.url)
		if entity.type == MessageEntity.TEXT_MENTION and entity.user is not None:
			user_link = f"tg://user?id={entity.user.id}"
			urls.append(user_link)
		if entity.type == MessageEntity.MENTION:
			username = get_entity_string(message.text, entity)[1:]
			user_link = f"https://t.me/{username}"
			urls.append(user_link)
	return urls

def get_entity_string(message_text: str, entity: MessageEntity) -> str:
	utf_16_message_bytes = message_text.encode('utf-16-le')
	start_byte = entity.offset * 2
	end_byte = start_byte + entity.length * 2
	return utf_16_message_bytes[start_byte:end_byte].decode('utf-16-le')

class LBUser:
	__slot__ = ('score', 'rank', 'userid')
	userid: int
	score: int
	rank: int

	def __init__(self, userid: int, score: int, rank: int):
		self.userid = userid
		self.score = score
		self.rank = rank

class Leaderboard:
	__slots__ = ('scoremap', 'scores', 'users')
	scoremap: dict[int, int]
	scores: tuple[int, ...]
	users: tuple[LBUser, ...]

	def __init__(self, db: database.UserDB):
		self.scoremap = db.get_all_vkscores()

		userIDs = tuple(
			sorted((userid for userid in self.scoremap.keys()), key=lambda userid: self.scoremap[userid], reverse=True)
		)
		self.scores = tuple(self.scoremap[userid] for userid in userIDs)
		self.users = tuple(
			LBUser(
				userid,
				self.scoremap[userid],
				self.scores.index(self.scoremap[userid]) + 1
			)
			for userid in userIDs
		)

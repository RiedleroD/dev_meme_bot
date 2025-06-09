#!/usr/bin/env python3
from typing import Optional
from collections.abc import Callable
from hashlib import md5

from telegram import Chat, Update, User, Message
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import CallbackContext
from telegram.error import BadRequest

import database
from config import CONFIG

recent_messages: list[tuple[int, bytes, int]] = []

def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User):
	return user.mention_markdown_v2()

def hashdigest(text: str) -> bytes:
	return md5(text.encode('utf-8')).digest()

def filter_chat(chat_id: int, chat: str) -> Callable[[Callable], Callable]:
	'''
	chat_id: id of a chat
	chat: chat handle
	'''
	def decorator(function: Callable) -> Callable:
		async def wrapper(update: Update, context: CallbackContext):
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


async def check_admin_to_user_action(message: Message, command: str, usable_on_bots: bool = False) -> Optional[User]:
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
	if (not usable_on_bots) and tuser.is_bot and tmsg.sender_chat is None:
		await message.reply_text(f'/{command} isn\'t usable on bots', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	return tuser

async def kick_message(message: Message, context: CallbackContext, db: database.UserDB, mark_as_spam: bool = False):
	'''
	Removes a message, bans the user, and does all the necessary autofiltering stuff
	'''
	assert message.from_user is not None
	toban = [message.from_user.id]
	try:
		await message.delete()
	except BadRequest:
		pass # we couldn't delete this message; no biggie. There's lots of weird restrictions on what messages can be deleted.
	for i in range(len(recent_messages)):
		if recent_messages[i][0] == message.id:
			del recent_messages[i]
			break

	if message.text is None: # TODO: find out what the hell causes this
		await message.reply_text("ERROR: could not get message text (wtf?)")
	if message.text is not None and len(message.text) >= CONFIG['spam_minlength']:
		thisdigest = hashdigest(message.text)
		badness = db.check_message_badness(thisdigest)

		if mark_as_spam:
			badness += CONFIG['spam_threshhold']
		else:
			badness += 1

		# autofiltering stuff
		if badness >= CONFIG['spam_threshhold']:
			for i in range(len(recent_messages) - 1, -1, -1):
				msgid, digest, userid = recent_messages[i]
				if digest == thisdigest:
					badness += 1
					await context.bot.delete_message(message.chat.id, msgid)
					if userid not in toban:
						toban.append(userid)
					del recent_messages[i]

		db.set_message_badness(thisdigest, badness)

	for userid in toban:
		await context.bot.ban_chat_member(chat_id=message.chat.id, user_id=userid)

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

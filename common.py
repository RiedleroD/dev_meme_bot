#!/usr/bin/env python3
from sys import stderr
from typing import Literal, overload, Optional, Sequence, Self
from collections.abc import Callable
from hashlib import md5
from urllib.parse import urlparse, urlunparse
from abc import ABC, abstractmethod
from dataclasses import dataclass

from telegram import Chat, ChatFullInfo, Update, User, Message, Bot, MessageEntity
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import CallbackContext
from telegram.error import BadRequest, TelegramError

import database
from config import CONFIG

recent_message_links: list[tuple[int, bytes, 'Bannable']] = [] # message_id, link_hash, user
recent_message_users: list['BannableWithHandle'] = []
join_messages: list[tuple[int, 'BannableWithObj']] = [] # message_id, user

@dataclass
class Bannable(ABC):
	__slots__ = ('id', '_obj', 'handle')
	id: int
	_obj: User | Chat | ChatFullInfo | None
	handle: str | None

	@abstractmethod
	async def get_obj(self, bot: Bot) -> User | Chat | ChatFullInfo:
		...

	@abstractmethod
	async def with_obj(self, bot: Bot) -> 'BannableWithObj':
		...

@dataclass
class BannableWithHandle(Bannable, ABC):
	__slots__ = ()
	handle: str

@dataclass
class BannableChat(Bannable):
	__slots__ = ()
	_obj: Chat | ChatFullInfo | None

	async def get_obj(self, bot: Bot) -> Chat | ChatFullInfo:
		if self._obj is None:
			self._obj = await bot.get_chat(self.id)
		return self._obj

	async def with_obj(self, bot: Bot) -> 'BannableChatWithObj':
		return BannableChatWithObj.from_chat(await self.get_obj(bot))

	@property
	def is_bot(self) -> bool:
		return False

@dataclass
class BannableChatWithObj(BannableChat, BannableWithHandle):
	__slots__ = ()
	_obj: Chat | ChatFullInfo

	@classmethod
	def from_chat(cls, obj: Chat | ChatFullInfo) -> Self:
		assert obj.username is not None  # guaranteed
		return cls(id=obj.id, handle=obj.username.lower(), _obj=obj)

	@property
	def full_name(self) -> str:
		return self._obj.full_name or f"@{self.handle}"

	def __repr__(self) -> str:
		return f"BannableChat(@{self.handle})"

@dataclass
class BannableUser(Bannable):
	__slots__ = ()
	_obj: User | None

	async def get_obj(self, bot: Bot) -> User:
		if self._obj is None:
			self._obj = (await bot.get_chat_member(CONFIG['private_chat_id'], self.id)).user
		return self._obj

	async def with_obj(self, bot: Bot) -> 'BannableUserWithObj':
		return BannableUserWithObj.from_user(await self.get_obj(bot))

@dataclass
class BannableUserWithObj(BannableUser):
	__slots__ = ()
	_obj: User

	@classmethod
	def from_user(cls, obj: User) -> Self:
		handle = obj.username
		if handle is not None:
			handle = handle.lower()
		return cls(id=obj.id, handle=handle, _obj=obj)

	@property
	def is_bot(self) -> bool:
		return self._obj.is_bot

	@property
	def full_name(self) -> str:
		return self._obj.full_name

	def __repr__(self) -> str:
		if self.handle is not None:
			return f"BannableUser(@{self.handle})"
		else:
			return f"BannableUser({self._obj.full_name})"

@dataclass
class BannableUserWithBoth(BannableUserWithObj, BannableWithHandle):
	__slots__ = ()


type BannableWithObj = BannableUserWithObj | BannableChatWithObj


def trunc_msgmem(l: list) -> None:
	while len(l) > CONFIG['message_memory']:
		l.pop(0)

async def register_joinmsg(msg: Message) -> None:
	if (newjoinc := len(msg.new_chat_members)) != 1:
		await msg.reply_text(f"DEBUG: what the hell is this? found {newjoinc} new_chat_members: {msg.new_chat_members}")
		return
	if msg.from_user is None:
		await msg.reply_text(
			"DEBUG: HOW is this join message not from a user??"
		)
		return
	if msg.new_chat_members[0].id != msg.from_user.id:
		await msg.reply_text(
			f"DEBUG: what the fuck? new chat member {msg.new_chat_members[0].id} != {msg.from_user.id}"
		)
		return

	user: Bannable
	if msg.sender_chat is not None:
		user = BannableChatWithObj.from_chat(msg.sender_chat)
	else:
		user = BannableUserWithObj.from_user(msg.from_user)

	join_messages.append((
		msg.id,
		user,
	))
	trunc_msgmem(join_messages)

def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User | BannableWithObj) -> str:
	if isinstance(user, Bannable):
		if isinstance(user, BannableUser):
			return user._obj.mention_markdown_v2()
		elif isinstance(user, BannableChat):
			return user._obj.mention_markdown_v2()
		else:
			raise NotImplementedError("unreachable")
	else:
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

async def is_admin(chat: Chat, user: Bannable | User) -> bool:
	# might wanna cache admins
	if isinstance(user, BannableUser) or isinstance(user, User):
		member = await chat.get_member(user.id)
		return member.status in ('creator', 'administrator')

	return False


@overload
async def get_ments_from_msg(
	message: Message,
	allow_mult: Literal[True],
	sendback: str | None = None,
) -> Sequence[Bannable]:
	...

@overload
async def get_ments_from_msg(
	message: Message,
	allow_mult: Literal[False],
	sendback: str | None = None,
) -> Bannable | None:
	...

async def get_ments_from_msg(
	message: Message,
	allow_mult: bool,
	sendback: str | None = None,
) -> Bannable | Sequence[Bannable] | None:
	tusers: list[Bannable] = []
	for entity in message.entities:
		if entity.type == MessageEntity.TEXT_MENTION:
			assert entity.user is not None # should be guaranteed
			tusers.append(BannableUserWithObj.from_user(entity.user))
		elif entity.type == MessageEntity.MENTION:
			assert message.text is not None
			search_handle = get_entity_string(message.text, entity)[1:].lower()
			print(f"what is this username? {search_handle}")
			found = False
			for bannable in recent_message_users:
				if bannable.handle == search_handle:
					print(f"found! it's {bannable.id}")
					tusers.append(bannable)
					found = True
					break
			if not found:
				await message.reply_text(
					f'hmm … could not find user @{search_handle}\\. Try targetting via reply instead\\.',
					parse_mode=ParseMode.MARKDOWN_V2
				)
	if allow_mult:
		return tusers
	elif len(tusers) > 1:
		if sendback is not None:
			await message.reply_text(
				f'The command /{sendback} only allows targeting ONE user at once. this may change in the future',
				parse_mode=ParseMode.MARKDOWN_V2
			)
		return None
	elif len(tusers) > 0:
		return tusers[0]
	else:
		return None

@overload
async def get_reply_target(
	message: Message,
	sendback: str | None,
	allow_ment: Literal[True]
) -> tuple[Bannable, Message | None] | None:
	...

@overload
async def get_reply_target(
	message: Message,
	sendback: str | None = None,
	allow_ment: Literal[False] = False
) -> tuple[Bannable, Message] | None:
	...

async def get_reply_target(
	message: Message,
	sendback: str | None = None,
	allow_ment: bool = False,
) -> tuple[Bannable, Message | None] | None:
	'''
	Returns the user and message that is supposed to be targeted. It might be a bot.
	May return None if no target could be identified.

	:allow_ment: whether to allow looking through user mentions to find a target user. only allows one target for now
	'''
	if message.reply_to_message is not None:
		if message.reply_to_message.from_user is None:
			await message.reply_text("somehow we couldn't get the user of the replied message…")
			return None
		else:
			if message.reply_to_message.sender_chat is not None:
				return (BannableChatWithObj.from_chat(message.reply_to_message.sender_chat), message.reply_to_message)
			else:
				return (BannableUserWithObj.from_user(message.reply_to_message.from_user), message.reply_to_message)
	elif allow_ment:
		# if the message isn't a reply, try finding mentions in the message
		tuser = await get_ments_from_msg(message, False, sendback)
		if tuser is not None:
			return (tuser, None)

	if sendback is not None:
		desc = 'reply to a message' if not allow_ment else 'reply to a message or tag a user'
		await message.reply_text(
			f'The command /{sendback} needs a target \\({desc}\\)',
			parse_mode=ParseMode.MARKDOWN_V2
		)

	return None


async def check_admin_to_user_action(
	message: Message,
	command: str,
	usable_on_bots: bool = False
) -> Optional[Bannable]:
	'''
	It sends message if admin to user action is not possible and returns None
	Returns user if it's possible.
	'''
	assert message.from_user is not None

	if not await is_admin(message.chat, message.from_user):
		await message.reply_text('You are not an admin', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	target = await get_reply_target(message, command, True)
	if target is None:
		return None
	tuser, tmsg = target
	if (not usable_on_bots) and (await tuser.get_obj(message.get_bot())).is_bot \
		and (tmsg is None or tmsg.sender_chat is None):
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
	users_to_ban: set[int] = set()
	chats_to_ban: set[int] = set()
	messages_to_delete = {message.id}

	# ban all easily associated users
	# NOTE: possibly to consider in the future: message.sender_business_bot
	associd: int
	if message.sender_chat is not None:
		associd = message.sender_chat.id
		chats_to_ban.add(message.sender_chat.id)
	elif message.from_user is not None:
		associd = message.from_user.id
		users_to_ban.add(message.from_user.id)
	else:
		raise Exception("could not associate kicked message with any user or channel-user")

	for attrname in ('guest_bot_caller_user', 'guest_bot_caller_user', 'guest_bot_caller_chat', 'guest_bot_caller_chat'):
		maybeuser: User | Chat | None
		if (maybeuser := getattr(message, attrname)) is not None:
			if isinstance(maybeuser, User):
				users_to_ban.add(maybeuser.id)
			elif isinstance(maybeuser, Chat):
				chats_to_ban.add(maybeuser.id)
			else:
				... # unreachable
	# immediately delete any messages associated with this votekick to unclog chat
	messages_to_delete.update(db.pop_vk_messages(associd))
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
					for message_id, recent_link_hash, bannable in recent_message_links:
						if recent_link_hash == link_hash:
							link_badness += 1
							messages_to_delete.add(message_id)
							if isinstance(bannable, BannableChat):
								chats_to_ban.add(bannable.id)
							else:
								users_to_ban.add(bannable.id)
							autofiltered += 1

				db.set_message_badness(link_hash, link_badness)
			if autofiltered > 0:
				plural = 's' if autofiltered >= 2 else ''
				await context.bot.send_message(message.chat.id, f"cleared {autofiltered} additional spam message{plural}")
	finally:
		for userid in users_to_ban:
			await ban_user(context, message.chat.id, BannableUser(userid, None, None))
		for chatid in chats_to_ban:
			await ban_user(context, message.chat.id, BannableChat(chatid, None, None))
		for message_id in messages_to_delete:
			try:
				await context.bot.delete_message(message.chat.id, message_id)
			except BadRequest as e:
				# we couldn't delete this message; no biggie. There's lots of weird restrictions on what messages can be deleted.
				print(f"couldn't delete message {message_id}: {e.message}", file=stderr)

async def ban_user(
	context: CallbackContext,
	chatid: int,
	bannable: Bannable,
	del_messages: bool = False,
) -> None:
	bot: Bot = context.bot
	if ischannel := isinstance(bannable, BannableChat):
		ban = bot.ban_chat_sender_chat(chatid, bannable.id)
	else:
		ban = bot.ban_chat_member(chatid, bannable.id, revoke_messages=del_messages)

	try:
		await ban
	except TelegramError as e:
		print(
			f"couldn't ban {'channel' if ischannel else 'user'} {bannable} ({e.message})",
			file=stderr
		)

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

	normalized_urls = [normalize_url(url) for url in urls if url]
	return normalized_urls

def normalize_url(url: str) -> str:
	if not url:
		return url
	parsed = urlparse(url)
	if parsed.scheme == '' or parsed.scheme == "http":
		parsed = parsed._replace(scheme='https')
	parsed = parsed._replace(netloc=parsed.netloc.lower())
	return urlunparse(parsed)

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

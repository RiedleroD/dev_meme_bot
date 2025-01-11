#!/usr/bin/env python3
from os import path
import sys
from datetime import datetime
from typing import Optional
from collections.abc import Callable
import json

from telegram import Update, Chat, User, Message
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters
from telegram.helpers import escape_markdown
from telegram.error import BadRequest
import database

print("reading config")
CURDIR = path.dirname(sys.argv[0])
CONFPATH = path.join(CURDIR, 'config.json')
if not path.exists(CONFPATH):
	with open(CONFPATH, 'w') as f:
		config = {
			'token': 'Your token goes here',
			'private_chat_id': -1001218939335,
			'private_chat_username': 'devs_chat',
			'database_path': 'memebot.db'
		}
		json.dump(config, f, indent=2)
		print(f'Config was created in {CONFPATH}, please edit it')
		sys.exit(0)

with open(CONFPATH) as f:
	CONFIG = json.load(f)

private_chat_id = CONFIG['private_chat_id']
private_chat_username = CONFIG['private_chat_username']
DB_PATH = path.join(CURDIR, CONFIG['database_path'])

print('loading/creating database')
db = database.UserDB(DB_PATH)

print("initializing commands")
application = Application.builder().token(CONFIG["token"]).build()


def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)


def get_mention(user: User):
	return user.mention_markdown_v2()


def on_command(name: str) -> Callable[[Callable], Callable]:
	def add_it(func: Callable) -> Callable:
		application.add_handler(CommandHandler(name, func))
		return func
	return add_it


def on_message(filters: filters.BaseFilter) -> Callable[[Callable], Callable]:
	def add_it(func: Callable) -> Callable:
		application.add_handler(MessageHandler(filters, func))
		return func
	return add_it


def filter_chat(chat_id: int, chat: str) -> Callable[[Callable], Callable]:
	'''
	chat_id: id of a chat
	chat: chat handle
	'''
	def decorator(function: Callable) -> Callable:
		async def wrapper(update: Update, context: CallbackContext):
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


@on_command("ping")
async def ping(update: Update, _context: CallbackContext):
	dt = datetime.now(update.message.date.tzinfo) - update.message.date
	await update.message.reply_text(f'Ping is {dt.total_seconds():.2f}s')


@on_message(filters.StatusUpdate.NEW_CHAT_MEMBERS)
@filter_chat(private_chat_id, private_chat_username)
async def new_chat_member(update: Update, _context: CallbackContext):
	handles = ", ".join(get_mention(member) for member in update.message.new_chat_members)
	await update.message.reply_text(
		f"""{handles},
いらっしゃいませ\\! \\[Welcome\\!\\]
Welcome to this chat\\! Please read the rules\\.
Добро пожаловать в чат\\! Прочти правила, пожалуйста\\.
このチャットへようこそ！ ルールをお読みください。

[rules](https://t\\.me/dev\\_meme/3667)""",
		parse_mode=ParseMode.MARKDOWN_V2
	)


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


@on_command("warn")
@filter_chat(private_chat_id, private_chat_username)
async def warn_member(update: Update, _context: CallbackContext):
	target = await check_admin_to_user_action(update.message, 'warn')
	if target is None:
		return

	warns = db.get_warns(target.id) + 1
	db.set_warns(target.id, warns)
	await update.message.chat.send_message(
		f'*{get_mention(target)}* recieved a warn\\! Now they have {warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("unwarn")
@filter_chat(private_chat_id, private_chat_username)
async def unwarn_member(update: Update, _context: CallbackContext):
	target = await check_admin_to_user_action(update.message, 'unwarn')
	if target is None:
		return

	warns = db.get_warns(target.id)
	if warns > 0:
		warns -= 1
	db.set_warns(target.id, warns)
	reply = f'*{get_mention(target)}* has been a good hooman\\! '
	if warns == 0:
		reply += 'Now they don\'t have any warns'
	else:
		reply += f'Now they have {warns} warns'
	await update.message.chat.send_message(reply, parse_mode=ParseMode.MARKDOWN_V2)


@on_command("clearwarns")
@filter_chat(private_chat_id, private_chat_username)
async def clear_member_warns(update: Update, _context: CallbackContext):
	target = await check_admin_to_user_action(update.message, 'clearwarns')
	if target is None:
		return

	db.set_warns(target.id, 0)
	await update.message.chat.send_message(
		f"*{get_mention(target)}*'s warns were cleared",
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("warns")
@filter_chat(private_chat_id, private_chat_username)
async def get_member_warns(update: Update, _context: CallbackContext):
	target = await get_reply_target(update.message)
	if target is not None:
		tuser, tmsg = target
	if target is None or tuser.id == update.message.from_user.id:
		warns = db.get_warns(update.message.from_user.id)
		await update.message.reply_text(
			f'You have {"no" if warns == 0 else warns} warns',
			parse_mode=ParseMode.MARKDOWN_V2
		)
		return
	warns = db.get_warns(tuser.id)
	if tuser.is_bot and tmsg.sender_chat is None:
		await update.message.reply_text("Bots don't have warns", parse_mode=ParseMode.MARKDOWN_V2)
		return

	await update.message.reply_text(
		f'*{escape_md(tuser.full_name)}* has {"no" if warns == 0 else warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("trust")
@filter_chat(private_chat_id, private_chat_username)
async def add_trusted_user(update: Update, _context: CallbackContext):
	target = await check_admin_to_user_action(update.message, 'trust')
	if target is None:
		return

	trusted = db.get_trusted(target.id)
	if trusted:
		await update.message.chat.send_message(
			f'*{get_mention(target)}* is already trusted, silly',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	else:
		db.set_trusted(target.id, True)
		if await is_admin(update.message.chat, target):
			await update.message.chat.send_message(
				f'*{get_mention(target)}* is already a moderater, but sure lmao',
				parse_mode=ParseMode.MARKDOWN_V2
			)
		else:
			await update.message.chat.send_message(
				f'*{get_mention(target)}* is now amongst the ranks of the **Trusted Users**\\!',
				parse_mode=ParseMode.MARKDOWN_V2
			)


@on_command("untrust")
@filter_chat(private_chat_id, private_chat_username)
async def del_trusted_user(update: Update, _context: CallbackContext):
	target = await check_admin_to_user_action(update.message, 'untrust')
	if target is None:
		return

	trusted = db.get_trusted(target.id)
	if not trusted:
		await update.message.chat.send_message(
			f'*{get_mention(target)}* wasn\'t trusted in the first place',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	else:
		db.set_trusted(target.id, False)
		if await is_admin(update.message.chat, target):
			await update.message.chat.send_message(
				f'*{get_mention(target)}* is a moderater, but sure lmao',
				parse_mode=ParseMode.MARKDOWN_V2
			)
		else:
			await update.message.chat.send_message(
				f'*{get_mention(target)}* has fallen off hard, no cap on god frfr',
				parse_mode=ParseMode.MARKDOWN_V2
			)


@on_command("votekick")
@on_command("kickvote")
@filter_chat(private_chat_id, private_chat_username)
async def votekick(update: Update, context: CallbackContext):
	target = await get_reply_target(update.message, 'votekick')
	if target is None:
		return
	tuser, tmsg = target
	voter = update.message.from_user
	chat = update.message.chat

	if tuser.id == 777000:
		if (db.get_trusted(voter.id) or await is_admin(chat, voter)):
			await update.message.reply_text(
				"You can't votekick the channel…",
				parse_mode=ParseMode.MARKDOWN_V2
			)
		else:
			await update.message.delete()
	elif not (db.get_trusted(voter.id) or await is_admin(chat, voter)):
		await update.message.reply_text(
			'Only trusted users can votekick someone',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	elif db.get_trusted(tuser.id):
		await update.message.reply_text(
			'You can\'t votekick another trusted user',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	elif await is_admin(chat, tuser):
		await update.message.reply_text(
			'You can\'t votekick an admin',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	else:
		db.add_votekick(voter.id, tuser.id)
		votes = db.get_votekicks(tuser.id)
		appendix = "\nthat constitutes a ban\\!" if votes >= 3 else ""
		await update.message.reply_text(
			f'User {get_mention(tuser)} now has {votes}/3 votes against them\\.{appendix}',
			parse_mode=ParseMode.MARKDOWN_V2
		)
		if votes >= 3:
			await context.bot.ban_chat_member(chat_id=chat.id, user_id=tuser.id)
			# NOTE: bot API doesn't support deleting all messages by a user, so we only delete the last
			# message. This is irreversible, but /votekick has worked well and hasn't been abused so far. As
			# it's mostly used to combat spam, enabling this seems fine.
			try:
				await update.message.reply_to_message.delete()
			except BadRequest:
				pass # we couldn't delete this message; no biggie. There's lots of asinine restrictions on what messages can be deleted.


print("starting polling")
application.run_polling()
print("exiting")

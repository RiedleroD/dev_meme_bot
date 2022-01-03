#!/usr/bin/env python3
print("loading libs")
from os import chdir,path
from sys import argv
from datetime import datetime
from typing import NamedTuple
from threading import Event, Thread
import json

from telegram import Update, ParseMode, Chat, User
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from telegram.ext.filters import Filters
from telegram.message import Message
from telegram.utils.helpers import escape_markdown
import database


private_chat_id = -1001218939335
private_chat_username = 'devs_chat'

print('loading/creating database')
DB_PATH = 'memebot.db'
db = database.UserDB(DB_PATH)

def save_db():
	global db
	if db.changed:
		print('saving database')
		db.changed = False
		db.dump()

class SaverThread(Thread):
	'''
	Class silimar to threading.Timer, but where Timer runs only once, this class runs function multiple times

	To stop the loop, use function set on passed event: event.set()
	'''

	def __init__(self, event: Event, interval: float):
		Thread.__init__(self)
		self.stopped = event
		self.interval = interval

	def run(self):
		while not self.stopped.wait(self.interval):
			save_db()

print('creating saving timer')
SAVE_INTERVAL = 5 * 60 # 5 minutes
stop_saving_flag = Event()
save_timer = SaverThread(stop_saving_flag, SAVE_INTERVAL)
save_timer.start()

print("reading config")
CURDIR=path.dirname(argv[0])
with open(path.join(CURDIR,"./config.json"),"r") as f:
	CONFIG=json.load(f)

print("initializing commands")

updater=Updater(CONFIG["TOKEN"])

def command(name:str):#some python magic
	def add_it(func):
		updater.dispatcher.add_handler(CommandHandler(name, func))
	return add_it

def message(filters):
	def add_it(func):
		updater.dispatcher.add_handler(MessageHandler(filters,func))
	return add_it

def filter_chat(id, chat):
	'''
	id: id of a chat
	chat: @<chat> without @
	'''
	def decorator(function):
		def wrapper(update: Update, context: CallbackContext):
			if update.message.chat_id != id:
				update.message.chat.send_message(f'This feature only works in chat @{chat}')
				return
			return function(update, context)
		return wrapper
	return decorator


@command("ping")
def ping(update: Update, context: CallbackContext):
	dt=datetime.now(update.message.date.tzinfo)-update.message.date
	update.message.reply_text(f'Ping is {dt.total_seconds():.2f}s')

def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User):
	return user.mention_markdown_v2()

@message(Filters.status_update.new_chat_members)
def new_chat_member(update: Update, context: CallbackContext):
	handles=", ".join(get_mention(user) for user in update.message.new_chat_members)
	update.message.reply_text(
f"""{handles},
いらっしゃいませ\\! \\[Welcome\\!\\]
Welcome to this chat\\! Please read the rules\\.
Добро пожаловать в чат\\! Прочти правила, пожалуйста\\.
このチャットへようこそ！ ルールをお読みください。

[rules](https://t\\.me/dev\\_meme/3667)""",
parse_mode=ParseMode.MARKDOWN_V2)

def is_admin(chat: Chat, user: User) -> bool:
	# might wanna cache admins
	status = chat.get_member(user.id).status
	return status == 'creator' or status == 'administrator'

def get_warn_target(message: Message) -> User | None:
	'''
	Returns the user that is supposed to be warned. It might be a bot.
	Returns None if no warn target.
	'''
	if message.reply_to_message is not None and message.reply_to_message.from_user is not None:
		return message.reply_to_message.from_user
	return None

class WarnPossibleResult(NamedTuple):
	'''
	can_warn -> can warn happen (user is admin, user is not a bot, warn target isnt bot)
	reason -> reason why warn cannot happen, might be None
	'''
	is_possible: bool
	reason: str | None

def is_warn_possible(message: Message, command: str) -> WarnPossibleResult:
	if message.from_user.is_bot: # might be redundant
		return WarnPossibleResult(False, None)
	if not is_admin(message.chat, message.from_user):
		return WarnPossibleResult(False, f'You are not an admin')
	target = get_warn_target(message)
	if target is None:
		return WarnPossibleResult(False, f'Please reply to a message with /{command}')
	if target.is_bot:
		return WarnPossibleResult(False, f'Bots cannot be warned')
	return WarnPossibleResult(True, None)

@command("warn")
@filter_chat(private_chat_id, private_chat_username)
def warn_member(update: Update, context: CallbackContext):
	warn_pos = is_warn_possible(update.message, 'warn')
	if not warn_pos.is_possible:
		if warn_pos.reason is not None:
			update.message.reply_text(warn_pos.reason, parse_mode=ParseMode.MARKDOWN_V2)
		return
	target = get_warn_target(update.message)
	userid = target.id
	warns = db.get_warns(userid) + 1
	db.set_warns(userid, warns)
	update.message.chat.send_message(
		f'*{get_mention(target)}* recieved a warn\\! Now they have {warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("unwarn")
@filter_chat(private_chat_id, private_chat_username)
def unwarn_member(update: Update, context: CallbackContext):
	can_warn = is_warn_possible(update.message, 'unwarn')
	if not can_warn.is_possible:
		if can_warn.reason is not None:
			update.message.reply_text(can_warn.reason, parse_mode=ParseMode.MARKDOWN_V2)
		return
	target = get_warn_target(update.message)
	userid = target.id
	warns = db.get_warns(userid)
	if warns > 0:
		warns -= 1
	db.set_warns(userid, warns)
	reply = f'*{target.mention_markdown_v2()}* been a good hooman\\! '
	if warns == 0:
		reply += 'Now they don\'t have any warns'
	else:
		reply += f'Now they have {warns} warns'
	update.message.chat.send_message(reply,
		parse_mode=ParseMode.MARKDOWN_V2)

@command("clearwarns")
@filter_chat(private_chat_id, private_chat_username)
def unwarn_member(update: Update, context: CallbackContext):
	can_warn = is_warn_possible(update.message, 'clearwarns')
	if not can_warn.is_possible:
		if can_warn.reason is not None:
			update.message.reply_text(can_warn.reason, parse_mode=ParseMode.MARKDOWN_V2)
		return
	target = get_warn_target(update.message)
	db.set_warns(target.id, 0)
	update.message.chat.send_message(f'*{target.mention_markdown_v2()}*\'s warns were cleared',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("warns")
@filter_chat(private_chat_id, private_chat_username)
def warns_member(update: Update, context: CallbackContext):
	if update.message.from_user.is_bot: # might be redundant
		return
	target = get_warn_target(update.message)
	if target is None or target.id == update.message.from_user.id:
		warns = db.get_warns(update.message.from_user.id)
		update.message.reply_text(f'You have {"no" if warns == 0 else warns} warns',
			parse_mode=ParseMode.MARKDOWN_V2)
		return
	warns = db.get_warns(target.id)
	if target.is_bot:
		update.message.reply_text(f'Bots don\'t have warns',
			parse_mode=ParseMode.MARKDOWN_V2)
		return
	update.message.reply_text(
		f'*{escape_md(target.full_name)}* has {"no" if warns == 0 else warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2)


try:
	print("starting polling")
	updater.start_polling()
	print("online")
	updater.idle()
finally:
	stop_saving_flag.set()
	save_db()
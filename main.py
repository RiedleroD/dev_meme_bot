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

print("reading config")
CURDIR=path.dirname(argv[0])
CONFDIR=path.join(CURDIR,'./config.json')
if not path.exists(CONFDIR):
	with open(CONFDIR,'w') as f:
		config = {
			'token': 'Your token goes here',
			'private_chat_id': -1001218939335,
			'private_chat_username': 'devs_chat',
			'database_save_interval': 5 * 60,
			'database_path': 'memebot.db'
		}
		json.dump(config, f, indent=2)
		print(f'Config was created in {CONFDIR}, please edit it')
		exit(0)
with open(CONFDIR,"r") as f:
	CONFIG=json.load(f)

private_chat_id = CONFIG['private_chat_id']
private_chat_username = CONFIG['private_chat_username']
SAVE_INTERVAL = CONFIG['database_save_interval']
DB_PATH = path.join(CURDIR,CONFIG['database_path'])

print('loading/creating database')
db = database.UserDB(DB_PATH)

def save_db():
	global db
	if db.changed:
		print('saving database')
		db.changed = False
		db.dump()

class SaverThread(Thread):
	'''
	Class silimar to threading.Timer, but where Timer runs only once,
	this class runs function multiple times with interval

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
stop_saving_flag = Event()
save_timer = SaverThread(stop_saving_flag, SAVE_INTERVAL)
save_timer.start()

print("initializing commands")
updater=Updater(CONFIG["token"])


def escape_md(txt: str) -> str:
	return escape_markdown(txt, 2)

def get_mention(user: User):
	return user.mention_markdown_v2()

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
				update.message.chat.send_message(f'''This feature only works in chat @{escape_md(chat)}

If you want to use this bot outside that group, please contact the developer: [@RiedleroD](tg://user?id=388037461)''',
parse_mode=ParseMode.MARKDOWN_V2)
				return
			return function(update, context)
		return wrapper
	return decorator


@command("ping")
def ping(update: Update, context: CallbackContext):
	dt=datetime.now(update.message.date.tzinfo)-update.message.date
	update.message.reply_text(f'Ping is {dt.total_seconds():.2f}s')

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

def get_reply_target(message: Message) -> User | None:
	'''
	Returns the user that is supposed to be warned. It might be a bot.
	Returns None if no warn target.
	'''
	if message.reply_to_message != None:
		return message.reply_to_message.from_user
	return None

def is_warn_possible(message: Message, command: str) -> bool:
	'''
	It sends message if warn is not possible
	Returns True/False if warn is possible.
	'''
	if not is_admin(message.chat, message.from_user):
		message.reply_text(f'You are not an admin', parse_mode=ParseMode.MARKDOWN_V2)
		return False
	target = get_reply_target(message)
	if target == None:
		message.reply_text(f'Please reply to a message with /{command}', parse_mode=ParseMode.MARKDOWN_V2)
		return False
	if target.is_bot:
		message.reply_text(f'Bots cannot be warned', parse_mode=ParseMode.MARKDOWN_V2)
		return False
	return True

@command("warn")
@filter_chat(private_chat_id, private_chat_username)
def warn_member(update: Update, context: CallbackContext):
	if not is_warn_possible(update.message, 'warn'):
		return
	target = get_reply_target(update.message)
	warns = db.get_warns(target.id) + 1
	db.set_warns(target.id, warns)
	update.message.chat.send_message(
		f'*{get_mention(target)}* recieved a warn\\! Now they have {warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("unwarn")
@filter_chat(private_chat_id, private_chat_username)
def unwarn_member(update: Update, context: CallbackContext):
	if not is_warn_possible(update.message, 'unwarn'):
		return
	target = get_reply_target(update.message)
	warns = db.get_warns(target.id)
	if warns > 0:
		warns -= 1
	db.set_warns(target.id, warns)
	reply = f'*{target.mention_markdown_v2()}* has been a good hooman\\! '
	if warns == 0:
		reply += 'Now they don\'t have any warns'
	else:
		reply += f'Now they have {warns} warns'
	update.message.chat.send_message(reply,
		parse_mode=ParseMode.MARKDOWN_V2)

@command("clearwarns")
@filter_chat(private_chat_id, private_chat_username)
def clear_member_warns(update: Update, context: CallbackContext):
	if not is_warn_possible(update.message, 'clearwarns'):
		return
	target = get_reply_target(update.message)
	db.set_warns(target.id, 0)
	update.message.chat.send_message(f'*{target.mention_markdown_v2()}*\'s warns were cleared',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("warns")
@filter_chat(private_chat_id, private_chat_username)
def warns_member(update: Update, context: CallbackContext):
	target = get_reply_target(update.message)
	if target == None or target.id == update.message.from_user.id:
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
#!/usr/bin/env python3
print("loading libs")
from os import path
from sys import argv
from datetime import datetime
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
CONFPATH=path.join(CURDIR,'./config.json')
if not path.exists(CONFPATH):
	with open(CONFPATH,'w') as f:
		config = {
			'token': 'Your token goes here',
			'private_chat_id': -1001218939335,
			'private_chat_username': 'devs_chat',
			'database_save_interval': 5 * 60,
			'database_path': 'memebot.db'
		}
		json.dump(config, f, indent=2)
		print(f'Config was created in {CONFPATH}, please edit it')
		exit(0)

with open(CONFPATH,"r") as f:
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

class SaveTimer(Thread):
	'''
	Class silimar to threading.Timer, but where Timer runs only once,
	this class runs save function periodically, like Timer in Delphi or
	setInterval() in js.

	To stop the loop, use function stop()
	'''

	def __init__(self, interval: float):
		Thread.__init__(self)
		self.stopped = Event()
		self.interval = interval

	def run(self):
		while not self.stopped.wait(self.interval):
			save_db()
	
	def stop(self):
		self.stopped.set()

print('creating saving timer')
save_timer = SaveTimer(SAVE_INTERVAL)
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
		return func
	return add_it

def message(filters):
	def add_it(func):
		updater.dispatcher.add_handler(MessageHandler(filters,func))
	return add_it

def filter_chat(id: int, chat: str):
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
@filter_chat(private_chat_id, private_chat_username)
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

def get_reply_target(message: Message, sendback: str|None = None) -> User | None:
	'''
	Returns the user that is supposed to be warned. It might be a bot.
	Returns None if no warn target.
	'''
	if message.reply_to_message is not None:
		return message.reply_to_message.from_user
	if sendback is not None:
		message.reply_text(f'Please reply to a message with /{sendback}', parse_mode=ParseMode.MARKDOWN_V2)
	return None

def check_admin_to_user_action(message: Message, command: str) -> User | None:
	'''
	It sends message if admin to user action is not possible and returns None
	Returns user if it's possible.
	'''
	if not is_admin(message.chat, message.from_user):
		message.reply_text(f'You are not an admin', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	target = get_reply_target(message, command)
	if target is None:
		return None
	if target.is_bot:
		message.reply_text(f'/{command} isn\'t usable on bots', parse_mode=ParseMode.MARKDOWN_V2)
		return None
	return target

@command("warn")
@filter_chat(private_chat_id, private_chat_username)
def warn_member(update: Update, context: CallbackContext):
	target = check_admin_to_user_action(update.message, 'warn')
	if target is None:
		return
	
	warns = db.get_warns(target.id) + 1
	db.set_warns(target.id, warns)
	update.message.chat.send_message(
		f'*{get_mention(target)}* recieved a warn\\! Now they have {warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("unwarn")
@filter_chat(private_chat_id, private_chat_username)
def unwarn_member(update: Update, context: CallbackContext):
	target = check_admin_to_user_action(update.message, 'unwarn')
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
	update.message.chat.send_message(reply,
		parse_mode=ParseMode.MARKDOWN_V2)

@command("clearwarns")
@filter_chat(private_chat_id, private_chat_username)
def clear_member_warns(update: Update, context: CallbackContext):
	target = check_admin_to_user_action(update.message, 'clearwarns')
	if target is None:
		return
	
	db.set_warns(target.id, 0)
	update.message.chat.send_message(f"*{get_mention(target)}*'s warns were cleared",
		parse_mode=ParseMode.MARKDOWN_V2)

@command("warns")
@filter_chat(private_chat_id, private_chat_username)
def get_member_warns(update: Update, context: CallbackContext):
	target = get_reply_target(update.message)
	if target is None or target.id == update.message.from_user.id:
		warns = db.get_warns(update.message.from_user.id)
		update.message.reply_text(f'You have {"no" if warns == 0 else warns} warns',
			parse_mode=ParseMode.MARKDOWN_V2)
		return
	warns = db.get_warns(target.id)
	if target.is_bot:
		update.message.reply_text(f"Bots don't have warns",
			parse_mode=ParseMode.MARKDOWN_V2)
		return
	
	update.message.reply_text(
		f'*{escape_md(target.full_name)}* has {"no" if warns == 0 else warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2)

@command("trust")
@filter_chat(private_chat_id, private_chat_username)
def add_trusted_user(update: Update, context: CallbackContext):
	target = check_admin_to_user_action(update.message, 'trust')
	if target is None:
		return
	
	trusted = db.get_trusted(target.id)
	if trusted:
		update.message.chat.send_message(
			f'*{get_mention(target)}* is already trusted, silly',
			parse_mode=ParseMode.MARKDOWN_V2)
	else:
		db.set_trusted(target.id, True)
		if is_admin(update.message.chat, target):
			update.message.chat.send_message(
				f'*{get_mention(target)}* is already a moderater, but sure lmao',
				parse_mode=ParseMode.MARKDOWN_V2)
		else:
			update.message.chat.send_message(
				f'*{get_mention(target)}* is now amongst the ranks of the **Trusted Users**\\!',
				parse_mode=ParseMode.MARKDOWN_V2)

@command("untrust")
@filter_chat(private_chat_id, private_chat_username)
def del_trusted_user(update: Update, context: CallbackContext):
	target = check_admin_to_user_action(update.message, 'untrust')
	if target is None:
		return
	
	trusted = db.get_trusted(target.id)
	if not trusted:
		update.message.chat.send_message(
			f'*{get_mention(target)}* wasn\'t trusted in the first place',
			parse_mode=ParseMode.MARKDOWN_V2)
	else:
		db.set_trusted(target.id, False)
		if is_admin(update.message.chat, target):
			update.message.chat.send_message(
				f'*{get_mention(target)}* is a moderater, but sure lmao',
				parse_mode=ParseMode.MARKDOWN_V2)
		else:
			update.message.chat.send_message(
				f'*{get_mention(target)}* has fallen off hard, no cap on god frfr',
				parse_mode=ParseMode.MARKDOWN_V2)

@command("votekick")
@command("kickvote")
@filter_chat(private_chat_id, private_chat_username)
def votekick(update: Update, context: CallbackContext):
	target = get_reply_target(update.message, 'votekick')
	if target is None:
		return
	voter = update.message.from_user
	chat = update.message.chat
	
	if not (db.get_trusted(voter.id) or is_admin(chat,voter)):
		update.message.reply_text(
			f'Only trusted users can votekick someone\\. Sucks to suck 🤷',
			parse_mode=ParseMode.MARKDOWN_V2)
	elif db.get_trusted(target.id):
		update.message.reply_text(
			f'You can\'t votekick another trusted user',
			parse_mode=ParseMode.MARKDOWN_V2)
	elif is_admin(chat,target):
		update.message.reply_text(
			f'You can\'t votekick an admin',
			parse_mode=ParseMode.MARKDOWN_V2)
	else:
		db.add_votekick(voter.id,target.id)
		votes = db.get_votekicks(target.id)
		appendix = "\nthat constitutes a ban\\!" if votes>=3 else ""
		update.message.reply_text(
			f'User {get_mention(target)} now has {votes}/3 votes against them\\.{appendix}',
			parse_mode=ParseMode.MARKDOWN_V2)
		if votes >= 3:
			#NOTE: deleting all messages from a user might be a bit harsh, since it's irreversible, so I've turned it off for now.
			# if in the future we have serious problems with spam floods, this can be turned on again
			context.bot.ban_chat_member(chat_id=chat.id,user_id=target.id,revoke_messages=False)

try:
	print("starting polling")
	updater.start_polling()
	print("online")
	updater.idle()
finally:
	save_timer.stop()
	save_db()
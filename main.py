#!/usr/bin/env python3
print("loading libs")
from os import chdir,path
from sys import argv
from datetime import datetime
import json

import telegram
from telegram import Update, ParseMode, Chat, User
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from telegram.ext.filters import Filters
from telegram.message import Message
import database

print('loading/creating database')
db = database.UserDB()

def is_admin(chat: Chat, user: User):
	# might wanna cache admins
	status = chat.get_member(user.id).status
	return status == 'creator' or status == 'administrator'

def get_warn_target(message: Message):
	if message.reply_to_message is not None:
		return message.reply_to_message.from_user
	return None

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

@command("ping")
def ping(update: Update, context: CallbackContext):
	dt=datetime.now(update.message.date.tzinfo)-update.message.date
	update.message.reply_text(f'Ping is {dt.total_seconds():.2f}s')

#taken from https://core.telegram.org/bots/api#markdownv2-style
ESCAPE_CHARS = "_*[]`~@()><#+-=|{}.!\\"
def escape_md(txt: str) -> str:
	ans = []
	for el in txt:
		if el in ESCAPE_CHARS:
			ans.append("\\")
		ans.append(el)
	return ''.join(ans)

def get_mention(user):
	if user.username == None:
		return f"[{escape_md(user.first_name)}](tg://user?id={user.id})"
	else:
		return "@"+escape_md(user.username)

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

@command("warn")
def warn_member(update: Update, context: CallbackContext):
	if update.message.from_user.is_bot: # might be redundant
		return
	target = get_warn_target(update.message)
	if target is None:
		update.message.reply_text(f'Please reply to a message with /warn')
		return
	if target.is_bot:
		update.message.reply_text(f'You cannot warn a bot')
		return
	if not is_admin(update.message.chat, update.message.from_user):
		update.message.reply_text(f'You are not an admin')
		return
	userid = target.id
	warns = db.get_warns(userid) + 1
	db.set_warns(userid, warns)
	update.message.reply_to_message.reply_text(
		f'You recieved a warn!\nNow you have {warns} warns.')

@command("unwarn")
def unwarn_member(update: Update, context: CallbackContext):
	if update.message.from_user.is_bot: # might be redundant
		return
	target = get_warn_target(update.message)
	if target is None:
		update.message.reply_text(f'Please reply to a message with /unwarn')
		return
	if target.is_bot:
		update.message.reply_text(f'Bots do not have warns')
		return
	if not is_admin(update.message.chat, update.message.from_user):
		update.message.reply_text(f'You are not an admin')
		return
	userid = target.id
	warns = db.get_warns(userid)
	if warns > 0: warns -= 1
	db.set_warns(userid, warns)
	reply = f'You\'ve been a good hooman!\n'
	if warns == 0:
		reply += 'Now you don\'t have any warns.'
	else:
		reply += f'Now you have {warns} warns.'
	update.message.reply_to_message.reply_text(reply)

@command("clearwarns")
def unwarn_member(update: Update, context: CallbackContext):
	if update.message.from_user.is_bot: # might be redundant
		return
	target = get_warn_target(update.message)
	if target is None:
		update.message.reply_text(f'Please reply to a message with /clearwarns')
		return
	if target.is_bot:
		update.message.reply_text(f'Bots do not have warns')
		return
	if not is_admin(update.message.chat, update.message.from_user):
		update.message.reply_text(f'You are not an admin')
		return
	userid = target.id
	warns = 0
	db.set_warns(userid, warns)
	reply = f'You\'ve been a good hooman!\nNow you don\'t have any warns.'
	update.message.reply_to_message.reply_text(reply)

@command("warns")
def warns_member(update: Update, context: CallbackContext):
	if update.message.from_user.is_bot: # might be redundant
		return
	target = get_warn_target(update.message)
	if target is None:
		userid = update.message.from_user.id
		warns = db.get_warns(userid)
		update.message.reply_text(f'You have {warns} warns.')
		return
	if target.is_bot:
		update.message.reply_text(f'Bots do not have warns')
		return
	warns = db.get_warns(target.id)
	update.message.reply_text(f'They have {warns} warns.')

try:
	print("starting polling")
	updater.start_polling()
	print("online")
	updater.idle()
finally:
	db.dump()
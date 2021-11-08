#!/usr/bin/env python3
print("loading libs")
from os import chdir,path
from sys import argv
from datetime import datetime
import json

from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from telegram.ext.filters import Filters

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
escape_chars = "_*[]`~@()><#+-=|{}.!\\"
def escape_md(txt: str) -> str:
	ans = []
	for el in txt:
		if el in escape_chars:
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

print("starting polling")
updater.start_polling()
print("online")
updater.idle()

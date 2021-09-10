#!/usr/bin/env python3
print("loading libs")
from os import chdir,path
from sys import argv
from datetime import datetime
import json

from telegram import Update
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

@message(Filters.status_update.new_chat_members)
def new_chat_member(update: Update, context: CallbackContext):
	handles=", ".join(user.username for user in update.message.new_chat_members)
	update.message.reply_text(
f"""{handles},
いらっしゃいませ! [Welcome!]
Welcome to this chat! Please read the rules.
Добро пожаловать в чат! Прочти правила, пожалуйста.
このチャットへようこそ！ ルールをお読みください。

https://t.me/dev_meme/3667""")

print("starting polling")
updater.start_polling()
print("online")
updater.idle()
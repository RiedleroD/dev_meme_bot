from collections.abc import Callable

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, Application, CommandHandler, MessageHandler, filters

from common import escape_md

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


def on_command(application: Application, name: str) -> Callable[[Callable], Callable]:
	def add_it(func: Callable) -> Callable:
		application.add_handler(CommandHandler(name, func))
		return func
	return add_it

def on_message(application: Application, filters: filters.BaseFilter) -> Callable[[Callable], Callable]:
	def add_it(func: Callable) -> Callable:
		application.add_handler(MessageHandler(filters, func))
		return func
	return add_it

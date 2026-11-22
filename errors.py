#!/usr/bin/env python3
import traceback
from datetime import datetime

from telegram import User, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application

from common import escape_md

LOG_FP = '/var/log/riedlersdevbot.log'

try:
	with open(LOG_FP, 'a+') as f:
		# mainly just an easy way to check if the file is writable
		f.write(f'started at {datetime.now().strftime('%F %T')}')
except Exception:
	raise OSError(f"could not write to log file {LOG_FP}")


async def error_handler(chat_id: int, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Log the error and send a telegram message to notify the developer. largely based on the errorhandlerbot example """

	if context.error is not None:
		tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
		tb_string = "".join(tb_list)
	else:
		tb_string = "<no traceback lol get rekt>"

	mommy = User(388037461, "Lisa", False, "Riedler", "RiedleroD")
	ment = mommy.mention_markdown_v2()

	message = (
		"Whoops, I shat myself ':3\n"
		"```traceback\n"
		f"{escape_md(tb_string)}\n"
		"```"
		f"{ment}, {ment}, {ment} please clean up my mess \\>\\.\\<"
	)

	await context.bot.send_message(
		chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN_V2
	)

	update_str = update.to_dict() if isinstance(update, Update) else str(update)
	with open(LOG_FP, "a+") as f:
		f.write(f"""
error at {datetime.now().strftime('%F %T')}
TRACEBACK
{tb_string}
UPDATE
{update_str}
CHAT CONTEXT
{context.chat_data}
USER CONTEXT
{context.user_data}
""")

def add_error_handler(app: Application, chat_id: int) -> None:
	app.add_error_handler(lambda u, c: error_handler(chat_id, u, c))

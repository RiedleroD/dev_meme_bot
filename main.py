#!/usr/bin/env python3
from math import floor, log10
from datetime import datetime
from collections.abc import Callable

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError

import database
from config import CONFIG
from common import escape_md, hashdigest, get_mention, filter_chat, is_admin, get_reply_target, \
	check_admin_to_user_action, kick_message, Leaderboard
import common

private_chat_id = CONFIG['private_chat_id']
private_chat_username = CONFIG['private_chat_username']

print('loading/creating database')
db = database.UserDB(CONFIG['database_path'])

print("initializing commands")
application = Application.builder().token(CONFIG["token"]).build()

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
	assert update.message is not None

	target = await get_reply_target(update.message, 'votekick')
	if target is None:
		return

	assert update.message.reply_to_message is not None

	tuser, tmsg = target
	voter = update.message.from_user
	chat = update.message.chat

	assert voter is not None
	assert chat is not None

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
		votec = len(votes)
		appendix = "\nthat constitutes a ban\\!" if votec >= 3 else ""
		await update.message.reply_text(
			f'User {get_mention(tuser)} now has {votec}/3 votes against them\\.{appendix}',
			parse_mode=ParseMode.MARKDOWN_V2
		)
		if votec >= 3:
			await kick_message(update.message.reply_to_message, context, db)

			# award score to all eligible users
			for userid in votes:
				db.increment_vkscore(userid)

@on_command("leaderboard")
@filter_chat(private_chat_id, private_chat_username)
async def leaderboard(update: Update, context: CallbackContext):
	assert update.message is not None

	replypromise = update.message.reply_text("loading leaderboard…", disable_notification=True)

	lb = Leaderboard(db)
	scoredigits = floor(log10(lb.scores[0])) + 1

	lines = []

	for user in lb.users:
		if user.rank > 5:
			break

		try:
			usermention = (await context.bot.get_chat_member(update.message.chat_id, user.userid)).user.mention_markdown_v2()
		except TelegramError:
			# couldn't find user… weird.
			usermention = f"user `{user.userid}` \\(not found\\)"

		lines.append(f"{user.rank}\\. `{user.score:{scoredigits}d}` \\- {usermention}")

	reply = await replypromise

	await reply.edit_text(
		f"Leaderboard\\!\n–––\n{'\n'.join(lines)}",
		parse_mode=ParseMode.MARKDOWN_V2
	)

@on_command("myrank")
async def myrank(update: Update, context: CallbackContext):
	assert update.message is not None
	assert update.message.from_user is not None

	lb = Leaderboard(db)
	user = None
	for _user in lb.users:
		if _user.userid == update.message.from_user.id:
			user = _user
			break

	if user is None:
		text = "You're not on the leaderboard yet\\. " \
			"Your score will increase with each successful votekick you participate in\\."
		if not db.get_trusted(update.message.from_user.id):
			text += "\nYou have to be a trusted user to participate in votekicks though\\."
	else:
		text = f"You're rank {user.rank} with {user.score} successful votekicks"
	await update.message.reply_text(text, ParseMode.MARKDOWN_V2)

@on_message(filters.TEXT)
async def on_text_message(update: Update, context: CallbackContext):
	if update.message is not None and update.message.text is not None:
		assert update.message.from_user is not None
		thishash = hashdigest(update.message.text)
		badness = db.check_message_badness(thishash)
		if badness >= CONFIG['spam_threshhold']:
			await kick_message(update.message, context, db)
		else:
			common.recent_messages.append((
				update.message.id,
				thishash,
				update.message.from_user.id
			))
			if len(common.recent_messages) > CONFIG['message_memory']:
				common.recent_messages = common.recent_messages[-CONFIG['message_memory']:]

print("starting polling")
application.run_polling()
print("exiting")

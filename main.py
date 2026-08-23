#!/usr/bin/env python3
from math import floor, log10
from datetime import datetime
from collections.abc import Callable

from telegram import Update, Bot, User, Chat, Message, MessageOriginUser, MessageOriginChat, MessageOriginChannel
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError

import database
from config import CONFIG
from common import escape_md, get_urls_from_message, hashdigest, get_mention, filter_chat, is_admin, get_reply_target, \
	check_admin_to_user_action, kick_message, ban_user, Leaderboard, \
	BannableChat, BannableChatWithObj, BannableUserWithObj, BannableUserWithBoth, BannableWithObj
import common

private_chat_id: int = CONFIG['private_chat_id']
private_chat_username: str = CONFIG['private_chat_username']

print('loading/creating database')
db = database.UserDB(CONFIG['database_path'])

print("initializing commands")
application = Application.builder().token(CONFIG["token"]).build()
if application.job_queue is None:
	raise Exception("missing requirement: python-telegram-bot[job-queue]")


async def delete_vk_messages(context: CallbackContext) -> None:
	db.cleanup_votekicks()
	msgs = db.pop_expired_messages()
	if msgs:
		await context.bot.delete_messages(private_chat_id, msgs)

async def check_sneaky_bitches(context: CallbackContext) -> None:
	toban = []

	bot: Bot = context.bot # needed because my LSP doesn't see the type of context.bot otherwise
	for i, (msgid, bannable) in enumerate(common.join_messages):
		# checks whether message exists
		success = await bot.set_message_reaction(private_chat_id, msgid, None)
		if not success:
			toban.append(i)

	print(f"banning {len(toban)} sneaky bitches out of {len(common.join_messages)}")

	for i in reversed(toban):
		msgid, bannable = common.join_messages.pop(i)
		await common.ban_user(context, private_chat_id, bannable)

	if len(toban) > 0:
		await bot.send_message(private_chat_id, f"banned {len(toban)} sneaky bitches")

async def cleanup(context: CallbackContext) -> None:
	await delete_vk_messages(context)
	await check_sneaky_bitches(context)

if CONFIG['autodelete_every_seconds'] is not None:
	application.job_queue.run_repeating(cleanup, interval=CONFIG['autodelete_every_seconds'], first=0)


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
async def ping(update: Update, _context: CallbackContext) -> None:
	assert update.message is not None
	dt = datetime.now(update.message.date.tzinfo) - update.message.date
	await update.message.reply_text(f'Ping is {dt.total_seconds():.2f}s')


@on_message(filters.StatusUpdate.NEW_CHAT_MEMBERS)
@filter_chat(private_chat_id, private_chat_username)
async def new_chat_member(update: Update, context: CallbackContext) -> None:
	await on_any_message(update, context)
	await on_text_message(update, context)
	assert update.message is not None
	# TODO: check for pfps
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

@on_command("spamkick")
@on_command("kickspam")
@filter_chat(private_chat_id, private_chat_username)
async def spamkick(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	assert update.message.from_user is not None
	target = await check_admin_to_user_action(update.message, 'spamkick', usable_on_bots=True)
	if target is None:
		return

	for voterid in db.get_votekicks(target.id):
		if voterid != update.message.from_user.id:
			db.increment_vkscore(voterid)

	db.increment_vkscore(update.message.from_user.id)

	if update.message.reply_to_message is not None:
		await kick_message(update.message.reply_to_message, context, db, mark_as_spam=True)
	else:
		await ban_user(context, update.message.chat.id, bannable=target, del_messages=True)

@on_command("warn")
@filter_chat(private_chat_id, private_chat_username)
async def warn_member(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	target = await check_admin_to_user_action(update.message, 'warn')
	if target is None:
		return

	warns = db.get_warns(target.id) + 1
	db.set_warns(target.id, warns)
	await update.message.chat.send_message(
		f'*{get_mention(await target.with_obj(context.bot))}* recieved a warn\\! Now they have {warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("unwarn")
@filter_chat(private_chat_id, private_chat_username)
async def unwarn_member(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	target = await check_admin_to_user_action(update.message, 'unwarn')
	if target is None:
		return

	warns = db.get_warns(target.id)
	if warns > 0:
		warns -= 1
	db.set_warns(target.id, warns)
	reply = f'*{get_mention(await target.with_obj(context.bot))}* has been a good hooman\\! '
	if warns == 0:
		reply += 'Now they don\'t have any warns'
	else:
		reply += f'Now they have {warns} warns'
	await update.message.chat.send_message(reply, parse_mode=ParseMode.MARKDOWN_V2)


@on_command("clearwarns")
@filter_chat(private_chat_id, private_chat_username)
async def clear_member_warns(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	target = await check_admin_to_user_action(update.message, 'clearwarns')
	if target is None:
		return

	db.set_warns(target.id, 0)
	await update.message.chat.send_message(
		f"*{get_mention(await target.with_obj(context.bot))}*'s warns were cleared",
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("warns")
@filter_chat(private_chat_id, private_chat_username)
async def get_member_warns(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	assert update.message.from_user is not None
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
	tuser = await tuser.with_obj(context.bot)
	if tuser.is_bot and tmsg.sender_chat is None:
		await update.message.reply_text("Bots don't have warns", parse_mode=ParseMode.MARKDOWN_V2)
		return

	await update.message.reply_text(
		f'*{escape_md(tuser.full_name)}* has {"no" if warns == 0 else warns} warns',
		parse_mode=ParseMode.MARKDOWN_V2
	)


@on_command("trust")
@filter_chat(private_chat_id, private_chat_username)
async def add_trusted_user(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	target = await check_admin_to_user_action(update.message, 'trust')
	if target is None:
		return

	trusted = db.get_trusted(target.id)
	target = await target.with_obj(context.bot)
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
async def del_trusted_user(update: Update, context: CallbackContext) -> None:
	assert update.message is not None
	target = await check_admin_to_user_action(update.message, 'untrust')
	if target is None:
		return

	trusted = db.get_trusted(target.id)
	target = await target.with_obj(context.bot)
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
async def votekick(update: Update, context: CallbackContext) -> None:
	assert update.message is not None

	target = await get_reply_target(update.message, 'votekick', allow_ment=True)
	if target is None:
		return
	tuser, tmsg = target
	voter = update.message.from_user
	chat = update.message.chat

	assert voter is not None
	assert chat is not None

	is_chat = isinstance(tuser, BannableChat)

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
	elif db.get_trusted(tuser.id) and not is_chat:
		await update.message.reply_text(
			f"You can\'t votekick another trusted user \"{escape_md(repr(tuser))}\"",
			parse_mode=ParseMode.MARKDOWN_V2
		)
	elif (not is_chat) and (await is_admin(chat, tuser)):
		await update.message.reply_text(
			'You can\'t votekick an admin',
			parse_mode=ParseMode.MARKDOWN_V2
		)
	else:
		votes_required = CONFIG['votes_required']
		tuser = await tuser.with_obj(context.bot)

		db.add_votekick(voter.id, tuser.id)
		votes = db.get_votekicks(tuser.id)
		votec = len(votes)
		appendix = "\nthat constitutes a ban\\!" if votec >= votes_required else ""
		pronoun = 'Channel' if is_chat else 'User'
		reply = await update.message.reply_text(
			f'{pronoun} {get_mention(tuser)} now has {votec}/{votes_required} votes against them\\.{appendix}',
			parse_mode=ParseMode.MARKDOWN_V2
		)

		if votec >= votes_required:
			# don't remove the bot's final message
			db.add_vk_messages(tuser.id, [update.message.message_id])

			if tmsg is not None:
				await kick_message(tmsg, context, db)

			# award score to all eligible users
			for userid in votes:
				db.increment_vkscore(userid)
		else:
			db.add_vk_messages(tuser.id, [update.message.message_id, reply.message_id])

	# immediately delete instead of queueing deletion if config says so
	if CONFIG['autodelete_every_seconds'] is None:
		await delete_vk_messages(context)

@on_command("leaderboard")
@filter_chat(private_chat_id, private_chat_username)
async def leaderboard(update: Update, context: CallbackContext) -> None:
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
async def myrank(update: Update, context: CallbackContext) -> None:
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
@filter_chat(private_chat_id, private_chat_username)
async def on_text_message(update: Update, context: CallbackContext) -> None:
	await on_any_message(update, context)
	if update.message is not None and update.message.text is not None:
		assert update.message.from_user is not None
		message_links: list[str] = get_urls_from_message(update.message)
		for link in message_links:
			link_hash: bytes = hashdigest(link)
			link_badness: int = db.check_message_badness(link_hash)
			if link_badness >= CONFIG['spam_threshhold']:
				await kick_message(update.message, context, db)
				break
			elif len(update.message.new_chat_members) > 0: # join message
				await common.register_joinmsg(update.message)

				if CONFIG['autodelete_every_seconds'] is None:
					assert application.job_queue is not None
					if not len(application.job_queue.get_jobs_by_name(check_sneaky_bitches.__name__)) > 0:
						application.job_queue.run_once(check_sneaky_bitches, 10)
			else:
				target: BannableWithObj
				if update.message.sender_chat is not None:
					target = BannableChatWithObj.from_chat(update.message.sender_chat)
				else:
					target = BannableUserWithObj.from_user(update.message.from_user)
				common.recent_message_links.append((
					update.message.id,
					link_hash,
					target,
				))
			common.trunc_msgmem(common.recent_message_links)


@on_message(filters.ALL)
@filter_chat(private_chat_id, private_chat_username)
async def on_any_message(update: Update, context: CallbackContext) -> None:
	# remembering users we've come across
	users_to_search: list[BannableUserWithBoth | BannableChatWithObj] = []

	def add_tuser(tuser: User | None) -> None:
		if tuser is not None and tuser.username is not None:
			users_to_search.append(BannableUserWithBoth.from_user(tuser))

	def add_tchat(tchat: Chat | None) -> None:
		if tchat is not None and tchat.username is not None:
			users_to_search.append(BannableChatWithObj.from_chat(tchat))

	def add_tmessage(tmessage: Message | None) -> None:
		if tmessage is not None:
			if tmessage.sender_chat is not None:
				add_tchat(tmessage.sender_chat)
			else:
				add_tuser(tmessage.from_user)
			add_tuser(tmessage.via_bot)
			add_tuser(tmessage.sender_business_bot)
			add_tuser(tmessage.guest_bot_caller_user)
			add_tchat(tmessage.guest_bot_caller_chat)
			if tmessage.new_chat_members is not None:
				for member in tmessage.new_chat_members:
					add_tuser(member)
			if tmessage.forward_origin is not None:
				if isinstance(tmessage.forward_origin, MessageOriginUser):
					add_tuser(tmessage.forward_origin.sender_user)
				if isinstance(tmessage.forward_origin, MessageOriginChat):
					add_tchat(tmessage.forward_origin.sender_chat)
				if isinstance(tmessage.forward_origin, MessageOriginChannel):
					add_tchat(tmessage.forward_origin.chat)
			if tmessage.reply_to_story is not None:
				add_tchat(tmessage.reply_to_story.chat)
			add_tmessage(tmessage.reply_to_message)
			if tmessage.pinned_message is not None and isinstance(tmessage.pinned_message, Message):
				add_tmessage(tmessage.pinned_message)

	add_tmessage(update.message)
	add_tmessage(update.edited_message)

	for search_bannable in users_to_search:
		found = False
		for i, bannable in enumerate(common.recent_message_users):
			if bannable.handle == search_bannable.handle:
				found = True
				if search_bannable.id == bannable.id:
					break # no problemo. already in memory
				else:
					# uh oh! it's someone else now. wtf? replace entry
					common.recent_message_users[i] = search_bannable
					break
		if not found:
			print(f"saw new user: {search_bannable.id} => {search_bannable.handle}")
			common.recent_message_users.append(search_bannable)

		common.trunc_msgmem(common.recent_message_users)

print("starting polling")
application.run_polling()
print("exiting")

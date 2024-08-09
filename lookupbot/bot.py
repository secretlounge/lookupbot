import telebot
import logging
import time
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict

from . import backend as xb

TMessage = telebot.types.Message

bot: telebot.TeleBot = None
dbs: Dict[str, xb.Database] = None

target_group: Optional[int] = None

def init(config: dict):
	global bot, dbs, target_group
	if not config.get("bot_token"):
		logging.error("No Telegram bot token specified")
		exit(1)

	logging.getLogger("urllib3").setLevel(logging.WARNING) # very noisy with debug otherwise

	bot = telebot.TeleBot(config["bot_token"], threaded=False)
	if config.get("target_group"):
		target_group = int(config["target_group"])

	dbs = xb.detect_dbs(config["database_path"])

	set_handler(handle_msg, content_types=["text"], chat_types=["group", "supergroup"])
	logging.info("Startup OK")

def set_handler(func, *args, **kwargs):
	def wrapper(*args, **kwargs):
		try:
			func(*args, **kwargs)
		except Exception as e:
			logging.exception("Exception raised in event handler")
	bot.message_handler(*args, **kwargs)(wrapper)

def run():
	assert not bot.threaded
	while True:
		try:
			bot.polling(non_stop=True, long_polling_timeout=60)
		except Exception as e:
			# you're not supposed to call .polling() more than once but I'm left with no choice
			logging.warning("%s while polling Telegram, retrying.", type(e).__name__)
			time.sleep(1)

def callwrapper(f) -> Optional[str]:
	while True:
		try:
			f()
		except telebot.apihelper.ApiException as e:
			status = check_telegram_exc(e)
			if not status:
				continue
			return status
		return

def check_telegram_exc(e):
	errmsgs = ["bot was blocked by the user", "user is deactivated",
		"PEER_ID_INVALID", "bot can't initiate conversation"]
	if any(msg in e.result.text for msg in errmsgs):
		return "blocked"

	if "Too Many Requests" in e.result.text:
		d = json.loads(e.result.text)["parameters"]["retry_after"]
		d = min(d, 30)
		logging.warning("API rate limit hit, waiting for %ds", d)
		time.sleep(d)
		return False # retry

	logging.exception("API exception")
	return "exception"

def handle_msg(ev: TMessage):
	if ev.chat.id != target_group:
		logging.warning("Got message from group %d which "
			"we're not supposed to be in", ev.chat.id)
	m = re.match(r"^/bf\s*([0-9]{3,})(@|\s|$)", ev.text)
	if m:
		return do_lookup(ev, int(m.group(1)))

def do_lookup(ev: TMessage, uid: int):
	banned = defaultdict(list)
	placeholder = []
	seen = []
	for dbname in sorted(dbs.keys()):
		row = xb.get_user(dbs[dbname], uid)
		if row and not xb.is_placeholder(row):
			seen.append(dbname)
		if row and row["rank"] < 0:
			if xb.is_placeholder(row):
				placeholder.append(dbname)
			else:
				grp = (row["left"].strftime("%Y-%m-%d")
					if row["left"] else "") + row["blacklistReason"] # group meaningfully
				banned[grp].append((dbname, row))

	if not seen:
		msg = "Haven't seen this guy anywhere"
	else:
		msg = ""
		if banned:
			for entries in banned.values():
				msg += f"<u>In {", ".join(e[0] for e in entries)}:</u>\n"
				l = format_row(entries[0][1])
				msg += "\n".join("\u2013 " + escape_html(s) for s in l) + "\n"
		if placeholder:
			msg += f"<u>In {", ".join(placeholder)}:</u>\n"
			msg += "\u2013 (placeholder)\n"
		if not msg:
			msg = "Not banned anywhere"

		msg = "Seen in: " + ", ".join(seen) + "\n\n" + msg

	msg = f"User ID: <code>{uid}</code>\n" + msg
	callwrapper(lambda: bot.send_message(target_group, msg, parse_mode="HTML"))

### Helpers

def escape_html(s):
	ret = ""
	for c in s:
		if c in ("<", ">", "&"):
			c = "&#" + str(ord(c)) + ";"
		ret += c
	return ret

def format_row(row: dict):
	l = []
	for k in sorted(row.keys()):
		if k in ("rank", "realname"):
			continue # need for processing but not interesting here
		val = row[k]
		if val is None:
			val = "NULL"
		elif isinstance(val, datetime):
			val = val.strftime("%Y-%m-%d %H:%M")
		l.append(f"{k}: {str(val)}")
	return l

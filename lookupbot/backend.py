import os
import logging
import sqlite3
from datetime import datetime, timedelta

class Database():
	def __init__(self, path):
		t = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
		self.db = sqlite3.connect(path, detect_types=t, check_same_thread=False)
		self.db.row_factory = sqlite3.Row
	# wrappers for standard functions
	def execute(self, *args, **kwargs):
		n = 1
		while True:
			try:
				return self.db.execute(*args, **kwargs)
			except sqlite3.OperationalError as e:
				if "database is locked" in str(e):
					msg = "Database read blocked by lock, retrying"
					if n > 1:
						msg += " (%d)" % n
					logging.warning(msg)
					n += 1
					continue
				raise
	def commit(self):
		return self.db.commit()

def detect_db_paths(top):
	assert os.path.isdir(top)
	single_path = os.path.join(top, "db.sqlite")
	if os.path.isfile(single_path):
		return {"default": single_path}
	d = {}
	for e in os.scandir(top):
		if e.is_dir():
			path = os.path.join(e.path, "db.sqlite")
			if os.path.exists(path):
				d[e.name] = path
	return d

def detect_dbs(top):
	d = detect_db_paths(top)
	if len(d) == 0:
		logging.error("No database(s) detected, exiting!")
		exit(1)
	logging.info("Detected %d database%s: %s", len(d),
		"s" if len(d) > 1 else "", ", ".join(d.keys()))
	for k, v in d.items():
		d[k] = Database(v)
	return d

###

GET_ATTRS = ("realname", "rank", "joined", "left", "lastActive", "cooldownUntil", "blacklistReason")

def get_user(db: Database, uid: int):
	sql = "SELECT " + ",".join(GET_ATTRS) + " FROM users WHERE id = ?"
	c = db.execute(sql, (uid, ))
	return c.fetchone()

def is_placeholder(row):
	return row["realname"] == "" and row["left"] == datetime.utcfromtimestamp(0)

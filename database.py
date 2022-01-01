import sqlite3
from os import path
import json

db_path = 'memebot.json'

class UserDB:
	db: dict
	
	def __init__(self):
		self.open()

	def open(self):
		if path.exists(db_path):
			with open(db_path, 'r') as f:
				self.db = json.load(f)
			return
		self.db = {}
		self.dump()
	
	def dump(self):
		with open(db_path, 'w') as f:
			json.dump(self.db, f)

	def create_user_record(self, userid: int, warncount: int = 0):
		self.db[str(userid)] = {
			'warncount': warncount
		}
	
	def get_warns(self, userid: int):
		if str(userid) not in self.db.keys():
			self.create_user_record(userid)
		return self.db[str(userid)]['warncount']
	
	def set_warns(self, userid: int, warncount: int):
		self.db[str(userid)]['warncount'] = warncount











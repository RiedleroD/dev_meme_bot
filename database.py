from os import path
import json

class UserDB:
	db: dict
	changed: bool
	db_path: str
	
	def __init__(self, db_path: str):
		self.open(db_path)
		self.changed = False

	def open(self, db_path: str):
		self.db_path = db_path
		self.db = {}
		if path.exists(db_path):
			with open(db_path, 'r') as f:
				self.db = json.load(f)
	
	def dump(self):
		with open(self.db_path, 'w') as f:
			json.dump(self.db, f)
		self.changed = False

	def create_user_record(self, userid: int, warncount: int = 0):
		self.db[str(userid)] = {
			'warncount': warncount
		}
		self.changed = True
	
	def get_warns(self, userid: int):
		if str(userid) not in self.db.keys():
			self.create_user_record(userid)
			self.changed = True
		return self.db[str(userid)]['warncount']
	
	def set_warns(self, userid: int, warncount: int):
		self.db[str(userid)]['warncount'] = warncount
		self.changed = True











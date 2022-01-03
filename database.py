import sqlite3
from threading import RLock

class UserDB:
	mutex: RLock
	db: sqlite3.Connection
	changed: bool
	
	def __init__(self, db_path: str):
		self.mutex = RLock()
		self.changed = False
		self.open(db_path)

	def open(self, db_path: str):
		self.db = sqlite3.connect(db_path, check_same_thread=False)
		self.db.execute('''CREATE TABLE IF NOT EXISTS users(
							userid INTEGER PRIMARY KEY UNIQUE,
							warncount INTEGER CHECK(warncount >= 0)
						)''')
	
	def dump(self):
		with self.mutex:
			self.db.commit()
			self.changed = False

	def create_user_row(self, userid: int, warncount: int = 0):
		with self.mutex:
			self.db.execute('''INSERT INTO users VALUES (?, ?)''', (userid, warncount))
			self.changed = True
	
	def get_warns(self, userid: int) -> int:
		'''
		Get user's warns. Create user row if user was not captured
		'''
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT warncount FROM users WHERE userid = ?''', (userid, ))
			fetch = c.fetchone()
			if fetch is None:
				self.create_user_row(userid)
				return 0
			return fetch[0]
	
	def set_warns(self, userid: int, warncount: int):
		with self.mutex:
			self.db.execute('''UPDATE users SET warncount = ? WHERE userid = ?''', (warncount, userid))
			self.changed = True











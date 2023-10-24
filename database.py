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
							warncount INTEGER CHECK(warncount >= 0),
							trusted INTEGER CHECK(trusted >= 0 AND trusted <= 1)
						)''')
		self.db.execute('''CREATE TABLE IF NOT EXISTS votekicks(
							voter INTEGER,
							bad_user INTEGER,
							timeout INTEGER,
							PRIMARY KEY (voter,bad_user)
						)''')
	
	def dump(self):
		with self.mutex:
			self.db.commit()
			self.changed = False

	def create_user_row(self, userid: int, warncount: int = 0, trusted: bool = False):
		with self.mutex:
			self.db.execute('''INSERT INTO users VALUES (?, ?, ?)''', (userid, warncount, trusted))
			self.changed = True
	
	def ensure_user(self, userid: int):
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT userid FROM users WHERE userid = ?''', (userid, ))
			fetch = c.fetchone()
			if fetch is None:
				self.create_user_row(userid)
	
	def get_warns(self, userid: int) -> int:
		'''
		Get user's warns. Create user row if user was not captured
		'''
		self.ensure_user(userid)
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT warncount FROM users WHERE userid = ?''', (userid, ))
			return c.fetchone()[0]
	
	def set_warns(self, userid: int, warncount: int):
		self.ensure_user(userid)
		with self.mutex:
			self.db.execute('''UPDATE users SET warncount = ? WHERE userid = ?''', (warncount, userid))
			self.changed = True
	
	def set_trusted(self, userid: int, trusted: bool):
		self.ensure_user(userid)
		with self.mutex:
			self.db.execute('''UPDATE users SET trusted = ? WHERE userid = ?''', (trusted, userid))
			self.changed = True
	
	def get_trusted(self, userid: int) -> bool:
		self.ensure_user(userid)
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT trusted FROM users WHERE userid = ?''', (userid, ))
			return [False,True][c.fetchone()[0]]
	
	def cleanup_votekicks(self):
		with self.mutex:
			c = self.db.cursor()
			c.execute('''DELETE FROM votekicks WHERE timeout < UNIXEPOCH('NOW')''')
			c.fetchall()
			if c.rowcount > 0:
				self.changed = True
	
	def add_votekick(self, voter: int, bad_user: int):
		self.cleanup_votekicks()
		with self.mutex:
			self.db.execute('''INSERT OR IGNORE INTO votekicks VALUES (?, ?, UNIXEPOCH('NOW','+24 hours'))''', (voter, bad_user))
			self.changed = True
	
	def get_votekicks(self, bad_user: int) -> int:
		self.cleanup_votekicks()
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT COUNT(bad_user) FROM votekicks WHERE bad_user=?''',(bad_user,))
			return c.fetchone()[0]

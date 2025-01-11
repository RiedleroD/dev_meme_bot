import sqlite3
from threading import RLock

DB_SCHEME_VERSION = 2


class UserDB:
	mutex: RLock
	db: sqlite3.Connection

	def __init__(self, db_path: str):
		self.mutex = RLock()
		self.open(db_path)

	def open(self, db_path: str):
		self.db = sqlite3.connect(db_path, check_same_thread=False)
		self.db.execute('''CREATE TABLE IF NOT EXISTS users(
							userid INTEGER PRIMARY KEY UNIQUE,
							warncount INTEGER CHECK(warncount >= 0),
							trusted INTEGER CHECK(trusted >= 0 AND trusted <= 1),
							vkscore INTEGER CHECK(vkscore >= 0)
						)''')
		self.db.execute('''CREATE TABLE IF NOT EXISTS votekicks(
							voter INTEGER,
							bad_user INTEGER,
							timeout REAL,
							PRIMARY KEY (voter,bad_user)
						)''')

		c = self.db.execute('''PRAGMA user_version''')
		user_version = c.fetchone()[0]

		if user_version < 2:
			print("upgrading DB to: v2")
			self.db.execute('''ALTER TABLE users ADD COLUMN vkscore INTEGER DEFAULT 0 CHECK(vkscore >= 0)''')

		self.db.execute(f'''PRAGMA user_version = {DB_SCHEME_VERSION}''')

	def create_user_row(self, userid: int, warncount: int = 0, trusted: bool = False):
		with self.mutex:
			self.db.execute('''INSERT INTO users VALUES (?, ?, ?, 0)''', (userid, warncount, trusted))
			self.db.commit()

	def ensure_user(self, userid: int):
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT userid FROM users WHERE userid = ?''', (userid,))
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
			c.execute('''SELECT warncount FROM users WHERE userid = ?''', (userid,))
			return c.fetchone()[0]

	def set_warns(self, userid: int, warncount: int):
		self.ensure_user(userid)
		with self.mutex:
			self.db.execute(
				'''UPDATE users SET warncount = ? WHERE userid = ?''',
				(warncount, userid)
			)
			self.db.commit()

	def set_trusted(self, userid: int, trusted: bool):
		self.ensure_user(userid)
		with self.mutex:
			self.db.execute('''UPDATE users SET trusted = ? WHERE userid = ?''', (trusted, userid))
			self.db.commit()

	def get_trusted(self, userid: int) -> bool:
		self.ensure_user(userid)
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT trusted FROM users WHERE userid = ?''', (userid,))
			return bool(c.fetchone()[0])

	def cleanup_votekicks(self):
		with self.mutex:
			c = self.db.cursor()
			c.execute('''DELETE FROM votekicks WHERE timeout < JULIANDAY('NOW')''')
			c.fetchall()
			self.db.commit()

	def add_votekick(self, voter: int, bad_user: int):
		self.cleanup_votekicks()
		with self.mutex:
			self.db.execute(
				'''INSERT OR IGNORE INTO votekicks VALUES (?, ?, JULIANDAY('NOW','+24 hours'))''',
				(voter, bad_user)
			)
			self.db.commit()

	def get_votekicks(self, bad_user: int) -> list[int]:
		self.cleanup_votekicks()
		with self.mutex:
			c = self.db.cursor()
			c.execute('''SELECT voter FROM votekicks WHERE bad_user=?''', (bad_user,))
			return [row[0] for row in c.fetchall()]

	def increment_vkscore(self, userid: int):
		curscore = self.get_vkscore(userid)
		with self.mutex:
			c = self.db.execute('''UPDATE users SET vkscore = ? WHERE userid = ?''', (curscore + 1, userid))
			c.fetchall() # wait for action to complete before committing db
			self.db.commit()

	def get_vkscore(self, userid: int) -> int:
		with self.mutex:
			c = self.db.execute('''SELECT vkscore FROM users WHERE userid = ?''', (userid,))
			return c.fetchone()[0]

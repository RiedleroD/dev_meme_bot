#!/usr/bin/env python3
from os import path
import sys
import json
from typing import TypedDict

class Config(TypedDict):
	token: str
	private_chat_id: int
	private_chat_username: str
	database_path: str
	message_memory: int
	spam_threshhold: int


defaultconfig: Config = {
	'token': 'Your token goes here',
	'private_chat_id': -1001218939335,
	'private_chat_username': 'devs_chat',
	'database_path': 'memebot.db',
	'message_memory': 100,
	'spam_threshhold': 2,
}

print("reading config")
CURDIR = path.dirname(sys.argv[0])
CONFPATH = path.join(CURDIR, 'config.json')
if not path.exists(CONFPATH):
	with open(CONFPATH, 'w') as f:
		json.dump(defaultconfig, f, indent=2)
		print(f'Config was created in {CONFPATH}, please edit it')
		sys.exit(0)

with open(CONFPATH) as f:
	CONFIG: Config = json.load(f)

for k, v in defaultconfig.items():
	if k not in CONFIG.keys():
		CONFIG[k] = v  # type: ignore[literal-required]
		print(f"  defaulting to {k}={v}")

CONFIG['database_path'] = path.join(CURDIR, CONFIG['database_path'])

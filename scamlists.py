from abc import ABC, abstractmethod
from requests import get

from config import CONFIG

class ScamList(ABC):
	__slots__ = ('idlist')

	def __init__(self) -> None:
		self.idlist: list[int] = []

	@abstractmethod
	def update(self) -> None:
		...

class FurrySL(ScamList):
	def update(self) -> None:
		data = get(
			'https://countersign.chat/api/scammer_ids.json',
			headers={
				'Accept': 'application/json',
				'User-Agent': f"Dev Meme Bot (code by t.me/RiedleroD running in t.me/{CONFIG['private_chat_username']})",
			}
		)
		self.idlist = [int(userid) for userid in data.json()]

class MasterSL(ScamList):
	""" Main Scamlist containing all enabled scamlists """
	__slots__ = ('members')

	def __init__(self) -> None:
		self.members = filter_scamlists()
		super().__init__()

	def update(self) -> None:
		idlist = set()
		for member in self.members:
			member.update()
			idlist.update(member.idlist)

		self.idlist = list(idlist)


ALL_SCAMLISTS: dict[str, type[ScamList]] = {
	'furry': FurrySL
}

def filter_scamlists() -> list[ScamList]:
	scamlists: list[ScamList] = []
	for name in CONFIG['scamlists']:
		if name not in ALL_SCAMLISTS.keys():
			raise ValueError(f"{name} is not a valid scam list. select one of ({", ".join(ALL_SCAMLISTS.keys())})")

		print(f"  loading {name}")
		scamlists.append(ALL_SCAMLISTS[name]())

	return scamlists

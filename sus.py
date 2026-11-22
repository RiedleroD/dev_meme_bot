#!/usr/bin/env python3
from dataclasses import dataclass

from telegram import User

@dataclass
class SussyData:
	pfpNr: int # how many PFPs the user has
	# pfpTimes: bool # unfortunately not possible with current bot API - whether all of the account's profile pictures are close together in timestamps
	accNr: int | None
	firstname: str | None
	lastname: str | None
	username: str | None
	premium: bool


type sussytuplist = list[tuple[str, float]] # [(reason, score)]

async def get_sussy_data(u: User) -> SussyData:
	pfps = await u.get_profile_photos(limit=10)

	return SussyData(
		pfps.total_count,
		u.id,
		u.first_name,
		u.last_name,
		u.username,
		u.is_premium or False,
	)

def sussy_rater(sb: SussyData) -> tuple[int, sussytuplist]:
	""" gives a score showing how likely or unlikely it is for an account to be a sockpuppet """
	sussy: sussytuplist = []

	# in general:
	# - 1: negligible
	# - 2: weak
	# - 10: strong
	# - 50: basically surefire

	sussy.append(("has pfp?", -1 if sb.pfpNr > 0 else 4)) # NOTE: some users have a "public" pfp different from their main pfp - in which case we cannot see it.
	"""
	if sb.pfpNr > 1:
		sussy.append(("pfp timestamps", -5 if not sb.pfpTimes else 10))
	"""
	# TODO: continually update at what account number accounts start being sussy, and then smoothly scale it from there
	if sb.accNr is not None and not 1_000_000_000 < sb.accNr < 9_000_000_000:
		sussy.append(("account nr.", -10 if sb.accNr < 1_000_000_000 else 5))

	# Firstname Lastname is a common pattern
	if sb.firstname is not None and sb.lastname is not None:
		fullname = f"{sb.firstname} {sb.lastname}"
		sussy.append(("middle name", 2 if fullname.count(' ') == 1 else -5))

		allnames = fullname.split(' ')
		if all(name.istitle() and len(name.strip()) >= 2 for name in allnames):
			sussy.append(("Firstname Lastname", 5))
		# special characters in fnln
		sussy.append(("alpha fnln", -5 if not all(name.isalpha() and name.isascii() for name in allnames) else 2))
	if (sb.firstname is None) != (sb.lastname is None):
		sussy.append(("mononym", -3))
	if sb.username is not None:
		sussy.append(("alpha usrname", -2 if not sb.username.isalpha() and sb.username.isascii() else 2))
	elif sb.username is None:
		sussy.append(("no username", 5))
	sussy.append(("premium", -1 if sb.premium else 1))

	# NOTE: minimum possible should be:
	# - 1 has pfp
	# -10 low accNr
	# - 5 non-alpha fnln
	# - 2 non-alpha username
	# - 3 mononym
	# - 1 premium
	# -22 TOTAL
	# NOTE: maximum possible should be:
	# - 1 has pfp
	# + 5 high accNr
	# + 2 no middle name
	# + 5 Firstname Lastname
	# + 2 fully alpha fnln
	# + 2 fully alpha username
	# + 1 premium
	# +17

	# NOTE: mine would be:
	# - 1 has pfp
	# -10 low accNr
	# - 5 Middle Name
	# + 5 Firstname Lastname
	# + 2 alphanum fnln
	# + 2 alphanum username
	# + 1 premium
	# -6 TOTAL

	return sum(score for reason, score in sussy), sussy

# dev_meme_bot

## install dependencies

```shell
pip install -r requirements.txt
```

## config
if there's no config yet, the script will create an example one for you. Simply edit that one with your preferred values.

## systemd service
simply replace the relevant paths in `riedlersdevbot.service` and drop the file into /etc/systemd/system/ .

uncomment and set the user field if your setup doesn't work system-wide.

## OpenRC service
replace relevant paths and the user in `riedlersdevbot.rcservice` and drop the file as `riedlersdevbot` into /etc/init.d/ .

## commands:

- `{user_joins}` - greets them
- `/ping` - check latency
- `/warns` - check your warns or warns of a person you replied to
- `/leaderboard` - shows the current leaderboard
- `/myrank` - shows the rank and score of the user

### for trusted users:

- `/votekick` - vote to kick a user (bot will ban after 3 votes) ((votes timeout after 24h))

### for admins:

- `/warn` - add a warn to person
- `/unwarn` - removes 1 warn from person
- `/clearwarns` - clears all warns
- `/trust` - adds a user to the trusted list
- `/untrust` - remove a user from the trusted list

## other features

The bot will greet new users with a welcome message when they join (TODO: make configurable)

It remembers the contents of messages that were subject to votekicks. If two votekicked messages had identical text content, other messages with that content will automatically be removed. For this, the bot looks through the last 100 messages it saw, as well as all future ones.

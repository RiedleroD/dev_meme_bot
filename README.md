# dev_meme_bot

## install dependencies

```shell
pip install -r requirements.txt
```

## config
rename current config.json if it exists in the same directory as the main script.

run the script, it will create config for you. you should edit it.

if config has errors or missing keys, rename current config so script can create new one.

## systemd service
simply drop it into /etc/systemd/system/

set the user field if your setup doesn't work system-wide

## commands:

{user_joins} - greets them

/ping - check latency

/warns - check your warns or warns of a person you replied to

### for trusted users:

/votekick - vote to kick a user (bot will ban after 3 votes) ((votes timeout after 24h))

### for moderators:

/warn - add a warn to person

/unwarn - removes 1 warn from person

/clearwarns - clears all warns

/trust - adds a user to the trusted list

/untrust - remove a user from the trusted list
# cathy
Slack bot for Chick-fil-A

## Overview
This is written in Python and is running on a Virtual Private Server (VPS).  I use GalaxyGate because I do other development work as a hobby.  If you have a spare computer at home (or a Raspberry Pi) you could easily run this without needing to pay for a server.

## Files
**app.py** is the main bot file.  I run this as a server in Linux, but there are many ways to run bot files.  Use the Google and find the fit that is best for you.  This is the file that needs to be running at all times for your bot to work.

**cash_remind.py** is a static python file that uses an Incoming Webhook in Slack.  It's sole purpose is to remind front of house to do a pick up at cash cart.  I use crontab (in Linux) to schedule this multiple times per day.

**cater_remind.py** is a static python file that uses an Incoming Webhook in Slack.  It connects to a Google Sheet that has a list of upcoming catering and the assigned drivers.  I use crontab (in Linux) to schedule this each morning.

**curbside_remind.py** is a static Python file that uses an Incoming Webhook in Slack.  It's sole purpose is to remind leaders to turn curbside on/off at specific times.  I use crontab (in Linux) to schedule this at specific times.

**db.py** is related to sms.py and is something that I'm still playing with.  We only have managers and above in our Slack, so I was kicking around the idea of having a way to quickly text all Team Members (or a subset like all front or all back).  It's basically functional, but there is no way to automate getting Team Members into the database.  It has to be manually updated which, at least for now, is more trouble than it's worth for me.

**scraper.py** is a fun one that takes some work, but comes in handy.  Any emails that come into our store email address that deal with outages at the distribution center are forwarded to my gmail account. This script looks at my gmail every night at 2am and reports any outages to Slack.

**sms.py** see notes above on db.py.

**utils.py** welcome message for sms.py.

**waste_remind.py** is the file that many on Facebook asked about.  Like cash_remind.py, it is a stand-alone script that is run multiple times throughout the day to remind the BOH team to record waste.  It includes two buttons.  One brings up a form in Slack to fill out the waste.  The other opens a Google Sheet where all the waste tracking happens.  This is just the reminder.  The form is part of app.py.

## Contact Me
I don't have a lot of spare time, but if you have questions, please email me and I'll help where I can.  I'm wpmjones on gmail.

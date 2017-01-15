from __future__ import unicode_literals
from datetime import datetime, date, timedelta
import youtube_dl
import OAuth2Util
import praw
import sqlite3
import sys
import time

try:
	import bot
	user = bot.hUser
except Exception:
	pass

ydl_opts = {}
with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download(['http://www.youtube.com/watch?v=BaW_jenozKc'])
db = sqlite3.connect('fresh.db')
c = db.cursor()
c.execute('CREATE TABLE IF NOT EXISTS subscriptions(USER TEXT, TYPE TEXT)')
db.commit()
db.close()

# Drop last week's table for that day and make a new one
def createDailyTable(day):
	db = sqlite3.connect('fresh.db')
	c = db.cursor()
	# this is to account for the fact that the roundup won't get posted until several hours into Sunday
	if day == 'Sunday':
		c.execute('DROP TABLE IF EXISTS SundayOld')
		c.execute('CREATE TABLE IF NOT EXISTS SundayOld(ID TEXT, TITLE TEXT, PERMA TEXT, URL TEXT, TIME INT, SCORE INT)')
		c.execute('INSERT INTO SundayOld SELECT * FROM Sunday')

	c.execute('DROP TABLE IF EXISTS ' + day)
	c.execute('CREATE TABLE IF NOT EXISTS ' + day + '(ID TEXT, TITLE TEXT, PERMA TEXT, URL TEXT, TIME INT, SCORE INT)')
	db.commit()

# Get all [Fresh] posts, ignoring ones submitted the previous day and ones already added
def getFresh(day, sub):
	thingID = ''
	title = ''
	permalink = ''
	url = ''
	created = ''
	score = 0

	db = sqlite3.connect('fresh.db')
	c = db.cursor()

	for post in sub.get_new(limit=100):
		print('  Looking at post ' + post.id + '...')

		if '[fresh' in post.title.lower():
			print('    Found Fresh!')
			print('https://redd.it/' + post.id)

			c = db.execute('SELECT * FROM ' + day + ' WHERE ID = ?', (post.id,))

			if c.fetchone() == None:
				thingID = post.id
				title = post.title
				permalink = 'https://redd.it/' + thingID
				url = post.url
				created = post.created_utc
				score = post.score

				if time.strftime("%A", time.gmtime(post.created_utc)) == day:
					param = (thingID, title, permalink, url, created, score)
					db.execute('INSERT INTO ' + day + ' VALUES(?,?,?,?,?,?)', param)
					db.commit()
				else:
					print ('    Wrong Day! D:')
					db.commit()
			else:
				print ('    Skipping :P')
				db.commit()
		
		time.sleep(1)

	c.close()
	db.close()

# Update the scores of logged posts in all tables
def updateScore():
	days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'SundayOld']

	db = sqlite3.connect('fresh.db')
	c = db.cursor()

	for day in days:
		print('  Updating ' + day)
		c.execute('SELECT * FROM ' + day)
		for row in c:
			post = r.get_submission(submission_id = row[0])
			newScore = post.score

			db.execute('UPDATE ' + day + ' SET SCORE = ? WHERE ID = ?', (newScore, row[0]))
			db.commit()

	db.close()

# Delete from the table posts that aren't at +50 after 12 hours
def dropLame(day, yday):
	age = ''

	db = sqlite3.connect('fresh.db')
	c = db.cursor()

	c.execute('SELECT * FROM ' + day)
	for row in c:
		change = time.time() - int(row[4])

		if (change >= 21600) & (row[5] < 25):
			print ('  Deleting ' + row[0])
			db.execute('DELETE FROM ' + day + ' WHERE ID = ?', (row[0],))
			db.commit()

	c.execute('SELECT * FROM ' + yday)
	for row in c:
		change = time.time() - int(row[4])

		if (change >= 21600) & (row[5] < 25):
			print ('  Deleting ' + row[0])
			db.execute('DELETE FROM ' + yday + ' WHERE ID = ?', (row[0],))
			db.commit()

	db.close()

# Creates the roundup for a specific day
def generateDaily(day):
	db = sqlite3.connect('fresh.db')
	c = db.cursor()

	entry = ''
	total = ''
	message = []

	c.execute('SELECT * FROM ' + day)
	datePosted = c.fetchone()[4]
	message.append(time.strftime('%A, %B %d, %Y', time.gmtime(datePosted)))

	c.execute('SELECT * FROM ' + day + ' ORDER BY SCORE DESC')
	for row in c:
		# FORMAT: * [title](permalink) - (+score)
		entry = '* [' + row[1] + '](' + row[2] + ') - (+' + str(row[5]) + ')\n'
		total += entry
	message.append(total)

	db.close()

	return message

# Creates the round up for that week
def generateWeekly():
	days = ['SundayOld', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
	messages = []

	db = sqlite3.connect('fresh.db')
	c = db.cursor()

	c.execute('SELECT * FROM ' + days[0])
	datePosted = c.fetchone()[4]
	messages.append(time.strftime('%A, %B %d, %Y', time.gmtime(datePosted)))

	for day in days:
		messages.append(generateDaily(day))

	db.close()

	return messages

if __name__ == '__main__':
	print('Logging in...')
	r = praw.Reddit("hhhbot")
	sub = r.get_subreddit('hiphopheads')

	print("Start HHHFreshBot for /r/hiphopheads")

	dayOfWeek = datetime.utcnow().strftime('%A')
	yesterday = (datetime.utcnow() - timedelta(1)).strftime('%A')

	if len(sys.argv) > 1:
		if sys.argv[1] == 'newT':
			print('RUNNING NEWT')
			print('Getting Fresh for ' + yesterday + '...')
			# getFresh(yesterday, sub)
			print('Updating Scores...')
			createDailyTable(dayOfWeek)
			print('Dropping Lame...')
			dropLame(dayOfWeek, yesterday)
			print('Making Table for ' + dayOfWeek + '...')
			createDailyTable(dayOfWeek)
			print('Getting Fresh...')
			getFresh(dayOfWeek, sub)
		elif sys.argv[1] == 'fresh':
			print('RUNNING FRESH')
			print('Getting Fresh for ' + yesterday + '...')
			getFresh(dayOfWeek, sub)
			print('Updating Scores...')
			updateScore()
			print('Dropping Lame...')
			dropLame(dayOfWeek, yesterday)
			print('Done!')
		else:
			print('Invalid argument.')

	print("End HHHFreshBot for /r/" + 'hiphopheads')

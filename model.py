#! /usr/bin/env python
# Author: Jelle 'wires' Herold <jelle@defekt.nl>
# Copyright: this code is place in the public domain.

import re, pwd, os

from os import popen, popen2
from random import randint
from getpass import getpass
from sqlobject import *
from configobj import ConfigObj

class EasypostException(Exception):
	pass

def askPassword(username):
	# interactively query the user
	p1 = getpass("Changing password for mail user %s\nEnter new password:" % username)
	p2 = getpass("Retype new password:")
		
	if not p1 == p2:
		raise EasypostException("Passwords do not match")
	
	if len(p1) < 7:
		raise EasypostException("Password too short")
	
	return p1

def SSHA(passwd):
	# use dovecotpw to generate a SSHA passwd
	o = popen('/usr/sbin/dovecotpw -s SSHA -p %s' % passwd)
	ssha = o.read().strip()
	o.close()
	return ssha

def randomPass():
	# get password and pronounciation using apg
	seed = str(randint(0,1234567))
	o = popen('/usr/bin/apg -n1 -m8 -x10 -c %s -q -t' % seed, 'r')
	p, q = o.read().split(' ')
	q = q[1:-1]
	o.close()
	return p, q[1:-1]

def existsUnix(username):
		# check if user is a existing unix user
		try:
			_,_,uid,gid,name,home,shell = pwd.getpwnam(username)
			return (uid, gid, home)
		except KeyError:
			return None

def validEmail(email):
	p = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b")
	return p.match(email.upper())

def domain(email):
	return email.split('@')[1]


class MailboxDomain(SQLObject):
	name = StringCol(alternateID=True)
	addresses = MultipleJoin("MailboxAddress")

class MailboxAddress(SQLObject):
	email = StringCol(alternateID=True)
	user = ForeignKey('MailboxUser', cascade=True)
	domain = ForeignKey('MailboxDomain', cascade=True)

class MailboxUser(SQLObject):
	username = StringCol(alternateID=True)
	password = StringCol()

	gid = IntCol(default = 0)
	uid = IntCol(default = 0)
	home = StringCol(default = None)

	# used by dovecot
	fullhome = StringCol(default = None)
	fullmail = StringCol(default = None)	

	addresses = MultipleJoin("MailboxAddress")
	
	def generatePassword(self, mail=None):
		# generate random password
		passwd, pron = randomPass()	
		ssha = SSHA(passwd)
		self.password = ssha
	
		if mail:
			# TODO
			print "TODO: implement sending a mail" 

		print "password for user %s changed into %s (%s)" % (self.username, passwd, pron)
		
	
	def changePassword(self):
		passwd = askPassword(self.username);
		ssha = SSHA(passwd)
		self.password = ssha
		print "password for user %s changed" % self.username

	def addAddress(self, email):
		if not validEmail(email):
			raise EasypostException("Email address %s not valid" % email)
		
		# create/get the domain
		dn = domain(email)
		try:
			d = MailboxDomain.byName(dn)
		except SQLObjectNotFound:
			d = MailboxDomain(name=dn)
		
		a = MailboxAddress(email=email, user=self, domain=d)
		print "address %s added to user %s" % (email, self.username)
		
		return a
		

class Easypost:
	def __init__(self):
		# load configuration
		self.config = None
	
		fns = ['/etc/easypost/config', 'easypost.cfg']
		for fn in fns:
			if os.path.exists(fn):
				self.config = ConfigObj(fn)
		
		# configuration is required
		if not self.config:
			raise EasypostException("No configuration found at %s" % fns)
	
		# connect to db
		sqlhub.processConnection = connectionForURI(self.config['db'])


	def setup(self, postfix, dovecot):
		MailboxUser.createTable()
		MailboxDomain.createTable()
		MailboxAddress.createTable()


	def createUser(self, username, email, unix=True):
		# check if valid unix user
		unixuser = existsUnix(username)
		if unix and not unixuser:
			raise EasypostException("User %s is not a valid unix user." % username)
		
		if MailboxUser.selectBy(username=username).count():
			raise EasypostException("User %s already exists" % username)
	
		if not validEmail(email):
			raise EasypostException("Not a valid email address '%s'" % email)
	
		if MailboxAddress.selectBy(email=email).count():
			raise EasypostException("Email adress %s already exists" % email)
	
		# store mail in for example /var/www/<domain>/homes/<user>/Maildir/
		# dovecot home will then be /var/www/<domain>/homes/<user>
		base = self.config['virtualbase']
		home = self.config['virtualhome']
		home = home.replace('%d', domain(email))
		home = home.replace('%n', username)
		mdir = self.config['virtualmaildir']
		
		fullhome = "%s/%s/" % (base, home)
		fullmail = "%s/%s/%s/" % (base, home, mdir)
		
		uid = int(self.config['virtualuid'])
		gid = int(self.config['virtualgid'])
		if unix:
			uid, gid, _ = unixuser
		
		# create mailbox folder	
		try:
			fn = "/%s/%s/%s/" % (base, home, mdir)
			os.makedirs(fn)
			os.chown(fullhome, uid, gid)
			os.chown(fullmail, uid, gid)
		except Exception, e:
			raise EasypostException("Couldn't create mailbox '%s', %s" % (fn, e)) 

		# generate random password
		passwd, pron = randomPass()
		ssha = SSHA(passwd)
	
		# create a user
		u = MailboxUser(username=username, password=ssha, home="%s/%s" % (home, mdir), uid=uid, gid=gid,
					    fullhome=fullhome, fullmail=fullmail)
		print "virtual user %s generated with passwd %s (%s)" % (username, passwd, pron)
	
		u.addAddress(email)
		
	
	def getUser(self, username):
		try:
			u = MailboxUser.byUsername(username)
		except SQLObjectNotFound:
			raise EasypostException("User %s doesn't exist" % username)
		return u
		
	
	def removeUser(self, username):
		self.getUser(username).destroySelf()

	def createEmail(self, username, email):
		self.getUser(username).addAddress(email)
	
	def removeEmail(self, email):
		try:
			MailboxAddress.byEmail(email.lower()).destroySelf()
		except SQLObjectNotFound:
			raise EasypostException("No such email address %s" % email.lower())
	
	def listUsers(self, email=None, domain=None):
		for u in MailboxUser.select():

			# print user
			print "%s (%s)" % (u.username, u.home)
				
			for a in MailboxAddress.selectBy(user=u):
				print "  %s" % a.email
		
	def listEmail(config, user=None, domain=None):
		for a in MailboxAddress.select():
			print a.email
	
	def listDomains(config, user=None):
		for d in MailboxDomain.select():
			print d.name
	


===========================================================
Easypost; A basic CLI postfix/dovecot administration system
===========================================================

Author: Jelle 'wires' Herold ``jelle {at} defekt {dot} nl``

Requirements
============

This is intended for Debian/Ubuntu based systems. Minimum requirements:

 - Dovecot
 - Postfix
 - Postgresql
 - Python-sqlobject
 - APG automatic password generator

``sudo aptitude install postfix-pgsql dovecot-imapd python-sqlobject postgresql apg``


Setup
=====

Postgresql
----------

First, postgresql setup. We create a password protected user
with limited capabilities, called ``easypost``. The password
is encrypted using MD5 (see ``man createuser`` for details).
Also, create a database called ``easypost`` for this user.::

  sudo -u postgres bash
  createuser -DRESP easypost
  createdb -O easypost easypost
  exit

We are running postfix and postgresql on the same system. So
we first configure postgres to accept connections from user.
Add the following line to
``/etc/postgresql/8.2/main/pg_hba.conf``.::

 local easypost easypost md5
 host  easypost easypost 127.0.0.1/32 md5

(Make sure this is above the line that says ``local all all
ident sameuser``. Also, the second line is nog needed if there
is a line like ``host all all 127.0.0.1/32 md5``.)

That's it. You can test this (as any user) with:::

  psql easypost -U easypost
  psql easypost -U easypost -l localhost

(This should ask for the passphrase).

Setup the system.
-----------------

 - read configuration from /etc/easypost/config
 - if not found, read configuration from ./easypost.cfg
 - if not found, fail

 - connect to database and create tables

 - if not exists <postfix_conf_dir>, create it
 - write example postfix configuration files to this dir

 - if not exists <dovecot_conf_dir>, create it
 - write example dovecot configuration files to this dir

``easypost setup -p <postfix_conf_dir> -d <dovecot_conf_dir>``

Usage
=====

Creating users and email adresses
---------------------------------

First, create the user named <username> with the associated
primary email address.

If you specify --unix and a local UNIX user named <username>
exists, the mailbox will be owned by that user and placed
in that users homedir.

In the configuration file can be configured where this
mailbox should be placed, e.g. /var/www/<domain>/mail/<user>

``easypost create user <username> <primaryEmailAddress> [--unix]``

``easypost remove user <username>``

Add a email address to a user (likewise, remove).

``easypost user <username> add address <address>``

``easypost user <username> remove address <address>``

Password changes
----------------

(Re-)generate a random password for the specified user, and optionally email
this somewhere, including system informat (e.g. what mail server to use, etc)

``easypost user <username> generate-password [--mail-to <email_address>]``

Change the password interactively.

``easypost user <username> change-password``


Listing database contents
-------------------------

List all users. Optionally limit to all users at <domain> or
with email adress <address>.

``easypost list users [--domain <domain>] [--address <address>]``

Likewise, list all email adresses. Optionally for a domain or specific user.

``easypost list addresses [--domain <domain>] [--user <username>]``

List all domains (for a specific user).

``easypost list domains [--user <username>]``

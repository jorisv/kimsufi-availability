# -*- coding: utf-8 -*-

"""
Find the Kimsufi servers availability.

Usage:
  kimsufi.py [options]
  kimsufi.py <model>... [options]

Options:
  -h, --help        Show this help.
  -v, --version     Show version.
  -m, --mail        Sends a mail when a server is available.
  -s, --sms         Sends a SMS using free mobile web API.
  --loop=<seconds>  Set the script in a endless mode that check
                    the availability every <seconds>.

Examples:
  kimsufi.py
  kimsufi.py KS-1 KS-3
  kimsufi.py KS-1 --mail
"""

import sys
import time
import smtplib
import urllib
import sched

import requests
from docopt import docopt

VERSION = "1.0"

MAIL_HOST = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USERNAME = "xxxxxx"
MAIL_PASSWORD = "xxxxxx"

MAIL_FROM = "xxxxxx@xxxxxx.xxx"
MAIL_TO = "xxxxxx@xxxxxx.xxx"

FREE_SMS_URL = "https://smsapi.free-mobile.fr/sendmsg?"
FREE_SMS_USER = "xxxxxxx"
FREE_SMS_PASS = "xxxxxxx"

API_URL = "https://ws.ovh.com/dedicated/r2/ws.dispatcher/getAvailability2"
REFERENCES = {'150sk10': 'KS-1',
              '150sk20': 'KS-2a',
              '150sk21': 'KS-2b',
              '150sk22': 'KS-2c',
              '150sk30': 'KS-3',
              '150sk31': 'KS-3',
              '150sk40': 'KS-4',
              '150sk41': 'KS-4',
              '150sk42': 'KS-4',
              '150sk50': 'KS-5',
              '150sk60': 'KS-6',
              '141game1': 'GAME-1',
              '141game2': 'GAME-2',
              '141game3': 'GAME-3',
}
ZONES = { 'bhs': 'Beauharnois, Canada (Americas)',
          'gra': 'Gravelines, France',
          'rbx': 'Roubaix, France (Western Europe)',
          'sbg': 'Strasbourg, France (Central Europe)',
          'par': 'Paris, France'}

def get_servers(models):
  """Get the servers from the OVH API."""

  r = requests.get(API_URL)

  if not r.ok:
    print 'Server request has failed'
    print 'Status code: %s' % r.status_code
    return []

  try:
    response = r.json()['answer']['availability']
  except TypeError as e:
    print 'Error during response reading: %s', e
    return []

  search = REFERENCES
  if models:
    search = {k: v for k, v in REFERENCES.items() if v in models}

  return [k for k in response if any(r == k['reference'] for r in search)]


def get_ref(name):
  """Return the reference based on the server model."""

  return list(REFERENCES.keys())[list(REFERENCES.values()).index(name)]


def send_mail(output, total):
  """Send a mail to <MAIL_TO>."""

  subject = "{0} server{1} {2} available on Kimsufi".format(
    total,
    "s"[total<=1:],
    ["is", "are"][total>1]
  )
  headers = "From: {}\r\nTo: {}\r\nSubject: {}\r\n\r\n".format(
    MAIL_FROM,
    MAIL_TO,
    subject
  )

  try:
    server = smtplib.SMTP(MAIL_HOST, MAIL_PORT)
  except smtplib.socket.gaierror:
    return False

  server.ehlo()
  server.starttls()
  server.ehlo()

  try:
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
  except smtplib.SMTPAuthenticationError:
    return False

  try:
    server.sendmail(MAIL_FROM, MAIL_TO, headers + output)
    return True
  except Exception:
    return False
  finally:
    server.close()


def send_sms(output, total):
  url_args = {
    'user': FREE_SMS_USER,
    'pass': FREE_SMS_PASS,
    'msg': output
  }
  free_sms_url_args = urllib.urlencode(url_args)
  free_sms_full_url = FREE_SMS_URL + free_sms_url_args
  # free certificate don't work on free-mobile url
  r = requests.get(free_sms_full_url, verify=False)
  if not r.ok:
    print 'SMS notification has failed'
    print 'Status code: %s' % r.status_code
    return False
  return True


def check_availability(arguments):
  kim = get_servers(arguments['<model>'])

  total = 0
  output = ""

  for k in kim:
    output += "\n{}\n".format(REFERENCES[k['reference']])
    output += "{}\n".format("="*len(REFERENCES[k['reference']]))

    for z in k['zones']:
      if z['availability'] in ['unknown', 'unavailable']:
        availability = z['availability']
      else:
        availability = "[OK]"
        total += 1
      output += '{} : {}\n'.format(ZONES[z['zone']], availability)

  output += "\n=======\nRESULT : {0} server{1} {2} available on Kimsufi\n=======\n".format(
    total,
    "s"[total<=1:],
    ["is", "are"][total>1]
  )

  return output, total


def send_notifications(arguments, output, total):
  if arguments['--mail']:
    send_mail(output, total)
  if arguments['--sms']:
    send_sms(output, total)
  print output


class CheckAndNotify(object):
  def __init__(self):
    self.has_been_notified = False
    self.i = 0

  def check_and_notify(self, arguments):
    output, total = check_availability(arguments)
    # trigger the notification if there is availability
    # and user has not been already notify
    if not self.has_been_notified and total > 0:
      send_notifications(arguments, output, total)
      self.has_been_notified = True
    elif total == 0:
      # if there is no availability we can reset
      # the notify trigger
      self.has_been_notified = False


if __name__ == '__main__':
  arguments = docopt(__doc__, version=VERSION)

  can = CheckAndNotify()

  if not arguments['--loop']:
    can.check_and_notify(arguments)
  else:
    seconds = int(arguments['--loop'])
    s = sched.scheduler(time.time, time.sleep)
    def check_and_reenter():
      can.check_and_notify(arguments)
      s.enter(seconds, 1, check_and_reenter, ())

    check_and_reenter()
    s.run()

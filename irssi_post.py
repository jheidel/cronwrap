import json
import logging
import requests
import socket
import string, os, urllib, urllib2, shlex
from subprocess import Popen, PIPE

CRED_FILE = '/root/.config/irssi_credentials'


def notify(msg):
  with open(CRED_FILE) as f:
    creds = json.load(f)
  notifier = IrssiNotifier(creds['token'], creds['password'])
  notifier.send(msg, chan='#cron', nick=socket.gethostname())


class IrssiNotifier(object):

  def __init__(self, api_token, enc_pass):
    self.api_token = api_token
    self.enc_pass = enc_pass

  def encrypt(self, text):
    command = 'openssl enc -aes-128-cbc -salt -base64 -A -pass env:OpenSSLEncPW'
    opensslenv = os.environ.copy()
    opensslenv['OpenSSLEncPW'] = self.enc_pass
    output, errors = Popen(
        shlex.split(command), stdin=PIPE, stdout=PIPE, stderr=PIPE,
        env=opensslenv).communicate(text + ' ')
    output = string.replace(output, '/', '_')
    output = string.replace(output, '+', '-')
    output = string.replace(output, '=', '')
    return output

  def send(self, message, chan='#local', nick='server'):
    data = {
      'apiToken': self.api_token,
      'nick': self.encrypt(nick),
      'channel': self.encrypt(chan),
      'message': self.encrypt(message),
      'version': 13,
    }
    url = 'https://irssinotifier.appspot.com/API/Message'
    logging.info('Now sending message to irssinotifier API.')
    resp = requests.post(url, data=data)
    logging.info('Message sent: %s', resp)

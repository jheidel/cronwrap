#!/usr/bin/env python

# Wraps a process with logging basic STDOUT / STDERR logging and failure
# notification via irssi_notifier (google cloud messaging)
#
# Usage:
#  ./cronwrap.py [command]

import logging
import os
import shutil
import subprocess
import sys
import threading
import time

import irssi_post


LOG_FILE = '/var/log/cronwrap'
CRON_LOG_DIR = '/var/log/cron/'

def get_name(argv):
  """Gets the canonical name for a cron."""
  # Avoid creating meaningless names.
  blacklist = ['sh', 'bash']
  name = 'empty' if len(argv) == 0 else os.path.basename(argv[0])
  return get_name(argv[1:]) if name in blacklist else name


def run(argv):
  exec_name = os.path.join(get_name(argv), 
      time.strftime('%Y%m%d-%H%M%S', time.localtime()))
  rundir = os.path.join(CRON_LOG_DIR, exec_name)
  logging.info('Logging cron to %s' % rundir)

  os.makedirs(rundir)

  log_file = os.path.join(rundir, 'log')
  proc_logger = logging.getLogger('ProcLogger')
  proc_logger.propagate = False  # Don't log to cronwrap's log
  fh = logging.FileHandler(log_file)
  fh.setLevel(logging.DEBUG)
  fmt = logging.Formatter('%(asctime)-15s %(levelname)s : %(message)s')
  fh.setFormatter(fmt)
  proc_logger.addHandler(fh)

  proc_logger.debug('Starting cron "%s" with args %s' % (exec_name, argv))
  start = time.time()
  logged_data = threading.Event()

  def consume(pipe, target):
    with pipe:
      for line in iter(pipe.readline, b''): #NOTE: workaround read-ahead bug
        logged_data.set()
        target(line.strip())

  proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  threads = [
      threading.Thread(target=consume, args=[proc.stdout, proc_logger.info]),
      threading.Thread(target=consume, args=[proc.stderr, proc_logger.error])
  ]
  map(lambda x: x.start(), threads)
  exit_code = proc.wait()
  map(lambda x: x.join(), threads)

  proc_logger.debug('Cron "%s" exit %s after %.2f sec' % (
      exec_name, exit_code, time.time() - start))
  logging.info('Done. Exit %s. Log file at %s.' % (exit_code, log_file))

  if exit_code != 0:
    with open(log_file, 'r') as f:
      tail = f.readlines()[-10:]
    irssi_post.notify('Cron %s completed with status %s. Might want to check on that.'
        '\nLog tail:\n%s' % (exec_name, exit_code, ''.join(tail)))

  if not logged_data.is_set():
    logging.info('Cron wrote no data.')
    shutil.rmtree(rundir)


if __name__ == '__main__':
  logging.basicConfig(
      filename=LOG_FILE, level=logging.DEBUG,
      format=('%(asctime)s.%(msecs)d %(levelname)s %(module)s - %(funcName)s: '
              '%(message)s'),
      datefmt='%Y-%m-%d %H:%M:%S')

  argv = sys.argv[1:]
  logging.info('Starting cron "%s" with args %s' % (get_name(argv), argv))
  run(argv)
  logging.info('Cronwrap done.')

"""Send an email when attacked."""
import argparse
import logging

from selenium.webdriver.common.by import By

import common
import email_lib
import selenium_lib as sln


def alert_if_attacked(b, args):
  """Check if we're being attacked and send an email."""
  alert_div = sln.find(b, By.ID, 'attack_alert')

  # The classes contain "noAttack" if there's no attack and "soon" if there is.
  classes = alert_div.get_attribute('class').split()
  if 'noAttack' in classes:
    logging.info('No attack, exiting')
    return

  # Send an alert email.
  logging.info('Attack! Sending email to {}'.format(args.email_to))
  subject = 'Attack alert'
  body = '{} is being attacked!'.format(sln.find(b, By.ID, 'playerName').text)
  email_lib.send_email(args.smtp_host, args.smtp_port, args.smtp_user,
                       args.smtp_password, args.email_to, subject, body)


def main():
  arg_parser = argparse.ArgumentParser()

  # Register common args.
  common.register_args(arg_parser)

  # Email args.
  arg_parser.add_argument('--smtp_host', type=str, required=True)
  arg_parser.add_argument('--smtp_port', type=int, required=True)
  arg_parser.add_argument('--smtp_user', type=str, required=True)
  arg_parser.add_argument('--smtp_password', type=str, required=True)
  arg_parser.add_argument('--email_to', type=str, required=True)

  args = arg_parser.parse_args()

  common.setup_logging(args)
  b = common.open_browser_and_connect(args)

  alert_if_attacked(b, args)


if __name__ == '__main__':
  main()

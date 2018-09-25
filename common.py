"""General utility functions."""
import logging
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By

import selenium_lib as sln


def register_args(arg_parser):
  """Register command-line args."""
  # Login args.
  arg_parser.add_argument('-c', '--tld', type=str, help='TLD', required=True)
  arg_parser.add_argument('-u', '--email', type=str,
                          help='Email', required=True)
  arg_parser.add_argument('-p', '--password', type=str,
                          help='Password', required=True)

  # Provide either --univ_name or --univ_num. Since univ indices change
  # according to which one was used last, --univ_name is recommended.
  group = arg_parser.add_mutually_exclusive_group()
  group.add_argument('--univ_num', type=int,
                     help='Index of univ in the account list (0-based)',
                     default=0)
  group.add_argument('--univ_name', type=str, help='Name of univ')

  # Program args.
  arg_parser.add_argument('--headless', type=bool,
                          default=False, help='Use headless browser')
  arg_parser.add_argument('-v', '--verbose', type=bool,
                          default=False, help='Verbose output')


def setup_logging(args):
  """Setup debug output."""
  if args.verbose:
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO,
        format='[%(levelname)s] %(asctime)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')


def open_browser_and_connect(args):
  """Open a Chrome browser and connect to OGame account."""
  b = _open_browser(args)

  url = 'http://www.ogame.' + args.tld
  logging.info('Navigating to ' + url)
  b.get(url)

  # Close ad.
  sln.find(sln.find(b, By.CLASS_NAME, 'openX_int_closeButton'), By.TAG_NAME, 'a').click()

  logging.info('Filling login form...')
  sln.find(b, By.ID, 'ui-id-1').click()  # Login tab
  sln.find(b, By.ID, 'usernameLogin').send_keys(args.email)
  sln.find(b, By.ID, 'passwordLogin').send_keys(args.password)
  sln.find(b, By.ID, 'loginSubmit').click()  # login

  # Get list of accounts.
  logging.info('Getting list of accounts...')
  accounts = sln.finds(sln.find(sln.find(b, By.ID, 'accountlist'),
                                By.CLASS_NAME, 'rt-tbody'),
                       By.CLASS_NAME, 'rt-tr')
  logging.info('Found {} accounts'.format(len(accounts)))

  # Use --univ_name if it was provided
  if args.univ_name:
    account_names = []
    for account in accounts:
      account_name = sln.find(account, By.CLASS_NAME, 'server-name-cell').text
      account_names.append(account_name)
      if account_name == args.univ_name:
        logging.info('Navigating to account {}'.format(account_name))
        sln.find(accounts[args.univ_num], By.TAG_NAME, 'button').click()
        break
    else:  # could not find --univ_name
      raise ValueError(
          'Could not find account with --univ_name = {}; '
          'accounts found are [{}]'.format(
              args.univ_name, ', '.join(account_names)))

  # Else use --univ_num
  else:
    if not 0 <= args.univ_num < len(accounts):
      raise ValueError('--univ_num should be between 0 and {}; found {}'.format(
          len(accounts) - 1, args.univ_num))
    account_name = sln.find(
        accounts[args.univ_num], By.CLASS_NAME, 'server-name-cell').text
    logging.info('Navigating to account {}'.format(account_name))
    sln.find(accounts[args.univ_num], By.TAG_NAME, 'button').click()

  b.switch_to.window(b.window_handles[-1])
  logging.info('Switched to tab ' + b.current_url)

  return b


def _open_browser(args):
  """Open a Chrome browser."""
  logging.info('Opening Chrome')
  options = webdriver.ChromeOptions()
  if args.headless:
    options.set_headless()
  return webdriver.Chrome(options=options)

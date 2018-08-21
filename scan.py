import argparse
import logging
import sys

from selenium import webdriver


def connect(browser, tld, email, password, univ_num):
  url = 'http://www.ogame.' + tld
  logging.info('Navigating to ' + url)
  browser.get(url)

  logging.info('Filling login form...')
  browser.find_element_by_id('ui-id-1').click()  # Login tab
  browser.find_element_by_id('usernameLogin').send_keys(email)
  browser.find_element_by_id('passwordLogin').send_keys(password)
  browser.find_element_by_id('loginSubmit').click()  # login

  # Get list of accounts.
  logging.info('Getting list of accounts...')
  accounts = browser.find_element_by_id(
      'accountlist').find_element_by_class_name(
      'rt-tbody').find_elements_by_class_name('rt-tr')
  logging.info('Found {} accounts'.format(len(accounts)))
  logging.info('Navigating to universe #{}'.format(univ_num))
  accounts[univ_num].find_element_by_tag_name('button').click()


def go_to_galaxy(browser, planet_num):
  browser.switch_to.window(browser.window_handles[-1])
  logging.info('Switched to tab ' + browser.current_url)
  planets = browser.find_element_by_id(
      'planetList').find_elements_by_class_name('planetlink')
  logging.info('Found {} planets'.format(len(planets)))
  logging.info('Navigating to planet #{}'.format(planet_num))
  planets[planet_num].click()
  logging.info('Navigating to galaxy view')
  browser.find_element_by_id('links').find_elements_by_class_name(
      'menubutton')[8].click()


def main():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('--tld', type=str, help='TLD', required=True)
  arg_parser.add_argument('-u', '--email', type=str,
                          help='Email', required=True)
  arg_parser.add_argument('-p', '--password', type=str,
                          help='Password', required=True)
  arg_parser.add_argument('-n', '--univ_num', type=int,
                          help='Index of univ', default=0)
  arg_parser.add_argument('--planet_num', type=int,
                          default=0, help='Which planet to use')
  arg_parser.add_argument('--headless', type=bool,
                          default=False, help='Use headless browser')
  arg_parser.add_argument('-v', '--verbose', type=bool,
                          default=False, help='Verbose output')
  args = arg_parser.parse_args()

  if args.verbose:
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO,
        format='[%(levelname)s] %(asctime)s - %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

  logging.info('Opening Chrome')
  options = webdriver.ChromeOptions()
  if args.headless:
    options.set_headless()
  browser = webdriver.Chrome(chrome_options=options)
  browser.implicitly_wait(10)

  connect(browser, args.tld, args.email, args.password, args.univ_num)
  go_to_galaxy(browser, args.planet_num)


if __name__ == '__main__':
  main()

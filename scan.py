import argparse
import logging
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def connect(b, tld, email, password, univ_num):
  url = 'http://www.ogame.' + tld
  logging.info('Navigating to ' + url)
  b.get(url)

  logging.info('Filling login form...')
  _find(b, By.ID, 'ui-id-1').click()  # Login tab
  _find(b, By.ID, 'usernameLogin').send_keys(email)
  _find(b, By.ID, 'passwordLogin').send_keys(password)
  _find(b, By.ID, 'loginSubmit').click()  # login

  # Get list of accounts.
  logging.info('Getting list of accounts...')
  accounts = _finds(_find(_find(b, By.ID,
                                'accountlist'), By.CLASS_NAME, 'rt-tbody'),
                    By.CLASS_NAME, 'rt-tr')
  logging.info('Found {} accounts'.format(len(accounts)))
  logging.info('Navigating to account #{}'.format(univ_num))
  _find(accounts[univ_num], By.TAG_NAME, 'button').click()
  b.switch_to.window(b.window_handles[-1])
  logging.info('Switched to tab ' + b.current_url)


def go_to_galaxy_view(b, planet_num):
  planets = _finds(_find(b, By.ID,
                         'planetList'), By.CLASS_NAME, 'planetlink')
  logging.info('Found {} planets'.format(len(planets)))
  logging.info('Navigating to planet #{}'.format(planet_num))
  planets[planet_num].click()
  logging.info('Navigating to galaxy view')
  _finds(_find(b, By.ID, 'links'), By.CLASS_NAME, 'menubutton')[8].click()

  galaxy = int(_find(b, By.ID, 'galaxy_input').get_attribute('value'))
  system = int(_find(b, By.ID, 'system_input').get_attribute('value'))
  logging.info('Home system is {}:{}'.format(galaxy, system))

  return galaxy, system


def go_to_system(b, galaxy, system):
  """Navigate to system and return num ongoing missions."""
  logging.info('Navigating to {}:{}'.format(galaxy, system))
  _find(b, By.ID, 'system_input').send_keys(str(system))
  _find(b, By.CSS_SELECTOR, '#galaxyHeader .btn_blue').click()
  try:
    # Wait for loader to appear.
    WebDriverWait(b, 1).until(
        EC.presence_of_element_located((By.ID, 'galaxyLoading')))
    # Then wait for it to disappear.
    WebDriverWait(b, 3).until_not(
        EC.presence_of_element_located((By.ID, 'galaxyLoading')))
  except TimeoutException:
    pass
  return int(_find(b, By.ID, 'slotUsed').text)


def inspect(b, num_already_processed, num_allowed, rank_min, rank_max, galaxy,
            system, args):
  """Inspect a system.

  Args:
    b: Browser.
    galaxy:
    num_already_processed: Num already processed in this system.
    num_allowed: Num probes allowed at this point.
    rank_min: Min rank to probe.
    rank_max: Max rank to probe.
    galaxy: Galaxy (for debug).
    system: System (for debug).
    args: Command-line args.

  Returns:
    num_processed: (int) Num newly processed in this system.
    done: (bool) Whether the scan was complete.
  """
  logging.info('Inspecting...')
  players = _finds(b, By.CSS_SELECTOR, '.playername',
                   timeout=2, timeout_ok=True)
  logging.info('Found {} players'.format(len(players)))
  potential_targets = []
  for player in players:
    classes = player.get_attribute('class')
    if any(x in classes for x in ['vacation', 'js_no_action', 'banned']):
      logging.info('Skipping protected player')
    elif len(classes) == 2:
      if args.include_normal:
        logging.info('Adding normal player')
        potential_targets.append(player)
      else:
        logging.info('Skipping normal player')
    elif 'inactive' in classes or 'longinactive' in classes:
      if args.include_inactive:
        logging.info('Adding inactive player')
        potential_targets.append(player)
      else:
        logging.info('Skipping inactive player')
    elif 'honorableTarget' in classes:
      if args.include_inactive:
        logging.info('Adding honorable player')
        potential_targets.append(player)
      else:
        logging.info('Skipping honorable player')
    else:
      logging.info(
          'Skipping unsupported player (classes = {})'.format(classes))
  logging.info('Found {} potential targets'.format(len(potential_targets)))
  if num_already_processed:
    logging.info('Will skip {} already processed'.format(
        num_already_processed))
  num_processed = 0
  for potential_target in potential_targets:
    if num_allowed == 0:
      return num_processed, False
    _hover(b, potential_target)
    player_name = potential_target.text
    while True:
      player_id = _find(potential_target, By.TAG_NAME,
                        'a').get_attribute('rel')
      if player_id:
        break
    player_rank = None
    tries = 0  # sometimes this cannot be done, e.g. if player name is empty.
    while not player_rank and tries < 100:
      tries += 1
      for tooltip in _finds(b, By.ID, player_id):
        rank = _find(tooltip, By.TAG_NAME, 'a').text
        if rank:
          player_rank = int(rank)
          break
    if not player_rank:
      logging.info('Skipping bogus')
      continue
    planet_name = _find(_find(potential_target, By.XPATH, '..'),
                        By.CLASS_NAME, 'planetname').text
    planet_position = int(
        _find(_find(potential_target, By.XPATH, '..'), By.CLASS_NAME,
              'position').text)
    logging.info('Potential target: {}:{}:{} [{}] - {} (rank {})'.format(
        galaxy, system, planet_position, planet_name, player_name, player_rank))
    if rank_min <= player_rank <= rank_max:
      if num_already_processed:
        logging.info('Skip (already processed)')
        num_already_processed -= 1
      else:
        logging.info('--> Sending probe to {}:{}:{}'.format(
            galaxy, system, planet_position))
        _click(b, _find(_find(potential_target, By.XPATH, '..'), By.CLASS_NAME,
                        'espionage'))
        num_processed += 1
        num_allowed -= 1
    else:
      logging.info('Not sending probe')
  return num_processed, True


def _hover(b, element):
  hover = ActionChains(b).move_to_element(element)
  hover.perform()


def _click(b, element):
  try:
    element.click()
  except WebDriverException:
    time.sleep(1)
    # Try closing tooltips.
    for close_button in b.find_elements_by_class_name('close-tooltip'):
      try:
        close_button.click()
      except ElementNotVisibleException:
        pass
    time.sleep(1)
    try:
      element.click()
    except WebDriverException:
      pass  # give up


def _find(b, by, element, timeout=10):
  return WebDriverWait(b, timeout).until(
      EC.presence_of_element_located((by, element)))


def _finds(b, by, element, timeout=10, timeout_ok=False):
  try:
    return WebDriverWait(b, timeout).until(
        EC.presence_of_all_elements_located((by, element)))
  except TimeoutException:
    if timeout_ok:
      return []
    else:
      raise


def _iter_coords(start, num):
  """Generator for next element in a donut system/galaxy."""
  yield start
  yield 338
  odd = num % 2 == 1
  bound = (num + 2) // 2
  for i in range(1, bound):
    yield (start + i) % (num + 1)
    yield (start - i) % (num + 1)
  if odd:
    yield (start + bound) % (num + 1)


def main():
  arg_parser = argparse.ArgumentParser()

  # Login args.
  arg_parser.add_argument('--tld', type=str, help='TLD', required=True)
  arg_parser.add_argument('-u', '--email', type=str,
                          help='Email', required=True)
  arg_parser.add_argument('-p', '--password', type=str,
                          help='Password', required=True)
  arg_parser.add_argument('-n', '--univ_num', type=int,
                          help='Index of univ', default=0)

  # Universe structure.
  arg_parser.add_argument('--num_galaxies', type=int, default=7)
  arg_parser.add_argument('--num_systems', type=int, default=499)

  # Probe strategy.
  arg_parser.add_argument('--planet_num', type=int,
                          default=0, help='Which planet to use')
  arg_parser.add_argument('--rank_min', type=int,
                          default=800, help='Min rank to send probes')
  arg_parser.add_argument('--rank_max', type=int,
                          default=3000, help='Max rank to send probes')
  arg_parser.add_argument('--max_missions', type=int,
                          default=14, help='Num missions to send at a time')
  arg_parser.add_argument('--max_scans', type=int,
                          default=100, help='Num of scans before exiting')
  arg_parser.add_argument('--systems_to_skip', type=int,
                          default=0, help='Skip the N closest systems')

  # Targets.
  arg_parser.add_argument('--include_inactive', type=bool, default=True)
  arg_parser.add_argument('--include_honorable', type=bool, default=False)
  arg_parser.add_argument('--include_normal', type=bool, default=False)

  # Program.
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
  b = webdriver.Chrome(chrome_options=options)

  connect(b, args.tld, args.email, args.password, args.univ_num)
  home_galaxy, home_system = go_to_galaxy_view(b, args.planet_num)

  # For now let's stay in the home galaxy.
  num_missions = 0
  num_scans = 0
  initial_num_missions = None
  for i, system in enumerate(_iter_coords(home_system, args.num_systems)):
    if i < args.systems_to_skip:
      logging.info('Skipping system {} [{}]'.format(i, system))
      continue
    done = False
    num_processed_in_this_system = 0
    while not done:
      num_missions = go_to_system(b, home_galaxy, system)
      if initial_num_missions is None:
        initial_num_missions = num_missions
      num_missions -= initial_num_missions
      logging.info('{} ongoing missions'.format(num_missions))
      logging.info('{} total scans'.format(num_scans))
      if num_missions >= args.max_missions:
        # Wait until a mission is done.
        logging.info('Too many missions. Waiting 10s...')
        time.sleep(10)
        continue
      num_allowed = args.max_missions - num_missions
      num_processed, done = inspect(
          b, num_processed_in_this_system, num_allowed,
          args.rank_min, args.rank_max, home_galaxy, system, args)
      num_missions += num_processed
      num_processed_in_this_system += num_processed
      num_scans += num_processed
      if num_scans >= args.max_scans:
        logging.info('Reached {} scans. Exiting.'.format(args.max_scans))
        return


if __name__ == '__main__':
  main()

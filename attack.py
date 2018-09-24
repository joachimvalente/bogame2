import argparse
import collections
import csv
import logging
import math
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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


def count_fleet(b):
  """Gathers number of cargos in each planet."""
  planets = _finds(_find(b, By.ID,
                         'planetList'), By.CLASS_NAME, 'planetlink')
  logging.info('Found {} planets'.format(len(planets)))
  fleet = {}
  for i in range(len(planets)):
    logging.info('Navigating to planet #{}'.format(i))
    # Need to find the planets again since previous references are stale.
    if i > 0:
      planets = _finds(_find(b, By.ID,
                             'planetList'), By.CLASS_NAME, 'planetlink')
    planets[i].click()
    if i == 0:
      logging.info('Navigating to fleet view')
      _finds(_find(b, By.ID, 'links'), By.CLASS_NAME, 'menubutton')[7].click()
    small_cargos = _find(_find(b, By.ID, 'button202'),
                         By.CLASS_NAME, 'level').text
    large_cargos = _find(_find(b, By.ID, 'button203'),
                         By.CLASS_NAME, 'level').text
    logging.info('Planet {} has {} small and {} large cargos'.format(
        i, small_cargos, large_cargos))
    fleet[i] = int(large_cargos)

  return fleet


Coords = collections.namedtuple('Coords', ['galaxy', 'system', 'position'])

PlanetInfo = collections.namedtuple(
    'PlanetInfo', ['metal', 'crystal', 'deuterium', 'fleet_pts', 'defense_pts'])


def parse_number(f):
  """Parse numbers like 123.456 or 1,234M."""
  if f[-1] == 'M':
    return int(float(f[:-1].replace(',', '.')) * 1e6)
  return int(f.replace('.', ''))


def gather_reports(b, max_reports):
  """Gathers all probe reports."""
  _find(b, By.CLASS_NAME, 'messages').click()
  reports = {}
  num_reports = 0
  last_data_msg_id = None  # to know when page is ready
  while num_reports < max_reports:
    page_ready = False
    while not page_ready:
      logging.info('Waiting for page to be ready')
      time.sleep(0.5)
      try:
        top_msg_id = _finds(b, By.CLASS_NAME, 'msg')[
            0].get_attribute('data-msg-id')
      except StaleElementReferenceException:
        continue
      page_ready = last_data_msg_id is None or last_data_msg_id != top_msg_id
    last_data_msg_id = top_msg_id
    for msg in _finds(b, By.CLASS_NAME, 'msg'):
      resspans = _finds(msg, By.CLASS_NAME, 'resspan',
                        timeout=1, timeout_ok=True)
      if len(resspans) != 3:
        logging.info('Skipping message: could not parse resources')
        continue
      metal = parse_number(resspans[0].text.split(' ')[1])
      crystal = parse_number(resspans[1].text.split(' ')[1])
      deuterium = parse_number(resspans[2].text.split(' ')[1])
      fleet_info = _finds(msg, By.CLASS_NAME, 'compacting')[-1]
      counts = _finds(fleet_info, By.CLASS_NAME, 'ctn')
      if len(counts) != 2:
        logging.info('Skipping message: could not parse fleet info')
        continue
      fleet_pts = parse_number(counts[0].text.split(' ')[1])
      defense_pts = parse_number(counts[1].text.split(' ')[1])
      title = _find(msg, By.CLASS_NAME, 'msg_title')
      links = _finds(title, By.TAG_NAME, 'a')
      if len(links) != 1:
        logging.info('Skipping message: could not parse message title')
        continue
      # Text is of the form "<planet name> [galaxy:system:position]"
      coords = list(map(int, links[0].text.split(' ')[-1][1:-1].split(':')))
      if len(coords) != 3:
        logging.info('Skipping message: could not parse coords')
        continue
      key = Coords(coords[0], coords[1], coords[2])
      value = PlanetInfo(
          metal, crystal, deuterium, fleet_pts, defense_pts)
      reports[key] = value
      num_reports += 1
      logging.info('Report #{}: {}: {}'.format(num_reports, key, value))
      if num_reports >= max_reports:
        break
    if num_reports < max_reports:
      # Not done, go to next page.
      lis = _finds(_find(b, By.CLASS_NAME, 'pagination'), By.TAG_NAME, 'li')
      if len(lis) != 5:
        logging.info('Could not find five elements, returning')
        return reports
      cur_page, total_pages = lis[2].text.split('/')
      if cur_page == total_pages:
        logging.info('Reached last page')
        return reports
      lis[3].click()
  return reports


def attack(b, coords, num_cargos, planet_num):
  """Attack a planet at given `coords` from `planet_num` with `num_cargos`."""
  # Navigate to planet.
  planets = _finds(_find(b, By.ID,
                         'planetList'), By.CLASS_NAME, 'planetlink')
  planet = planets[planet_num]
  logging.info('Navigating to planet {}'.format(planet_num))
  planet.click()

  # Navigate to fleet view.
  logging.info('Navigating to fleet view')
  _finds(_find(b, By.ID, 'links'), By.CLASS_NAME, 'menubutton')[7].click()

  # Set num cargos.
  large_cargos = _find(_find(b, By.ID, 'button203'),
                       By.CLASS_NAME, 'fleetValues')
  large_cargos.send_keys(str(num_cargos))
  _find(b, By.ID, 'continue').click()

  # Set target coords.
  galaxy = _find(b, By.ID, 'galaxy')
  system = _find(b, By.ID, 'system')
  position = _find(b, By.ID, 'position')
  galaxy.clear()
  galaxy.send_keys(str(coords.galaxy))
  system.clear()
  system.send_keys(str(coords.system))
  position.clear()
  position.send_keys(str(coords.position))
  position.send_keys(Keys.RETURN)

  # Launch attack.
  _find(b, By.ID, 'missionButton1').click()
  _find(b, By.ID, 'start').click()

  # Wait for fleet view to be visible again.
  _find(b, By.ID, 'button203')
  logging.info(
      'Launched attack on [{}:{}:{}] with {} cargos from planet {}'.format(
          coords.galaxy, coords.system, coords.position, num_cargos,
          planet_num))


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

  # Reports params.
  arg_parser.add_argument('--max_reports', type=int, required=True,
                          help='Maximum num of reports to parse')

  # Attack strategy.
  arg_parser.add_argument('--num_attacks', type=int, required=True,
                          help='Num of attacks')
  arg_parser.add_argument(
      '--sort_by', choices=['total', 'metal', 'crystal', 'deuterium'],
      default='total')
  arg_parser.add_argument('--action', choices=['attack', 'export'],
                          default='export',
                          help='Whether to actually attack or export as CSV')
  arg_parser.add_argument('--output', type=str, default='reports.csv')

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
  if args.action == 'attack':
    fleet = count_fleet(b)
  reports = gather_reports(b, args.max_reports)

  def evaluate(x):
    if args.sort_by == 'total':
      return x.metal + x.crystal + x.deuterium
    if args.sort_by == 'metal':
      return x.metal
    if args.sort_by == 'crystal':
      return x.crystal
    if args.sort_by == 'deuterium':
      return x.deuterium
  sorted_reports = sorted(
      reports.items(), key=lambda x: evaluate(x[1]),
      reverse=True)

  if args.action == 'export':
    columns = Coords._fields + PlanetInfo._fields
    with open(args.output, 'w') as f:
      csv_file = csv.DictWriter(f, fieldnames=columns)
      csv_file.writeheader()
      for coords, planet_info in sorted_reports:
        csv_file.writerow(dict(zip(columns, list(coords) + list(planet_info))))
    logging.info('Wrote reports to {}'.format(args.output))

  elif args.action == 'attack':
    num_targets = 0
    total_metal = 0
    total_crystal = 0
    total_deuterium = 0
    total = 0
    planet_num = 0
    for coords, planet_info in sorted_reports:
      if planet_info.fleet_pts > 0 or planet_info.defense_pts > 0:
        logging.info('Skipping planet with defense')
        continue
      resources = (
          planet_info.metal + planet_info.crystal + planet_info.deuterium)
      total_metal += planet_info.metal
      total_crystal += planet_info.crystal
      total_deuterium += planet_info.deuterium
      total += resources
      num_cargos = int(math.ceil(resources / 50000))
      while fleet[planet_num] < num_cargos:
        logging.info(
            'Not enough cargos on planet {}, trying next one'.format(planet_num))
        planet_num += 1
      logging.info('[{}:{}:{}]: {:,} (M: {:,}, C: {:,}, D: {:,}) '
                   '-> {} large cargos'.format(
                       coords.galaxy, coords.system, coords.position, resources,
                       planet_info.metal, planet_info.crystal,
                       planet_info.deuterium, num_cargos))
      attack(b, coords, num_cargos, planet_num)
      fleet[planet_num] -= num_cargos
      num_targets += 1
      if num_targets >= args.num_attacks:
        break
    logging.info('Total plundered: {:,} (M: {:,}, C: {:,}, D: {:,})'.format(
        total / 2, total_metal / 2, total_crystal / 2, total_deuterium / 2))


if __name__ == '__main__':
  main()

"""Parse probe reports and attack most lucrative targets, or export to CSV."""
import argparse
import collections
import csv
import logging
import math
import time

from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

import common
import selenium_lib as sln

Coords = collections.namedtuple('Coords', ['galaxy', 'system', 'position'])

PlanetInfo = collections.namedtuple(
    'PlanetInfo', ['metal', 'crystal', 'deuterium', 'fleet_pts', 'defense_pts'])


def gather_reports(b, args):
  """Gather probe reports."""
  logging.info('Gathering reports...')
  sln.find(b, By.CLASS_NAME, 'messages').click()

  reports = {}
  num_reports = 0
  last_data_msg_id = None  # to know when next page is ready
  while num_reports < args.max_reports:

    # Wait for page to be ready.
    page_ready = False
    while not page_ready:
      logging.info('Waiting for page to be ready')
      time.sleep(0.5)
      try:
        top_msg_id = sln.finds(b, By.CLASS_NAME, 'msg', timeout=5)[
            0].get_attribute('data-msg-id')
      except StaleElementReferenceException:
        continue
      except TimeoutException:
        # Most likely indicates there are no probe reports.
        logging.warn('Cannot find messages, returning empty list')
        return []
      page_ready = last_data_msg_id is None or last_data_msg_id != top_msg_id
    last_data_msg_id = top_msg_id

    # Iterate over messages.
    for msg in sln.finds(b, By.CLASS_NAME, 'msg'):

      # Parse resources.
      resspans = sln.finds(msg, By.CLASS_NAME, 'resspan',
                           timeout=1, timeout_ok=True)
      if len(resspans) != 3:
        logging.warn('Skipping message: could not parse resources')
        continue
      metal = parse_number(resspans[0].text.split(' ')[1])
      crystal = parse_number(resspans[1].text.split(' ')[1])
      deuterium = parse_number(resspans[2].text.split(' ')[1])

      # Parse fleet info.
      fleet_info = sln.finds(msg, By.CLASS_NAME, 'compacting')[-1]
      counts = sln.finds(fleet_info, By.CLASS_NAME, 'ctn')
      if len(counts) != 2:
        logging.warn('Skipping message: could not parse fleet info')
        continue
      fleet_pts = parse_number(counts[0].text.split(' ')[1])
      defense_pts = parse_number(counts[1].text.split(' ')[1])

      # Parse target coords from the message title.
      title = sln.find(msg, By.CLASS_NAME, 'msg_title')
      links = sln.finds(title, By.TAG_NAME, 'a')
      if len(links) != 1:
        logging.warn('Skipping message: could not parse message title')
        continue
      # Text is of the form "<planet name> [galaxy:system:position]"
      coords = list(map(int, links[0].text.split(' ')[-1][1:-1].split(':')))
      if len(coords) != 3:
        logging.warn('Skipping message: could not parse coords')
        continue

      # Add report to the dict.
      key = Coords(coords[0], coords[1], coords[2])
      value = PlanetInfo(
          metal, crystal, deuterium, fleet_pts, defense_pts)
      reports[key] = value
      num_reports += 1
      logging.info('Report #{}: {}: {}'.format(num_reports, key, value))
      if num_reports >= args.max_reports:
        break

    if num_reports < args.max_reports:
      # Not done, go to next page.
      lis = sln.finds(sln.find(b, By.CLASS_NAME, 'pagination'),
                      By.TAG_NAME, 'li')
      if len(lis) != 5:
        logging.warn('Could not find five elements, returning')
        break
      cur_page, total_pages = lis[2].text.split('/')
      if cur_page == total_pages:
        logging.info('Reached last page')
        break
      lis[3].click()

  def score(x):
    if args.sort_by == 'total':
      return x.metal + x.crystal + x.deuterium
    if args.sort_by == 'metal':
      return x.metal
    if args.sort_by == 'crystal':
      return x.crystal
    if args.sort_by == 'deuterium':
      return x.deuterium

  return sorted(
      reports.items(), key=lambda x: score(x[1]), reverse=True)


def export(b, reports, args):
  """Export parsed reports to CSV."""
  columns = Coords._fields + PlanetInfo._fields
  with open(args.csv, 'w') as f:
    csv_file = csv.DictWriter(f, fieldnames=columns)
    csv_file.writeheader()
    for coords, planet_info in reports:
      csv_file.writerow(dict(zip(columns, list(coords) + list(planet_info))))
  logging.info('Wrote reports to {}'.format(args.csv))


def attack(b, reports, args):
  """Attack most lucrative undefended targets."""
  max_attacks = min(args.num_attacks, len(reports))

  # Count fleet.
  fleet = count_large_cargos(b)

  # Iterate over sorted reports and launch attacks.
  num_targets = 0
  total_metal = 0
  total_crystal = 0
  total_deuterium = 0
  total = 0
  planet_num = 0
  for coords, planet_info in reports:

    # Check if we're done.
    if num_targets >= max_attacks:
      logging.info('Launched {} attacks'.format(num_targets))
      break

    # Skip planets with defense.
    if planet_info.fleet_pts > 0 or planet_info.defense_pts > 0:
      logging.info('Skipping planet with defense')
      continue

    # Count number of cargos needed.
    resources = (
        planet_info.metal + planet_info.crystal + planet_info.deuterium)
    num_cargos = int(math.ceil(resources / 50000))
    logging.info('Need to send {} cargos'.format(num_cargos))

    # Find planet with largest fleet.
    planet_num, cargos = max(fleet.items(), key=lambda x: x[1])
    if not cargos:
      logging.info('Used all cargos available')
      break
    logging.info(
        'Using planet #{} which has the largest fleet ({} cargos)'.format(
            planet_num, cargos))
    num_cargos = min(num_cargos, cargos)
    logging.info('Will send {} cargs'.format(num_cargos))

    # Count resources accrued so far.
    plundered = min(resources, 25000 * cargos)
    ratio = float(plundered) / resources
    total_metal += int(math.floor(planet_info.metal * ratio))
    total_crystal += int(math.floor(planet_info.crystal * ratio))
    total_deuterium += int(math.floor(planet_info.deuterium * ratio))
    total += plundered

    # Launch attack.
    logging.info('[{}:{}:{}]: {:,} (M: {:,}, C: {:,}, D: {:,}) '
                 '-> {} large cargos'.format(
                     coords.galaxy, coords.system, coords.position, resources,
                     planet_info.metal, planet_info.crystal,
                     planet_info.deuterium, num_cargos))
    attack_target(b, coords, planet_num, num_cargos)
    fleet[planet_num] -= num_cargos
    num_targets += 1

  logging.info('Total plundered: {:,} (M: {:,}, C: {:,}, D: {:,})'.format(
      total / 2, total_metal / 2, total_crystal / 2, total_deuterium / 2))


def count_large_cargos(b):
  """Gather number of large cargos in each planet."""

  def find_planets():
    return sln.finds(sln.find(b, By.ID, 'planetList'),
                     By.CLASS_NAME, 'planetlink')

  num_planets = len(find_planets())
  logging.info('Found {} planets'.format(num_planets))

  fleet = {}
  for i in range(num_planets):
    logging.info('Navigating to planet #{}'.format(i))

    # Need to find the planets again since previous references are stale.
    planets = find_planets()
    planets[i].click()

    # Navigate to fleet view (only needed for the first planet).
    if i == 0:
      logging.info('Navigating to fleet view')
      sln.finds(sln.find(b, By.ID, 'links'),
                By.CLASS_NAME, 'menubutton')[7].click()

    try:
      large_cargos = sln.find(sln.find(b, By.ID, 'button203', timeout=5),
                              By.CLASS_NAME, 'level').text
    except TimeoutException:
      # Most likely indicates there is no fleet on this planet.
      logging.warn('No fleet on this planet')
      large_cargos = 0
    logging.info('Planet {} has {} large cargos'.format(i, large_cargos))
    fleet[i] = int(large_cargos)

  return fleet


def attack_target(b, coords, planet_num, num_cargos):
  """Attack a planet at given `coords` from `planet_num` with `num_cargos`."""
  # Navigate to planet.
  planets = sln.finds(sln.find(b, By.ID,
                               'planetList'), By.CLASS_NAME, 'planetlink')
  planet = planets[planet_num]
  logging.info('Navigating to planet {}'.format(planet_num))
  planet.click()

  # Navigate to fleet view.
  logging.info('Navigating to fleet view')
  sln.finds(sln.find(b, By.ID, 'links'),
            By.CLASS_NAME, 'menubutton')[7].click()

  # Set num cargos.
  large_cargos = sln.find(sln.find(b, By.ID, 'button203'),
                          By.CLASS_NAME, 'fleetValues')
  large_cargos.send_keys(str(num_cargos))
  sln.find(b, By.ID, 'continue').click()

  # Set target coords.
  galaxy = sln.find(b, By.ID, 'galaxy')
  system = sln.find(b, By.ID, 'system')
  position = sln.find(b, By.ID, 'position')
  galaxy.clear()
  galaxy.send_keys(str(coords.galaxy))
  system.clear()
  system.send_keys(str(coords.system))
  position.clear()
  position.send_keys(str(coords.position))
  position.send_keys(Keys.RETURN)

  # Launch attack.
  sln.find(b, By.ID, 'missionButton1').click()
  sln.find(b, By.ID, 'start').click()

  # Wait for fleet view to be visible again.
  sln.wait_until(b, By.ID, 'movements')
  logging.info(
      'Launched attack on [{}:{}:{}] with {} cargos from planet {}'.format(
          coords.galaxy, coords.system, coords.position, num_cargos,
          planet_num))


def parse_number(f):
  """Parse numbers like 123.456 or 1,234M."""
  if f[-1] == 'M':
    return int(float(f[:-1].replace(',', '.')) * 1e6)
  return int(f.replace('.', ''))


def main():
  arg_parser = argparse.ArgumentParser()

  # Register common args.
  common.register_args(arg_parser)

  # Args for reports.
  arg_parser.add_argument('--max_reports', type=int, required=True,
                          help='Maximum num of reports to parse')
  arg_parser.add_argument(
      '--sort_by', choices=['total', 'metal', 'crystal', 'deuterium'],
      default='total', help='What to sort reports by')

  # Use --num_attacks or --csv to choose between actually attacking or
  # exporting reports to CSV.
  group = arg_parser.add_mutually_exclusive_group(required=True)
  group.add_argument('-n', '--num_attacks', type=int, help='Num of attacks')
  group.add_argument(
      '--csv', type=str,
      help='If present, will instead export reports into this CSV file')

  args = arg_parser.parse_args()

  common.setup_logging(args)
  b = common.open_browser_and_connect(args)

  # Parse and sort reports.
  reports = gather_reports(b, args)

  if args.csv:
    export(b, reports, args)
  else:
    attack(b, reports, args)


if __name__ == '__main__':
  main()

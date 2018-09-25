"""Scan closest targets satisfying filters (e.g. inactive, rank > 600)."""
import argparse
import logging
import time

from selenium.webdriver.common.by import By

import common
import selenium_lib as sln


def scan(b, args):
  """Scan closest targets."""
  home_galaxy, home_system = go_to_galaxy_view(b, args.planet_num)
  num_missions = 0
  num_scans = 0
  initial_num_missions = None

  # Use home galaxy or galaxy specified in command line.
  galaxy = args.galaxy or home_galaxy
  if not 1 <= galaxy <= args.num_galaxies:
    raise ValueError('Galaxy should be between 1 and {}; got {}'.format(
        args.num_galaxies, galaxy))
  logging.info('Scanning galaxy {}'.format(galaxy))

  for i, system in enumerate(
          iter_coords(home_system, args.num_systems) if galaxy == home_galaxy
          else range(1, args.num_systems + 1)):
    if i < args.systems_to_skip:
      logging.info('Skipping system {} [{}]'.format(i, system))
      continue

    system_done = False
    num_processed_in_this_system = 0
    while not system_done:
      num_ongoing_missions = go_to_system(b, galaxy, system)

      if initial_num_missions is None:
        initial_num_missions = num_ongoing_missions
      # We count the number of ongoing probe missions by parsing the galaxy page
      # so we need to offset it by the number of ongoing when starting this
      # program.
      num_ongoing_missions -= initial_num_missions
      logging.info('{} ongoing missions'.format(num_ongoing_missions))
      logging.info('{} total scans'.format(num_scans))

      if num_ongoing_missions >= args.parallelism:
        # Wait until a mission is done.
        logging.info('Too many missions. Waiting 10s...')
        time.sleep(10)
        continue

      num_allowed = args.parallelism - num_ongoing_missions
      num_processed, system_done = inspect(
          b, num_processed_in_this_system, num_allowed, galaxy, system,
          args)
      num_processed_in_this_system += num_processed
      num_scans += num_processed
      if num_scans >= args.max_scans:
        logging.info('Reached {} scans. Exiting.'.format(args.max_scans))
        return


def go_to_galaxy_view(b, planet_num):
  """Navigate to galaxy view and return home galaxy and system."""
  planets = sln.finds(sln.find(b, By.ID,
                               'planetList'), By.CLASS_NAME, 'planetlink')
  logging.info('Found {} planets'.format(len(planets)))
  logging.info('Navigating to planet #{}'.format(planet_num))
  planets[planet_num].click()
  logging.info('Navigating to galaxy view')
  sln.finds(sln.find(b, By.ID, 'links'),
            By.CLASS_NAME, 'menubutton')[8].click()

  galaxy = int(sln.find(b, By.ID, 'galaxy_input').get_attribute('value'))
  system = int(sln.find(b, By.ID, 'system_input').get_attribute('value'))
  logging.info('Home system is {}:{}'.format(galaxy, system))

  return galaxy, system


def go_to_system(b, galaxy, system):
  """Navigate to system and return num ongoing missions."""
  logging.info('Navigating to {}:{}'.format(galaxy, system))
  sln.find(b, By.ID, 'galaxy_input').send_keys(str(galaxy))
  sln.find(b, By.ID, 'system_input').send_keys(str(system))
  sln.find(b, By.CSS_SELECTOR, '#galaxyHeader .btn_blue').click()

  # Wait for loader to appear, then wait for it to disappear.
  sln.wait_until(b, By.ID, 'galaxyLoading', timeout=1, timeout_ok=True)
  sln.wait_until_not(b, By.ID, 'galaxyLoading', timeout=3, timeout_ok=True)

  return int(sln.find(b, By.ID, 'slotUsed').text)


def iter_coords(start, num):
  """Generator for next element in a donut system/galaxy."""
  yield start
  odd = num % 2 == 1
  bound = (num + 2) // 2
  for i in range(1, bound):
    yield (start + i) % (num + 1)
    yield (start - i) % (num + 1)
  if odd:
    yield (start + bound) % (num + 1)


def inspect(b, num_already_processed, num_allowed, galaxy, system, args):
  """Inspect a system.

  Args:
    b: Browser.
    num_already_processed: Num already processed in this system.
    num_allowed: Num probes allowed at this point.
    galaxy: Galaxy (for debug).
    system: System (for debug).
    args: Command-line args.

  Returns:
    num_processed: (int) Number of targets newly processed in this system.
    done: (bool) Whether the scan was complete.
  """
  logging.info('Inspecting [{}:{}]...'.format(galaxy, system))

  # Get list of planets in this system.
  players = [p for p in sln.finds(b, By.CSS_SELECTOR, '.playername',
                                  timeout=2, timeout_ok=True)
             if len(p.get_attribute('class').split()) > 1 and
             'js_no_action' not in p.get_attribute('class')]
  logging.info('Found {} players'.format(len(players)))

  # Get list of potential targets based on their class (inactive, strong, etc).
  potential_targets = []
  for player in players:
    classes = player.get_attribute('class').split()
    if len(classes) == 2:  # normal players have 2 classes
      if args.include_normal:
        logging.info('Adding normal player')
        potential_targets.append(player)
    elif any(x in classes for x in ['noob', 'vacation', 'vacationlonginactive',
                                    'vacationinactive', 'banned']):
      pass
    else:
      for classname, arg, label in [
          ('inactive', args.include_inactive, 'inactive'),
          ('longinactive', args.include_inactive, 'inactive'),
          ('honorableTarget', args.include_honorable, 'honorable'),
          ('stronghonorableTarget', args.include_strong, 'strong'),
      ]:
        if classname in classes:
          if arg:
            logging.info('Adding {} player'.format(label))
            potential_targets.append(player)
          break
      else:  # no known classname found
        logging.warn(
            'Skipping unsupported player (classes = {})'.format(classes))
  logging.info('Found {} potential targets'.format(len(potential_targets)))

  # Iterate over potential targets and scan those with rank within bounds.
  num_processed = 0
  for potential_target in potential_targets:
    if num_allowed == 0:
      # Reached max number of concurrent missions.
      return num_processed, False

    # Find player name.
    sln.hover(b, potential_target)
    player_name = potential_target.text

    # Find player ID (sometimes we need to try multiple times).
    player_id, tries = None, 0
    while not player_id and tries < 10:
      tries += 1
      player_id = sln.find(potential_target, By.TAG_NAME,
                           'a').get_attribute('rel')
    if not player_id:
      logging.warn('Skipping (could not find player ID)')
      continue

    # Find player rank. Sometimes it can't be done e.g. if player name is empty.
    player_rank, tries = None, 0
    while not player_rank and tries < 10:
      tries += 1
      for tooltip in sln.finds(b, By.ID, player_id):
        rank = sln.find(tooltip, By.TAG_NAME, 'a').text
        if rank:
          player_rank = int(rank)
          break
    if not player_rank:
      logging.warn('Skipping (could not find player rank')
      continue

    # Find planet name.
    planet_name = sln.find(sln.find(potential_target, By.XPATH, '..'),
                           By.CLASS_NAME, 'planetname').text

    # Find planet position.
    planet_position = int(
        sln.find(sln.find(potential_target, By.XPATH, '..'), By.CLASS_NAME,
                 'position').text)

    logging.info('Potential target: {}:{}:{} [{}] - {} (rank {})'.format(
        galaxy, system, planet_position, planet_name, player_name, player_rank))

    if not args.rank_min <= player_rank <= args.rank_max:
      logging.info('Skipping (outside allowed rank bounds)')
      continue

    if num_already_processed:
      logging.info('Skipping (already processed)')
      num_already_processed -= 1
      continue

    logging.info('--> Sending probe to {}:{}:{}'.format(
        galaxy, system, planet_position))
    sln.click(b, sln.find(sln.find(potential_target, By.XPATH, '..'),
                          By.CLASS_NAME, 'espionage'))
    num_processed += 1
    num_allowed -= 1

  return num_processed, True


def main():
  arg_parser = argparse.ArgumentParser()

  # Register common args.
  common.register_args(arg_parser)

  # Filters for targets.
  arg_parser.add_argument('--include_inactive', type=bool, default=True)
  arg_parser.add_argument('--include_normal', type=bool, default=False)
  arg_parser.add_argument('--include_honorable', type=bool, default=False)
  arg_parser.add_argument('--include_strong', type=bool, default=False)
  arg_parser.add_argument('--rank_min', type=int, required=True,
                          help='Min rank to send probes')
  arg_parser.add_argument('--rank_max', type=int, required=True,
                          help='Max rank to send probes')

  # Scan config.
  arg_parser.add_argument('--planet_num', type=int,
                          default=0, help='Which planet to send probes from')
  arg_parser.add_argument('--parallelism', type=int, required=True,
                          help='Num missions to send at a time')
  arg_parser.add_argument('-n', '--max_scans', type=int, required=True,
                          help='Num of scans before exiting')
  arg_parser.add_argument('--systems_to_skip', type=int,
                          default=0, help='Skip the N closest systems')
  arg_parser.add_argument(
      '--galaxy', type=int,
      help='If present, scan this galaxy instead of the home galaxy')

  # Args for universe structure.
  arg_parser.add_argument('--num_galaxies', type=int, default=7)
  arg_parser.add_argument('--num_systems', type=int, default=499)

  args = arg_parser.parse_args()

  common.setup_logging(args)
  b = common.open_browser_and_connect(args)

  scan(b, args)


if __name__ == '__main__':
  main()

"""Util functions for selenium."""
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def hover(b, element):
  """Hover over an element."""
  hover = ActionChains(b).move_to_element(element)
  hover.perform()


def click(b, element):
  """Click an element."""
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


def find(b, by, element, timeout=10):
  """Wait for element to be present and return it."""
  return WebDriverWait(b, timeout).until(
      EC.presence_of_element_located((by, element)))


def finds(b, by, element, timeout=10, timeout_ok=False):
  """Wait for elements to be present and return them."""
  try:
    return WebDriverWait(b, timeout).until(
        EC.presence_of_all_elements_located((by, element)))
  except TimeoutException:
    if timeout_ok:
      return []
    else:
      raise


def wait_until(b, by, element, timeout=10, timeout_ok=False):
  """Wait for element to be present."""
  try:
    find(b, by, element, timeout)
  except TimeoutException:
    if not timeout_ok:
      raise


def wait_until_not(b, by, element, timeout=10, timeout_ok=False):
  """Wait for element to be present."""
  try:
    WebDriverWait(b, timeout).until_not(
        EC.presence_of_all_elements_located((by, element)))
  except TimeoutException:
    if not timeout_ok:
      raise

"""Utilities for using sizzle (jQuery-style) selectors with Selenium."""

import re

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

from .has_driver import exception_indicates_stale_element

SIZZLE_LOAD_TIMEOUT = 5
SIZZLE_URL = "//cdnjs.cloudflare.com/ajax/libs/sizzle/1.10.18/sizzle.js"


def sizzle_selector_clickable(selector):
    def ec(driver):
        elements = find_elements_by_sizzle(driver, selector)
        if not elements:
            return False
        element = elements[0]
        try:
            clickable = element.is_displayed() and element.is_enabled()
        except Exception as e:
            # Handle the case where the element is detached between when it is
            # discovered and when it is checked - it is likely changing quickly
            # and the next pass will be the final state. If not, this should be
            # wrapped in a wait anyway - so no problems there. For other
            # non-custom selectors I believe this all happens on the Selenium
            # server and so there is likely no need to handle this case - they
            # are effectively atomic.
            if exception_indicates_stale_element(e):
                return None

            raise
        if clickable:
            return element
        else:
            return None

    return ec


def sizzle_presence_of_selector(selector):
    def ec(driver):
        elements = find_elements_by_sizzle(driver, selector)
        if not elements:
            return False
        element = elements[0]
        try:
            displayed = element.is_displayed()
        except Exception as e:
            # See note above insizzle_selector_clickable about this exception.
            if exception_indicates_stale_element(e):
                return None

            raise

        if displayed:
            return element
        else:
            return None

    return ec


def find_element_by_sizzle(driver, sizzle_selector):
    """
    Finds an element by sizzle selector.
    :Args:
     - sizzle_selector: The sizzle selector to use when finding element.
    :Usage:
        driver.find_element_by_sizzle('#foo')
    """
    elements = driver.find_elements_by_sizzle(sizzle_selector)
    if elements:
        return elements[0]
    else:
        raise NoSuchElementException(
            "Unable to locate element by Sizzle: {selector}".format(selector=sizzle_selector)
        )


def find_elements_by_sizzle(driver, sizzle_selector):
    """
    Finds elements by sizzle selector.
    :Args:
     - sizzle_selector: The sizzle selector to use when finding elements.
    :Usage:
        driver.find_elements_by_sizzle('.foo')
    """
    if not _is_sizzle_loaded(driver):
        _inject_sizzle(driver, SIZZLE_URL, SIZZLE_LOAD_TIMEOUT)
    elements = driver.execute_script(_make_sizzle_string(sizzle_selector))
    return elements


def _inject_sizzle(driver, sizzle_url, timeout):
    script = """
        if(typeof(window.$) != "undefined") {
            // Just reuse jQuery if it is available, avoids potential amd problems
            // that have cropped up with Galaxy for instance.
            window.Sizzle = window.$;
        } else {
            var _s = document.createElement("script");
            _s.type = "text/javascript";
            _s.src = "%s";
            var _h = document.getElementsByTagName("head")[0];
            _h.appendChild(_s);
        }
    """ % sizzle_url
    driver.execute_script(script)
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: _is_sizzle_loaded(d),
               "Can't inject Sizzle in {timeout} seconds".format(timeout=timeout))


def _is_sizzle_loaded(driver):
    script = "return typeof(Sizzle) != \"undefined\";"
    return driver.execute_script(script)


def _make_sizzle_string(sizzle_selector):
    try:
        selector = sizzle_selector.decode("utf-8")
    except (AttributeError, UnicodeEncodeError):
        selector = sizzle_selector
    return u"return Sizzle(\"{selector}\");".format(selector=re.escape(selector))


__all__ = (
    "find_element_by_sizzle",
    "find_elements_by_sizzle",
    "sizzle_selector_clickable",
    "sizzle_presence_of_selector",
)

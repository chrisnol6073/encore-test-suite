# Verifies the FIRST20 discount rule from PRD footnote [^2]: 20% off ANY seat
# regardless of tier, on a guest's first completed booking in a session.
#
# The booking is deliberately mixed-tier (one VIP seat + one Standard seat).
# A code that only discounted Standard seats (like SAVE10) or ignored the tier
# would produce a different discount and total, so this order breaks if the rule
# isn't followed. The code is typed in lowercase to also cover the PRD's
# "matched case-insensitively" rule.
#
# Expected values are COMPUTED from the seat prices shown on the seat map
# (content-desc "Seat A1, vip, available, $135"), not copied from the payment
# screen, so the assertion can fail if the app mis-computes the discount.
#
# Run via the BrowserStack Python SDK (browserstack-sdk), which reads
# ../browserstack.yml for credentials, the app, and device details.

import re
from decimal import Decimal, ROUND_HALF_UP

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NAV_WAIT_SECONDS = 20
EVENT_TEST_ID = "event-card-evt-28"  # "City Derby Night" — 16 VIP + 32 Standard seats
VIP_SEAT_TEST_ID = "seat-A1"  # row A is VIP tier
STANDARD_SEAT_TEST_ID = "seat-C1"  # row C is Standard tier
DISCOUNT_CODE = "first20"  # PRD: FIRST20, entered case-insensitively
DISCOUNT_RATE = Decimal("0.20")


def by_resource_id(resource_id):
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}")')


def money(text):
    """Parse '$135', '-$41.40' or 'USD 165.60' into a Decimal."""
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    assert match, f"no amount found in {text!r}"
    return Decimal(match.group(1))


def cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def seat_price(driver, wait, resource_id):
    """Read the seat's base price from its content-desc, e.g. 'Seat A1, vip, available, $135'."""
    seat = wait.until(EC.presence_of_element_located(by_resource_id(resource_id)))
    return money(seat.get_attribute("content-desc").split(",")[-1])


def text_of(wait, resource_id):
    return wait.until(EC.presence_of_element_located(by_resource_id(resource_id))).text


def test_first20_discounts_vip_and_standard_seats():
    options = UiAutomator2Options()
    driver = webdriver.Remote("http://localhost:4723/wd/hub", options=options)

    try:
        wait = WebDriverWait(driver, NAV_WAIT_SECONDS)

        wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Continue as Guest"))).click()

        wait.until(EC.presence_of_element_located(by_resource_id("event-list-screen")))
        wait.until(
            EC.presence_of_element_located(
                (
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().resourceId("event-list").scrollable(true))'
                    f'.scrollIntoView(new UiSelector().resourceId("{EVENT_TEST_ID}"))',
                )
            )
        ).click()

        wait.until(EC.presence_of_element_located(by_resource_id("select-seat-button"))).click()

        # Mixed-tier order: one VIP seat and one Standard seat.
        vip_price = seat_price(driver, wait, VIP_SEAT_TEST_ID)
        standard_price = seat_price(driver, wait, STANDARD_SEAT_TEST_ID)
        assert vip_price > standard_price, "precondition: VIP seat must cost more than Standard"

        wait.until(EC.presence_of_element_located(by_resource_id(VIP_SEAT_TEST_ID))).click()
        wait.until(EC.presence_of_element_located(by_resource_id(STANDARD_SEAT_TEST_ID))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("seat-selection-continue-button"))).click()

        # Apply FIRST20 on this (first) booking of the session.
        wait.until(EC.presence_of_element_located(by_resource_id("discount-input"))).send_keys(DISCOUNT_CODE)
        wait.until(EC.presence_of_element_located(by_resource_id("discount-apply-button"))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("discount-remove-button")))
        wait.until(EC.presence_of_element_located(by_resource_id("discount-continue-button"))).click()

        # Expected values computed from the base prices and the PRD rule.
        expected_subtotal = vip_price + standard_price
        expected_vip_line = cents(vip_price * (1 - DISCOUNT_RATE))
        expected_standard_line = cents(standard_price * (1 - DISCOUNT_RATE))
        expected_discount = cents(expected_subtotal * DISCOUNT_RATE)
        expected_total = cents(expected_subtotal - expected_discount)

        wait.until(EC.presence_of_element_located(by_resource_id("payment-screen")))

        assert money(text_of(wait, "payment-subtotal")) == expected_subtotal
        # 20% must apply to the VIP seat too, not just Standard.
        assert money(text_of(wait, "payment-line-price-A1")) == expected_vip_line
        assert money(text_of(wait, "payment-line-price-C1")) == expected_standard_line
        assert money(text_of(wait, "payment-discount-amount")) == expected_discount
        assert money(text_of(wait, "payment-total")) == expected_total
        print(
            "[test_first20_mixed_tier_discount] final total",
            text_of(wait, "payment-total"),
            "expected",
            expected_total,
        )
    finally:
        driver.quit()

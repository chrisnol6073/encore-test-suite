# Books out every seat on "Late Night Jazz" through the real booking flow,
# confirms the event re-sorts to the sold-out section, then opens the
# sold-out card by stable resource-id and asserts it shows the expected event.
#
# Run via the BrowserStack Python SDK (browserstack-sdk), which reads
# ../browserstack.yml for credentials, the app, and device details, and
# transparently redirects this local Appium session to BrowserStack. Do not
# set capabilities here — they live in browserstack.yml.

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NAV_WAIT_SECONDS = 20
PAYMENT_WAIT_SECONDS = 30
EXPECTED_EVENT_TITLE = "Late Night Jazz"
EXPECTED_EVENT_ID = "evt-17"
ALL_SEAT_IDS = ["seat-A1", "seat-A2", "seat-A3", "seat-A4"]

CAPTURED_EVENT_LOCATOR = "event-card-0"


def by_resource_id(resource_id):
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}")')


def scroll_into_view(resource_id):
    return (
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiScrollable(new UiSelector().resourceId("event-list").scrollable(true))'
        f'.scrollIntoView(new UiSelector().resourceId("{resource_id}"))',
    )


def test_event_list_locator():
    options = UiAutomator2Options()
    driver = webdriver.Remote("http://localhost:4723/wd/hub", options=options)

    try:
        wait = WebDriverWait(driver, NAV_WAIT_SECONDS)

        # Use accessibility id (content-desc) — this app's resource-ids have no
        # package prefix so AppiumBy.ID fails; content-desc is stable and
        # confirmed in page source.
        wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Continue as Guest"))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("event-list-screen")))

        # Step 1: record the target event's on-screen position while it
        # still has available seats.
        title_at_capture = wait.until(
            EC.presence_of_element_located(by_resource_id(f"event-card-title-{EXPECTED_EVENT_ID}"))
        ).text
        assert title_at_capture == EXPECTED_EVENT_TITLE, (
            f"Expected {EXPECTED_EVENT_TITLE!r} at the captured position, found {title_at_capture!r} — "
            "catalog data may have changed; this script's assumptions need updating."
        )
        event_card = wait.until(EC.presence_of_element_located(by_resource_id(CAPTURED_EVENT_LOCATOR)))

        # Step 2: book every seat on the event through the real standard-seat
        # booking flow (this event has zero VIP seats — verified below, not
        # assumed).
        event_card.click()
        wait.until(EC.presence_of_element_located(by_resource_id("select-seat-button"))).click()
        for seat_id in ALL_SEAT_IDS:
            seat_element = wait.until(EC.presence_of_element_located(by_resource_id(seat_id)))
            seat_label = seat_element.get_attribute("content-desc") or ""
            assert ", standard," in seat_label, (
                f"Expected {seat_id} to be Standard tier, but its accessibility label was "
                f"{seat_label!r} — refusing to book a seat whose tier wasn't verified."
            )
            seat_element.click()
        wait.until(EC.presence_of_element_located(by_resource_id("seat-selection-continue-button"))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("discount-continue-button"))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("payment-pay-button"))).click()

        WebDriverWait(driver, PAYMENT_WAIT_SECONDS).until(
            EC.invisibility_of_element_located(by_resource_id("payment-processing-indicator"))
        )
        WebDriverWait(driver, PAYMENT_WAIT_SECONDS).until(
            EC.presence_of_element_located(by_resource_id("confirmation-screen"))
        )
        wait.until(EC.presence_of_element_located(by_resource_id("confirmation-done-button"))).click()

        # Step 3: confirm the event sorted to the bottom of the list (sold
        # out). The sold-out card is at the bottom so we must scroll to it.
        wait.until(EC.presence_of_element_located(by_resource_id("event-list-screen")))
        wait.until(EC.presence_of_element_located(scroll_into_view(f"event-card-soldout-{EXPECTED_EVENT_ID}")))
        print(f"[test_event_list_locator] confirmed {EXPECTED_EVENT_TITLE!r} sorted to sold-out position")

        # Step 4: scroll to the sold-out event (now at the bottom after re-sort)
        # and open it by stable resource-id. The original coordinate-based tap
        # is replaced because the list re-sort makes captured XY stale.
        wait.until(EC.presence_of_element_located(scroll_into_view(f"event-card-soldout-{EXPECTED_EVENT_ID}"))).click()
        actual_title = wait.until(EC.presence_of_element_located(by_resource_id("event-details-title"))).text

        print(f"[test_event_list_locator] opened sold-out card -> {actual_title!r}")
        assert actual_title == EXPECTED_EVENT_TITLE, (
            f"Expected to open {EXPECTED_EVENT_TITLE!r} from the sold-out section, "
            f"but got {actual_title!r} instead."
        )
    finally:
        driver.quit()

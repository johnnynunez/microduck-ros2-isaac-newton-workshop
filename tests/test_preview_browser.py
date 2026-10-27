"""Optional real Chromium UI tests, using explicitly SYNTHETIC JPEG fixtures."""

import io
import json
import os
import shutil
import time
from pathlib import Path

import pytest
from test_preview import synthetic_frame, synthetic_health
from test_preview import synthetic_upstream as source_fixture

synthetic_upstream = source_fixture


@pytest.fixture
def page():
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("Chromium is not installed")
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        yield page
        browser.close()


def prepare_browser_source(source):
    image = pytest.importorskip("PIL.Image")
    output = io.BytesIO()
    image.new("RGB", (32, 24), color=(70, 100, 120)).save(output, format="JPEG")
    synthetic_frame(source)
    source.body = output.getvalue()  # Explicitly synthetic; never native camera evidence.
    source.routes["/v1/health"] = (
        200,
        {"Content-Type": "application/json"},
        json.dumps(synthetic_health()).encode(),
    )
    return dict(source.headers)


def test_browser_live_stale_offline_and_independent_views(page, synthetic_upstream):
    source = synthetic_upstream
    headers = prepare_browser_source(source)
    fresh = lambda: dict(headers, **{"X-Microduck-Capture-Monotonic": str(time.monotonic())})
    source.routes["/v1/camera"] = (200, fresh, source.body)
    source.routes["/v1/overview"] = (503, {}, b"not captured")
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda req: requests.append((req.method, req.url)))
    page.goto(f"http://127.0.0.1:{source.portal.server_port}")
    page.locator('#head[data-state="live"]').wait_for(timeout=5000)
    assert page.locator("#head img").is_visible()
    assert page.locator("#overview").get_attribute("data-state") == "offline"
    assert page.locator("#overview img").is_hidden()
    assert page.locator("#head .epoch").inner_text() == "SYNTHETIC"
    assert page.locator("button, input, form").count() == 0
    source.routes["/v1/camera"] = (200, dict(headers), source.body)
    page.locator('#head[data-state="stale"]').wait_for(timeout=5000)
    assert "STALE" in page.locator("#head .image-warning").inner_text()
    old_url = page.locator("#head img").get_attribute("src")
    source.routes["/v1/camera"] = (503, {}, b"offline")
    page.locator('#head[data-state="offline"]').wait_for(timeout=5000)
    assert page.locator("#head img").is_visible()
    assert "LAST IMAGE" in page.locator("#head .image-warning").inner_text()
    assert page.locator("#head img").get_attribute("src") == old_url
    assert not errors
    assert all(method == "GET" for method, _ in requests)
    origin = f"http://127.0.0.1:{source.portal.server_port}/"
    assert all(url.startswith((origin, "blob:" + origin)) for _, url in requests)


def test_browser_status_failure_and_epoch_mismatch_prevent_live(page, synthetic_upstream):
    source = synthetic_upstream
    headers = prepare_browser_source(source)
    source.routes["/v1/camera"] = (
        200,
        lambda: dict(headers, **{"X-Microduck-Capture-Monotonic": str(time.monotonic())}),
        source.body,
    )
    page.goto(f"http://127.0.0.1:{source.portal.server_port}")
    page.locator('#head[data-state="live"]').wait_for(timeout=5000)
    health = synthetic_health()
    health["episode_id"] = "NEW_EPOCH"
    source.routes["/v1/health"] = (
        200,
        {"Content-Type": "application/json"},
        json.dumps(health).encode(),
    )
    page.locator('#head[data-state="stale"]').wait_for(timeout=5000)
    assert "epoch" in page.locator("#head .feed-note").inner_text().lower()
    source.routes["/v1/health"] = (503, {}, b"offline")
    page.locator('#runtime-state[data-state="offline"]').wait_for(timeout=5000)
    assert page.locator("#head").get_attribute("data-state") != "live"
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_same_origin_secure_link_cookie_is_kept_at_browser_boundary(page, synthetic_upstream):
    source = synthetic_upstream
    headers = prepare_browser_source(source)
    source.routes["/v1/camera"] = (
        200,
        lambda: dict(headers, **{"X-Microduck-Capture-Monotonic": str(time.monotonic())}),
        source.body,
    )
    url = f"http://127.0.0.1:{source.portal.server_port}"
    page.context.add_cookies([{"name": "preview_auth", "value": "synthetic-cookie", "url": url}])

    def authenticated_link(route):
        if "preview_auth=synthetic-cookie" in route.request.all_headers().get("cookie", ""):
            route.continue_()
        else:
            route.fulfill(status=401, body="Synthetic Secure Link auth boundary")

    page.route("**/status", authenticated_link)
    page.goto(url)
    page.locator('#head[data-state="live"]').wait_for(timeout=5000)
    assert all("Cookie" not in headers for _, headers in source.seen)


def test_corrupt_jpeg_never_replaces_last_decoded_frame(page, synthetic_upstream):
    source = synthetic_upstream
    headers = prepare_browser_source(source)
    fresh = lambda: dict(headers, **{"X-Microduck-Capture-Monotonic": str(time.monotonic())})
    source.routes["/v1/camera"] = (200, fresh, source.body)
    page.goto(f"http://127.0.0.1:{source.portal.server_port}")
    page.locator('#head[data-state="live"]').wait_for(timeout=5000)
    # Freeze the stream before checking its retained identity.
    source.routes["/v1/camera"] = (200, dict(headers), source.body)
    page.locator('#head[data-state="stale"]').wait_for(timeout=5000)
    last = page.locator("#head img").get_attribute("src")
    source.routes["/v1/camera"] = (
        200,
        dict(headers, **{"X-Microduck-Sequence": "43"}),
        b"\xff\xd8SYNTHETIC-CORRUPT-NOT-A-JPEG\xff\xd9",
    )
    page.locator('#head[data-state="offline"]').wait_for(timeout=5000)
    assert page.locator("#head img").get_attribute("src") == last
    assert page.locator("#head .sequence").inner_text() == "42"


def test_recorded_camera_visual_only_qa(page, synthetic_upstream):
    path = os.environ.get("PREVIEW_RECORDED_JPEG")
    if not path:
        pytest.skip("Optional recorded-camera visual QA; not live acceptance")
    source = synthetic_upstream
    prepare_browser_source(source)
    synthetic_frame(source, age=3600)
    source.headers["X-Microduck-Episode"] = "RECORDED_QA_NOT_LIVE"
    health = synthetic_health()
    health["episode_id"] = "RECORDED_QA_NOT_LIVE"
    health["ready"] = False
    source.routes["/v1/health"] = (
        200,
        {"Content-Type": "application/json"},
        json.dumps(health).encode(),
    )
    source.routes["/v1/overview"] = (503, {}, b"No recorded overview exists")
    source.body = Path(path).read_bytes()
    page.goto(f"http://127.0.0.1:{source.portal.server_port}")
    page.locator('#head[data-state="stale"] img').wait_for(timeout=5000)
    assert page.locator("#head .epoch").inner_text() == "RECORDED_QA_NOT_LIVE"
    assert page.locator("#overview img").is_hidden()
    output = Path(".workshop/preview-qa")
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "recorded-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / "recorded-mobile.png"), full_page=True)
    source.routes["/v1/camera"] = (503, {}, b"Offline after recorded frame")
    page.locator('#head[data-state="offline"]').wait_for(timeout=5000)
    assert page.locator("#head img").is_visible()
    page.set_viewport_size({"width": 1440, "height": 1100})
    page.screenshot(path=str(output / "recorded-offline.png"), full_page=True)

"""Interaction regressions exercised by flow_canvas_gate.py's fresh account."""
import json
import math
import time

from playwright.sync_api import expect

from browser_gate import BASE, step


class FlowMotionChecks:
    def __init__(self, page, call):
        self.page = page
        self.call = call

    def report(self, name, body=None):
        return self.call(self.page, name, body or {})

    def fresh(self, specs, label=""):
        self.report("DeleteFlowLine")
        rows = [self.report("SaveStep", {"name": name, "x": x, "y": y}) for name, x, y in specs]
        if label:
            link = {"from_id": rows[0]["id"], "to_id": rows[1]["id"]}
            assert self.report("LinkTransition", link)["ok"]
            assert self.report("LabelTransition", {**link, "label": label})["ok"]
        self.page.evaluate("localStorage.setItem('flowline_wf_view', 'flow')")
        self.page.goto(BASE + "/flowlines?start=blank")
        expect(self.page.locator("[data-step]")).to_have_count(len(rows))
        expect(self.page.locator("[data-zoom]")).to_be_visible()
        self.page.evaluate("() => document.fonts.ready")
        # Both fit passes and the font-ready effect run on animation frames.
        self.page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        return rows

    def node(self, row):
        return self.page.locator(f'[data-step="{row["id"]}"]')

    def positions(self):
        return {s["id"]: (s["x"], s["y"]) for s in self.report("GetFlowLine", {"with_counts": False})}

    def wait_for(self, condition, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if condition():
                return
            self.page.wait_for_timeout(50)
        raise AssertionError(message)

    def held_drag(self, row, dx, dy):
        box = self.node(row).bounding_box()
        assert box, row
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + dx, y + dy, steps=12)
        return self.node(row).bounding_box()

    def drop(self, row, dx, dy):
        self.held_drag(row, dx, dy)
        with self.page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/walker/MoveStep")) as saved:
            self.page.mouse.up()
        assert saved.value.ok, saved.value.text()
        saved.value.json()
        return saved.value.request.post_data_json

    def overlap(self):
        step("motion: overlapping steps drag the visible front step")
        front, back = self.fresh([("Front step", 0, 0), ("Back step", 240, 0)])
        self.node(front).click()
        expect(self.page.get_by_role("textbox", name="Step name", exact=True)).to_have_value("Front step")
        self.drop(front, 240, 0)
        box = self.node(front).bounding_box()
        top = self.page.evaluate(
            "b => document.elementFromPoint(b.x+b.width/2, b.y+b.height/2).closest('[data-step]').getAttribute('data-step')",
            box,
        )
        assert top == front["id"], "The selected step must be visually on top"
        saved = self.drop(front, 75, 0)
        assert saved["step_id"] == top, saved
        positions = self.positions()
        assert positions[front["id"]] == (315, 0), positions
        assert positions[back["id"]] == (240, 0), positions

    def stale_refresh(self):
        step("motion: a delayed refresh cannot interrupt an active drag")
        row, = self.fresh([("Slow refresh", 0, 0)])
        held = []

        def hold_read(route):
            held.append((route, route.fetch()))

        self.page.route("**/walker/GetFlowLine", hold_read)
        try:
            self.drop(row, 80, 0)
            self.wait_for(lambda: bool(held), "The first drop did not refresh the flow")
            before = self.held_drag(row, 80, 0)
            route, response = held.pop(0)
            route.fulfill(response=response)
            self.page.unroute("**/walker/GetFlowLine", hold_read)
            # Give the older refresh a chance to settle while the pointer is held.
            self.page.wait_for_timeout(250)
            after = self.node(row).bounding_box()
            assert math.isclose(before["x"], after["x"], abs_tol=1), (before, after)
            assert math.isclose(before["y"], after["y"], abs_tol=1), (before, after)
            with self.page.expect_response(lambda r: r.url.endswith("/walker/MoveStep")) as saved:
                self.page.mouse.up()
            assert saved.value.ok, saved.value.text()
            assert self.positions()[row["id"]] == (160, 0)
        finally:
            self.page.unroute("**/walker/GetFlowLine", hold_read)
            for route, response in held:
                route.fulfill(response=response)

    def delayed_write(self):
        step("motion: a delayed first write cannot overwrite the latest drop")
        row, = self.fresh([("Queued saves", 0, 0)])
        held = []
        responses = []
        intercepted = [False]

        def hold_first(route):
            if not intercepted[0]:
                intercepted[0] = True
                held.append(route)
            else:
                route.continue_()

        def responded(response):
            if response.url.endswith("/walker/MoveStep"):
                responses.append(response)

        self.page.route("**/walker/MoveStep", hold_first)
        self.page.on("response", responded)
        try:
            self.held_drag(row, 80, 0)
            self.page.mouse.up()
            self.wait_for(lambda: bool(held), "The first position write did not start")
            last_box = self.held_drag(row, 80, 0)
            self.page.mouse.up()
            self.page.wait_for_timeout(150)
            held.pop(0).continue_()
            self.page.unroute("**/walker/MoveStep", hold_first)
            self.wait_for(lambda: len(responses) == 2, "Both position writes did not finish")
            for response in responses:
                assert response.ok, response.text()
                response.json()
            assert self.positions()[row["id"]] == (160, 0)
            self.page.wait_for_timeout(150)
            after = self.node(row).bounding_box()
            assert math.isclose(last_box["x"], after["x"], abs_tol=1), (last_box, after)
        finally:
            self.page.unroute("**/walker/MoveStep", hold_first)
            self.page.remove_listener("response", responded)
            for route in held:
                route.continue_()

    def failed_write(self):
        step("motion: a failed save restores the stored position and allows another drag")
        row, = self.fresh([("Failed save", 0, 0)])
        before = self.node(row).bounding_box()

        def reject(route):
            route.fulfill(status=500, content_type="application/json", body='{"detail":"Motion gate failure"}')

        self.page.route("**/walker/MoveStep", reject)
        try:
            self.held_drag(row, 80, 0)
            self.page.mouse.up()
            expect(self.page.get_by_text("Failed to save the position", exact=True)).to_be_visible()
            self.wait_for(
                lambda: math.isclose(self.node(row).bounding_box()["x"], before["x"], abs_tol=1),
                "The failed save did not restore the stored position",
            )
            assert self.positions()[row["id"]] == (0, 0)
        finally:
            self.page.unroute("**/walker/MoveStep", reject)
        self.drop(row, 40, 0)
        assert self.positions()[row["id"]] == (40, 0)

    def large_fit(self):
        step("motion: Fit shows every step across wide and tall canvases")
        for extent in (3000, 19900):
            rows = self.fresh([("Top left", -extent, -extent), ("Bottom right", extent, extent)])
            self.page.get_by_role("button", name="Fit", exact=True).click()
            self.page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            viewport = self.page.locator('[data-canvas="flow"]').bounding_box()
            for row in rows:
                box = self.node(row).bounding_box()
                assert box["x"] >= viewport["x"] - 1, (box, viewport)
                assert box["y"] >= viewport["y"] - 1, (box, viewport)
                assert box["x"] + box["width"] <= viewport["x"] + viewport["width"] + 1, (box, viewport)
                assert box["y"] + box["height"] <= viewport["y"] + viewport["height"] + 1, (box, viewport)
            zoom = float(self.page.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
            assert 0 < zoom < 30, zoom
            # A fitted fraction can round to the same readout as the next
            # stop; two presses must still advance visibly out of overview.
            next_zoom = zoom
            for _ in range(2):
                self.page.get_by_role("button", name="Zoom in", exact=True).click()
                next_zoom = float(self.page.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
                if next_zoom > zoom:
                    break
            assert next_zoom > zoom, (zoom, next_zoom)

    def negative_labels(self):
        step("motion: transition labels remain visible at far negative coordinates")
        self.fresh([("Left step", -12000, 0), ("Right step", -11600, 0)], label="Ready to review")
        expect(self.page.locator('[data-chip="label"]')).to_have_count(1)
        expect(self.page.locator('[data-chip="label"]')).to_be_visible()
        expect(self.page.locator('[data-chip="label"]')).to_have_text("Ready to review")
        assert self.page.locator("[data-wire]").count() == 1

    def boundaries(self):
        step("motion: dragging past each coordinate boundary stops smoothly")
        for x, y, dx, dy, expected in (
            (19980, 0, 50, 0, (20000, 0)),
            (-19980, 0, -50, 0, (-20000, 0)),
            (0, 19980, 0, 50, (0, 20000)),
            (0, -19980, 0, -50, (0, -20000)),
        ):
            row, = self.fresh([("Boundary", x, y)])
            self.page.locator("[data-zoom]").click()
            before = self.node(row).bounding_box()
            saved = self.drop(row, dx, dy)
            assert (saved["x"], saved["y"]) == expected, saved
            stored = self.positions()[row["id"]]
            assert stored == expected, ("boundary position", stored, expected)
            after = self.node(row).bounding_box()
            assert math.isclose(after["x"] - before["x"], expected[0] - x, abs_tol=1), (before, after)
            assert math.isclose(after["y"] - before["y"], expected[1] - y, abs_tol=1), (before, after)
        probe = self.report("SaveStep", {"name": "Clamped create", "x": -25000, "y": 25000})
        assert (probe["x"], probe["y"]) == (-20000, 20000), probe
        # The backend may reject non-standard JSON numbers before the walker;
        # if it accepts them, neither the envelope nor the graph may keep them.
        token = self.page.evaluate("localStorage.getItem('jac_token')")
        for value in (float("nan"), float("inf"), -float("inf")):
            response = self.page.request.post(
                BASE + "/walker/MoveStep",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                data=json.dumps({"step_id": probe["id"], "x": value, "y": value}),
            )
            assert response.ok or response.status in (400, 422), response.text()
            if response.ok:
                def reject_constant(value):
                    raise AssertionError("Non-finite response value: " + value)

                payload = json.loads(response.text(), parse_constant=reject_constant)
                stored = self.positions()[probe["id"]]
                assert all(math.isfinite(v) for v in stored), stored
                if (payload.get("data") or {}).get("reports"):
                    assert stored == (0, 0), ("non-finite position", value, stored, payload)

    def pan_and_zoom(self):
        step("motion: small flows pan freely, wheel-pan, and recover with Fit")
        row, = self.fresh([("Free canvas", 0, 0)])
        viewport = self.page.locator('[data-canvas="flow"]').bounding_box()
        before = self.node(row).bounding_box()
        x, y = viewport["x"] + 50, viewport["y"] + 50
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + 100, y + 80, steps=12)
        self.page.mouse.up()
        after = self.node(row).bounding_box()
        assert math.isclose(after["x"] - before["x"], 100, abs_tol=1), (before, after)
        assert math.isclose(after["y"] - before["y"], 80, abs_tol=1), (before, after)
        self.page.mouse.wheel(70, 40)
        self.wait_for(
            lambda: math.isclose(self.node(row).bounding_box()["x"], after["x"] - 70, abs_tol=1),
            "Wheel panning did not move a small flow",
        )
        assert self.positions()[row["id"]] == (0, 0), "Panning must not move the stored step"
        self.page.get_by_role("button", name="Fit", exact=True).click()
        self.page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        expect(self.node(row)).to_be_in_viewport()

        step("motion: wheel zoom keeps the point under the cursor anchored")
        before = self.node(row).bounding_box()
        before_zoom = float(self.page.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
        px, py = before["x"] + before["width"] / 2 + 50, before["y"] + before["height"] / 2 + 20
        self.page.mouse.move(px, py)
        self.page.keyboard.down("Control")
        self.page.mouse.wheel(0, -40)
        self.page.keyboard.up("Control")
        self.wait_for(lambda: self.node(row).bounding_box()["width"] > before["width"] + 1, "Wheel zoom did not change scale")
        after = self.node(row).bounding_box()
        # Text keeps its screen size, so card width is not a scale measure.
        after_zoom = float(self.page.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
        scale = after_zoom / before_zoom
        cx, cy = before["x"] + before["width"] / 2, before["y"] + before["height"] / 2
        assert math.isclose(after["x"] + after["width"] / 2, px + (cx - px) * scale, abs_tol=1), (before, after, scale)
        assert math.isclose(after["y"] + after["height"] / 2, py + (cy - py) * scale, abs_tol=1), (before, after, scale)

    def lanes(self):
        step("motion: switching to lanes preserves saved flow positions")
        rows = self.fresh([("First lane step", -100, 0), ("Second lane step", 400, 200)])
        before = self.positions()
        self.page.get_by_role("button", name="Done editing", exact=True).click()
        self.page.get_by_role("button", name="Lanes", exact=True).click()
        for row in rows:
            expect(self.node(row)).to_be_in_viewport()
        self.page.get_by_role("button", name="Fit", exact=True).click()
        assert self.positions() == before
        self.page.get_by_role("button", name="Flow", exact=True).click()
        for row in rows:
            expect(self.node(row)).to_be_in_viewport()
        self.page.screenshot(path=".jac/flow-motion-desktop.png", full_page=True)

    def touch(self):
        step("motion: phone touch dragging, panning, pinch zoom, and large-flow Fit")
        context = self.page.context.browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
            storage_state=self.page.context.storage_state(),
        )
        mobile = context.new_page()
        mobile.set_default_timeout(20000)
        errors = []
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        try:
            checks = FlowMotionChecks(mobile, self.call)
            mobile.goto(BASE + "/flowlines?start=blank")
            row, = checks.fresh([("Touch", 0, 0)])
            checks.node(row).scroll_into_view_if_needed()
            cdp = context.new_cdp_session(mobile)

            def gesture(points, targets):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": points})
                for n in range(1, 9):
                    moved = [
                        {**a, "x": a["x"] + (b["x"] - a["x"]) * n / 8,
                         "y": a["y"] + (b["y"] - a["y"]) * n / 8}
                        for a, b in zip(points, targets)
                    ]
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": moved})

            box = checks.node(row).bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            gesture([{"id": 1, "x": x, "y": y}], [{"x": x - 60, "y": y - 30}])
            with mobile.expect_response(lambda r: r.url.endswith("/walker/MoveStep")) as saved:
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            assert saved.value.ok, saved.value.text()
            stored = checks.positions()[row["id"]]
            assert math.isclose(stored[0], -60, abs_tol=1) and math.isclose(stored[1], -30, abs_tol=1), stored

            frame = mobile.locator('[data-canvas="flow"]').bounding_box()
            before = checks.node(row).bounding_box()
            x, y = frame["x"] + 25, max(frame["y"] + 25, 40)
            gesture([{"id": 2, "x": x, "y": y}], [{"x": x + 40, "y": y + 30}])
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            after = checks.node(row).bounding_box()
            assert math.isclose(after["x"] - before["x"], 40, abs_tol=1), (before, after)
            assert math.isclose(after["y"] - before["y"], 30, abs_tol=1), (before, after)

            x, y = after["x"] + after["width"] / 2, after["y"] + after["height"] / 2
            before_zoom = float(mobile.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
            gesture(
                [{"id": 3, "x": x - 35, "y": y}, {"id": 4, "x": x + 35, "y": y}],
                [{"x": x - 50, "y": y}, {"x": x + 50, "y": y}],
            )
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            after_zoom = float(mobile.locator("[data-zoom]").get_attribute("data-zoom").rstrip("%"))
            assert after_zoom > before_zoom, (before_zoom, after_zoom)
            assert checks.positions()[row["id"]] == stored
            checks.large_fit()
            mobile.get_by_role("button", name="Fit", exact=True).click()
            mobile.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            mobile.screenshot(path=".jac/flow-motion-mobile.png", full_page=True)
            assert not errors, errors
        finally:
            context.close()


def run_motion_checks(page, call):
    checks = FlowMotionChecks(page, call)
    for check in (
        checks.overlap, checks.stale_refresh, checks.delayed_write, checks.failed_write,
        checks.large_fit, checks.negative_labels, checks.boundaries,
        checks.pan_and_zoom, checks.lanes, checks.touch,
    ):
        check()

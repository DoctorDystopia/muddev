"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Cases for the status endpoint that the website reads.

             No database: the payload takes a stub session handler, and the
             resource renders a Twisted DummyRequest.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.serverstatus.tests.test_status
"""

import json
import unittest
from unittest import mock

from twisted.web import resource
from twisted.web.server import UnsupportedMethod
from twisted.web.test.requesthelper import DummyRequest

from server.conf import web_plugins
from systems.interface.serverstatus import status


# ─── Private constant definitions ────────────────────────────────────────────

_PLAYERS = 3

_CHILD_NAME = status.STATUS_PATH.encode("utf-8")


class _StubSessions:
    """A session handler with a fixed account count."""

    def __init__(self, count: int):
        self._count = count

    def account_count(self) -> int:
        return self._count


def _request(method: bytes) -> DummyRequest:
    request = DummyRequest([_CHILD_NAME])
    request.method = method
    return request


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestStatusPayload(unittest.TestCase):
    """The payload says "up" and gives the account count."""

    def test_it_says_online_with_the_count(self):
        payload = status.status_payload(_StubSessions(_PLAYERS))

        self.assertIs(True, payload[status.FIELD_ONLINE])
        self.assertEqual(_PLAYERS, payload[status.FIELD_PLAYERS])

    def test_an_empty_server_is_still_online(self):
        payload = status.status_payload(_StubSessions(0))

        self.assertIs(True, payload[status.FIELD_ONLINE])
        self.assertEqual(0, payload[status.FIELD_PLAYERS])


class TestStatusResource(unittest.TestCase):
    """The resource answers JSON that no cache between may keep."""

    def setUp(self):
        self.resource = status.StatusResource()
        patcher = mock.patch.object(
            status.evennia, "SESSION_HANDLER", _StubSessions(_PLAYERS))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_answers_the_payload_as_json(self):
        request = _request(b"GET")

        body = self.resource.render(request)

        expected = status.status_payload(_StubSessions(_PLAYERS))
        self.assertEqual(expected, json.loads(body))
        content_type = request.responseHeaders.getRawHeaders(b"content-type")
        self.assertIn(b"json", content_type[0])

    def test_no_cache_may_keep_it(self):
        request = _request(b"GET")

        self.resource.render(request)

        cache_control = request.responseHeaders.getRawHeaders(b"cache-control")
        self.assertIn(b"no-store", cache_control[0])

    def test_a_write_is_refused(self):
        request = _request(b"POST")

        with self.assertRaises(UnsupportedMethod):
            self.resource.render(request)


class TestMount(unittest.TestCase):
    """The web plugin hook puts the resource on the root, beside Django."""

    def test_the_hook_mounts_the_resource(self):
        root = resource.Resource()

        returned = web_plugins.at_webserver_root_creation(root)

        self.assertIs(root, returned)
        self.assertIsInstance(root.children[_CHILD_NAME], status.StatusResource)

    def test_the_child_wins_over_a_dynamic_root(self):
        # DjangoWebRoot hands every path to Django from getChild. A child
        # added with putChild must be found first.
        class _CatchAll(resource.Resource):
            def getChild(self, path, request):
                return resource.NoResource()

        root = status.mount(_CatchAll())

        child = root.getChildWithDefault(_CHILD_NAME, _request(b"GET"))

        self.assertIsInstance(child, status.StatusResource)

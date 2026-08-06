"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/31/2026
Description: Round-trip tests for the shopkeep ware labels.

EvMenu's list_node hands the SELECTED LABEL back to the select callback, so
the label producer and the label matcher must agree exactly. When those were
four separate copies in two formats, any edit to one silently broke selection
-- every item would report "no longer available". These tests pin the
round-trip for both the buy and sell price fields.

Pure functions: no Django, no DB.
"""

from unittest import TestCase

from systems.menus.npc_dialogues.npc_shopkeep import (
    BUY_PRICE_ATTR,
    SELL_PRICE_ATTR,
    _find_entry_by_display,
    _ware_label,
    _ware_labels,
)


class _Entry:
    """Stand-in for shop_service's BuyEntry / SellEntry."""

    def __init__(self, name, count, buy_price=0, unit_price=0):
        self.name = name
        self.count = count
        self.buy_price = buy_price
        self.unit_price = unit_price


class TestWareLabels(TestCase):
    """Label producer and matcher must agree exactly."""

    def test_single_item_label_has_no_count(self):
        entry = _Entry("hammer", count=1, buy_price=25)

        label = _ware_label(entry, BUY_PRICE_ATTR)

        assert "(x" not in label
        assert "hammer" in label
        assert "25" in label


    def test_multi_item_label_shows_count_and_each(self):
        entry = _Entry("credits", count=7, buy_price=3)

        label = _ware_label(entry, BUY_PRICE_ATTR)

        assert "(x7)" in label
        assert "each" in label


    def test_buy_label_round_trips_through_matcher(self):
        entries = [
            _Entry("hammer", count=1, buy_price=25),
            _Entry("credits", count=7, buy_price=3),
        ]

        for label, expected in zip(_ware_labels(entries, BUY_PRICE_ATTR), entries):
            found = _find_entry_by_display(entries, label, BUY_PRICE_ATTR)
            assert found is expected


    def test_sell_label_round_trips_through_matcher(self):
        entries = [
            _Entry("Scrap", count=1, unit_price=4),
            _Entry("Chunk", count=12, unit_price=9),
        ]

        for label, expected in zip(_ware_labels(entries, SELL_PRICE_ATTR), entries):
            found = _find_entry_by_display(entries, label, SELL_PRICE_ATTR)
            assert found is expected


    def test_buy_and_sell_use_different_price_fields(self):
        entry = _Entry("Widget", count=1, buy_price=100, unit_price=40)

        assert "100" in _ware_label(entry, BUY_PRICE_ATTR)
        assert "40" in _ware_label(entry, SELL_PRICE_ATTR)


    def test_unknown_selection_returns_none(self):
        entries = [_Entry("hammer", count=1, buy_price=25)]

        assert _find_entry_by_display(entries, "not a real label", BUY_PRICE_ATTR) is None

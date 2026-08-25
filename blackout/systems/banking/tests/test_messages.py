"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: The player-facing wording in systems/banking/messages.py.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.banking
"""

from evennia.utils.test_resources import EvenniaTest

from systems.banking import messages
from systems.banking.handler import VAULT_FULL_ERROR, TransferResult


class TestTransferMessages(EvenniaTest):
    """The wording both consumers share."""

    def test_a_single_unit_is_named_without_a_multiplier(self):
        result = TransferResult(True, 1, "hammer", None)

        line = messages.format_transfer(result, messages.VERB_DEPOSIT)

        self.assertEqual(line, "You deposit hammer into the bank.")

    def test_several_units_carry_the_multiplier(self):
        result = TransferResult(True, 12, "credits", None)

        line = messages.format_transfer(result, messages.VERB_DEPOSIT)

        self.assertEqual(line, "You deposit credits (x12) into the bank.")

    def test_a_withdrawal_reads_in_the_other_direction(self):
        result = TransferResult(True, 3, "credits", None)

        line = messages.format_transfer(result, messages.VERB_WITHDRAW)

        self.assertEqual(line, "You withdraw credits (x3) from the bank.")

    def test_a_failure_renders_as_its_reason(self):
        result = TransferResult(False, 0, "credits", None, VAULT_FULL_ERROR)

        line = messages.format_transfer(result, messages.VERB_DEPOSIT)

        self.assertEqual(line, VAULT_FULL_ERROR)

    def test_a_partial_transfer_reports_what_landed(self):
        """Not the reason it stopped -- the caller prints that separately, so
        one event does not become two sentences from one call."""
        result = TransferResult(True, 12, "credits", None, VAULT_FULL_ERROR)

        line = messages.format_transfer(result, messages.VERB_DEPOSIT)

        self.assertEqual(line, "You deposit credits (x12) into the bank.")

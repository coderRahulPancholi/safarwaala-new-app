# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from safarwaala.safarwaala import booking_policy as bp

# Direction -> the only party type that direction can settle with, and the field on
# `Bookings` that must hold that party when the payment is tied to a booking.
DIRECTION_PARTY = {
    "Inbound": ("Customer", "customer"),
    "Outbound": ("Vendors", "assigned_to"),
}

# Party doctype -> field holding its display name.
PARTY_NAME_FIELD = {
    "Customer": "full_name",
    "Vendors": "company_name",
}


class Payments(Document):
    def __setup__(self):
        # `party` is a Dynamic Link resolved through `party_type`, and Frappe validates
        # links *before* any `before_validate`/`validate` hook runs. Filling the party type
        # here — at document construction — is the only point early enough for a
        # programmatic insert that passes `payment_direction` but not `party_type`.
        # A value the caller *did* supply is left alone, so the link resolves and the
        # mismatch is reported by `validate()` instead of as an opaque link error.
        self.fill_party_type()

    def validate(self):
        self.apply_direction()
        self.validate_amount()
        self.validate_booking_party()
        self.set_party_name()
        if not self.status:
            self.status = bp.get_default_booking_status()

    def on_submit(self):
        self.refresh_booking()

    def on_cancel(self):
        self.refresh_booking()

    def on_trash(self):
        self.refresh_booking()

    # ── Validation ──────────────────────────────────────────────────────────────
    def fill_party_type(self):
        """Set `party_type` from the direction when the caller left it blank.

        Runs from ``__setup__``, before the field values are necessarily attached, so it
        reads defensively and never raises: a half-built document must not break
        ``frappe.new_doc``.
        """
        expected = DIRECTION_PARTY.get(self.get("payment_direction"))
        if expected and not self.get("party_type"):
            self.party_type = expected[0]

    def apply_direction(self):
        """Reject a direction / party-type pair that cannot settle with each other."""
        direction = self.payment_direction
        expected = DIRECTION_PARTY.get(direction)
        if not expected:
            frappe.throw(
                _("Direction must be one of: {0}").format(", ".join(DIRECTION_PARTY)),
                frappe.ValidationError,
            )

        party_type = expected[0]
        if self.party_type and self.party_type != party_type:
            frappe.throw(
                _("{0} payments must settle with a {1}, not {2}.").format(
                    direction, party_type, self.party_type
                ),
                frappe.ValidationError,
            )
        self.party_type = party_type

    def validate_amount(self):
        if flt(self.amount) <= 0:
            frappe.throw(
                _("Amount must be greater than zero. The direction carries the sign."),
                frappe.ValidationError,
            )

    def validate_booking_party(self):
        """A booking-linked payment must name that booking's own customer / vendor."""
        if not self.booking:
            return

        _party_type, booking_field = DIRECTION_PARTY[self.payment_direction]
        expected = frappe.db.get_value("Bookings", self.booking, booking_field)
        if not expected:
            frappe.throw(
                _("Booking {0} has no {1} set, so it cannot be settled yet.").format(
                    self.booking, frappe.unscrub(booking_field)
                ),
                frappe.ValidationError,
            )
        if expected != self.party:
            frappe.throw(
                _("Booking {0} belongs to {1}, not {2}.").format(
                    self.booking, expected, self.party
                ),
                frappe.ValidationError,
            )

    def set_party_name(self):
        field = PARTY_NAME_FIELD.get(self.party_type)
        self.party_name = (
            frappe.db.get_value(self.party_type, self.party, field)
            if field and self.party
            else None
        )

    # ── Settlement ──────────────────────────────────────────────────────────────
    def refresh_booking(self):
        if self.booking:
            bp.refresh_booking_settlement(self.booking)

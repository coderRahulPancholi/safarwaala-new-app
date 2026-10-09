# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from safarwaala.safarwaala import booking_policy as bp

PRICED_FIELDS = (
    "min_hours",
    "min_km",
    "per_hour_rate",
    "per_km_rate",
    "night_rate",
    "base_amount",
    "extra_km_charges",
    "extra_hour_charges",
    "night_charges",
)


class Bookings(Document):
    # ── Lifecycle ───────────────────────────────────────────────────────────────
    def before_insert(self):
        if not self.assigned_to and "Vendor" in frappe.get_roles(frappe.session.user):
            vendor = frappe.db.get_value("Vendors", {"linked_user": frappe.session.user}, "name")
            if vendor:
                self.assigned_to = vendor

    def validate(self):
        policy = bp.get_policy()
        self.validate_booking_type()
        self.validate_schedule(policy)
        self.validate_log_sheet()
        self.validate_mobile(policy)
        if not self.booking_status:
            self.booking_status = bp.get_default_booking_status()
        self.calculate_charges(policy)
        self.calculate_vendor_cost(policy)
        self.derive_settlement()

    # ── Validation ──────────────────────────────────────────────────────────────
    def validate_booking_type(self):
        self.booking_type = bp.resolve_booking_type(self.booking_type)
        # strict: the booking type's permitted trip types come from Safarwaala Settings, and
        # a direct document save must honour them just like the API does.
        self.trip_type = bp.resolve_trip_type(self.booking_type, self.trip_type, strict=True)
        meta = bp.get_booking_type_meta(self.booking_type)
        if meta["requires_return"] and not self.return_datetime:
            frappe.throw(
                _("Return date/time is required for {0} bookings.").format(meta["label"]),
                frappe.ValidationError,
            )
        if meta["requires_drop"] and not self.drop_address:
            frappe.throw(
                _("Drop address is required for {0} bookings.").format(meta["label"]),
                frappe.ValidationError,
            )
        if meta["supports_packages"] and not self.package_type:
            frappe.throw(
                _("Package is required for {0} bookings.").format(meta["label"]),
                frappe.ValidationError,
            )

    def validate_schedule(self, policy):
        pickup = bp.parse_datetime(self.pickup_datetime)
        return_dt = bp.parse_datetime(self.return_datetime)
        if return_dt and pickup and return_dt <= pickup:
            frappe.throw(_("Return date/time must be after the pickup date/time."), frappe.ValidationError)
        if pickup and self.is_new() and not self.amended_from and not self._is_desk_user():
            bp.check_pickup_window(pickup, policy)

        # An itinerary that cannot physically be driven in the booked window is rejected
        # here too, so a Desk-entered booking gets the same guard as the customer API.
        feasibility = bp.check_trip_feasibility(
            self.estimated_distance_km, pickup, return_dt, self.trip_type, policy
        )
        if not feasibility["feasible"]:
            frappe.throw(feasibility["message"], frappe.ValidationError)

    @staticmethod
    def _is_desk_user():
        """Desk (System User) accounts may enter back-dated bookings."""
        user = frappe.session.user
        return user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User"

    def validate_log_sheet(self):
        if self.end_km and flt(self.end_km) < flt(self.start_km):
            frappe.throw(_("End Km cannot be less than Start Km."), frappe.ValidationError)

    def validate_mobile(self, policy):
        if self.customer_mobile:
            bp.check_mobile(self.customer_mobile, policy)

    # ── Pricing ─────────────────────────────────────────────────────────────────
    def calculate_charges(self, policy):
        if self.booking_type == "Package":
            self.calculate_package_charges()
            return

        car = bp.get_car_rates(self.car_model)
        package = bp.get_package(self.package_type) if self.booking_type == "Local" else None
        fare = bp.compute_fare(
            booking_type=self.booking_type,
            car=car,
            package=package,
            pickup=self.pickup_datetime,
            return_dt=self.return_datetime,
            trip_type=self.trip_type,
            estimated_distance_km=self.estimated_distance_km,
            office_to_pickup_km=self.get("office_to_pickup_km"),
            start_km=self.start_km,
            end_km=self.end_km,
            policy=policy,
            tax_target=self,
        )
        for fieldname in PRICED_FIELDS:
            self.set(fieldname, fare[fieldname])
        self.total_km = fare["total_km"]
        self.tax_total = fare["tax_total"]
        self.grand_total = fare["grand_total"]

    def calculate_package_charges(self):
        """Package bookings: grand_total is the vendor-entered, all-inclusive price.

        Rate-driven fields are zeroed; only the logged km and the tax-row total are derived."""
        self.total_km = max(flt(self.end_km) - flt(self.start_km), 0) if self.end_km else 0
        for fieldname in PRICED_FIELDS:
            self.set(fieldname, 0)
        self.tax_total = flt(sum(flt(row.amount) for row in self.get("tax_and_charges")), 2)

    # ── Vendor cost & margin ────────────────────────────────────────────────────
    def calculate_vendor_cost(self, policy):
        """What we owe the vendor, and the margin we keep.

        Reuses the customer fare geometry (days, nights, chargeable km, package hours) and
        swaps only the rates, so the two sides can never drift apart.
        """
        cost = bp.compute_vendor_cost(self, policy=policy)

        self.vendor_rate_source = cost["vendor_rate_source"]
        if not self.override_vendor_rates:
            self.vendor_per_km_rate = cost["vendor_per_km_rate"]
            self.vendor_per_hour_rate = cost["vendor_per_hour_rate"]
            self.vendor_night_charge = cost["vendor_night_charge"]
            self.vendor_minimum_km_per_day = cost["vendor_minimum_km_per_day"]

        for fieldname in bp.VENDOR_AMOUNT_FIELDS:
            self.set(fieldname, cost[fieldname])

        self.margin_amount = cost["margin_amount"]
        self.margin_percent = cost["margin_percent"]

    # ── Settlement ──────────────────────────────────────────────────────────────
    def derive_settlement(self):
        """Outstanding amounts and status from the stored paid totals.

        `customer_paid` / `vendor_paid` are maintained by the `Payments` controller via
        `db_set`; this only derives the figures that follow from them.
        """
        self.customer_outstanding = flt(flt(self.grand_total) - flt(self.customer_paid), 2)
        self.vendor_outstanding = flt(flt(self.vendor_payable) - flt(self.vendor_paid), 2)
        self.settlement_status = bp.settlement_status(
            grand_total=self.grand_total,
            customer_paid=self.customer_paid,
            vendor_payable=self.vendor_payable,
            vendor_paid=self.vendor_paid,
        )

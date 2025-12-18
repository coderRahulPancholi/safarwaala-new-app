# Copyright (c) 2025, Safarwaala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class VehicleExpenseLog(Document):
    def on_submit(self):
        self.update_booking_total()
        
    def on_update(self):
        # Also trigger on update (for non-submittable docs or updates)
        self.update_booking_total()
        
    def on_trash(self):
        self.update_booking_total()

    def update_booking_total(self):
        # We rely on booking_ref being the name of the Bookings Master
        if self.booking_ref and frappe.db.exists("Bookings Master", self.booking_ref):
            booking = frappe.get_doc("Bookings Master", self.booking_ref)
            # Saving triggers validate() -> calculate_expenses() -> calculate_totals()
            booking.save(ignore_permissions=True)

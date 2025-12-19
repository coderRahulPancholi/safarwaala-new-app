# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


from frappe.utils import flt

class CustomerInvoice(Document):
    def before_save(self):
        self.calculate_totals()

    def calculate_totals(self):
        gross_total = 0.0
        if self.invoice_item:
            for item in self.invoice_item:
                gross_total += flt(item.amount)
        
        self.gross_total = gross_total
        self.grand_total = self.gross_total - flt(self.discount)
        self.payable_amount = self.grand_total - flt(self.paid_amount)

    def before_submit(self):
        # Loop through each row in the bookings child table
        for booking_row in self.invoice_item:
            if booking_row.booking_id:
                try:
                    # Logic updated: booking_type removed, always Bookings Master
                    booking = frappe.get_doc("Bookings Master", booking_row.booking_id)
                    booking.booking_status = "Invoiced"
                    booking.linked_invoice = self.name
                    booking.flags.ignore_permissions = True
                    booking.save()
                    # Do not submit the booking here if it's already completed or if workflow differs.
                    # Usually Invoicing happens AFTER completion. If not submitted, maybe submit?
                    # Keeping existing logic check for now but safe to assume it might be submitted already.
                    if booking.docstatus == 0:
                        booking.submit()
                except Exception as e:
                    frappe.log_error(f"Failed to update booking {booking_row.booking_id}: {e}")
            else:
                frappe.log_error(f"Booking ID is missing for booking reference row")
# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomerInvoice(Document):
    def before_submit(self):
        # Loop through each row in the bookings child table
        for booking_row in self.invoice_item:
            if booking_row.booking_type and booking_row.booking_id:
                try:
                    booking = frappe.get_doc(booking_row.booking_type, booking_row.booking_id)
                    booking.booking_status = "Invoiced"  # Or any status you want
                    booking.invoice = self.name  # Or any status you want
                    booking.save()
                    if booking.docstatus == 0:  # Only submit if not already submitted
                        booking.submit()
                except Exception as e:
                    frappe.log_error(f"Failed to update booking {booking_row.booking_reference}: {e}")
            else:
                frappe.log_error(f"Booking type or ID is missing for booking reference {booking_row.booking_reference}")
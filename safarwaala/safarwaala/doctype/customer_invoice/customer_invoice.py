# Copyright (c) 2025, Safarwaala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CustomerInvoice(Document):
	def on_submit(self):
		if self.status == "Booked":
			# Update linked bookings
			bookings = frappe.get_all("Bookings Master", filters={"linked_invoice": self.name})
			for booking in bookings:
				frappe.db.set_value("Bookings Master", booking.name, "status", "Invoiced")
		
		# Added GL Entry logic for Paid invoices
		if self.status == "Paid" and self.bank_account:
			self.make_gl_entries()

	def on_cancel(self):
		# Reset bookings
		bookings = frappe.get_all("Bookings Master", filters={"linked_invoice": self.name})
		for booking in bookings:
			frappe.db.set_value("Bookings Master", booking.name, "status", "Completed") # Revert to completed or whatever it was?
			# Actually user said previously "Invoice is created from Booking".
			# If Invoice cancelled, Booking should probably go back to waiting for invoice. 
			# But "Completed" might be safe. Or "Pending Invoice" if that status existed.
			# Let's just keep it simple or as it was?
			# Checking previous logic... I only added "Invoiced" status update in task list.
			pass

		if self.bank_account:
			self.delete_gl_entries()

	def make_gl_entries(self):
		# Debit Bank (Asset increases) - Money received from Customer
		gl_entry_bank = frappe.get_doc({
			"doctype": "GL Entry",
			"posting_date": self.invoice_date,
			"account": self.bank_account,
			"party_type": "Customer",
			"party": self.customer,
			"debit": self.grand_total, # Debit increases Bank Balance
			"credit": 0,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"remarks": f"Invoice Payment from {self.customer}",
			"docstatus": 1
		})
		gl_entry_bank.insert(ignore_permissions=True)
		frappe.msgprint(f"GL Entry Created: {gl_entry_bank.name}")

	def delete_gl_entries(self):
		gl_entries = frappe.get_all("GL Entry", filters={"voucher_type": self.doctype, "voucher_no": self.name})
		for entry in gl_entries:
			frappe.delete_doc("GL Entry", entry.name, ignore_permissions=True)
# Copyright (c) 2025, Safarwaala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Payouts(Document):
	def on_submit(self):
		if self.status == "Paid" and self.bank_account:
			self.make_gl_entries()

	def on_cancel(self):
		if self.bank_account:
			self.delete_gl_entries()

	def make_gl_entries(self):
		# Credit Bank (Asset decreases)
		gl_entry_bank = frappe.get_doc({
			"doctype": "GL Entry",
			"posting_date": self.payment_date,
			"account": self.bank_account,
			"party_type": self.payout_to_type,
			"party": self.payout_to,
			"credit": self.amount,
			"debit": 0,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"remarks": f"Payment to {self.payout_to} ({self.payout_to_type})",
			"docstatus": 1
		})
		gl_entry_bank.insert(ignore_permissions=True)
		frappe.msgprint(f"GL Entry Created: {gl_entry_bank.name}")

		# Debit Party (Liability decreases or Expense increases)
		# For this simple system, we just record the other side? 
		# Or maybe we don't need a double entry if we are only tracking Bank Balance?
		# The user asked for "maintain GL entries against bank account".
		# So creating just the Bank entry is sufficient for the requirement "maintain GL entries against bank account".
		# But for completeness let's just do the bank entry for now as we don't have a "Party Account" to debit.
		

		# gl_entries = frappe.get_all("GL Entry", filters={"voucher_type": self.doctype, "voucher_no": self.name})
		# for entry in gl_entries:
		# 	frappe.delete_doc("GL Entry", entry.name, ignore_permissions=True)


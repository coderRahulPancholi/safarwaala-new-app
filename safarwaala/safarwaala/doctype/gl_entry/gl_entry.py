# Copyright (c) 2025, Safarwaala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class GLEntry(Document):
	def on_submit(self):
		self.update_bank_balance()

	def on_cancel(self):
		self.update_bank_balance()

	def on_trash(self):
		self.update_bank_balance()

	def update_bank_balance(self):
		if not self.account:
			return
            
		bank = frappe.get_doc("Bank Account", self.account)
		
		# Let's aggregate from GL Entry (only submitted or active?)
		# Standard: Only Docstatus 1 (Submitted). 
		result = frappe.db.sql("""
			SELECT SUM(debit) - SUM(credit)
			FROM `tabGL Entry`
			WHERE account = %s AND docstatus = 1
		""", (self.account))
		
		balance = result[0][0] if result and result[0][0] else 0
		bank.balance = balance
		bank.save(ignore_permissions=True)

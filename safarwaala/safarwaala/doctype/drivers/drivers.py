# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Drivers(Document):
	def validate(self):
		if not self.name1:
			return
		
		# Name formatting
		parts = self.name1.split(" ")
		self._first_name = parts[0]
		self._last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

		if self.create_user == 1:
			if not self.email:
				frappe.throw("Email is required when Create User is checked")
			
			user_email = self.email
			# If linked_user is also provided, ensure it matches?
			# Actually, if Create User is checked, we ignore linked_user input and create/link based on email.
			
			if frappe.db.exists("User", user_email):
				# User exists.
				# Check if linked to another driver
				linked_driver = frappe.db.get_value("Drivers", {"linked_user": user_email, "name": ["!=", self.name]}, "name")
				if linked_driver:
					frappe.throw(f"User {user_email} is already linked to Driver {linked_driver}")
			else:
				# User does not exist. We will create it.
				self._pending_user_creation = user_email
			
			# Ensure linked_user is correctly set for the upcoming check or cleared for creation
			if not frappe.db.exists("User", user_email):
				self.linked_user = None
			else:
				self.linked_user = user_email

		elif self.linked_user:
			# Normal linking logic
			linked_driver = frappe.db.get_value("Drivers", {"linked_user": self.linked_user, "name": ["!=", self.name]}, "name")
			if linked_driver:
				frappe.throw(f"User {self.linked_user} is already linked to Driver {linked_driver}")
	
	def after_insert(self):
		if self.create_user == 1 and hasattr(self, '_pending_user_creation'):
			# Create the new user
			new_user = frappe.get_doc({
				"doctype": "User",
				"email": self._pending_user_creation,
				"first_name": self._first_name,
				"last_name": self._last_name,
				"enabled": 1,
				"send_welcome_email": 0,
				"roles": [{"role": "Driver"}],
				"role_profile_name": "Driver"
			})
			new_user.insert(ignore_permissions=True)
			
			# Update self with new link
			frappe.db.set_value(self.doctype, self.name, "linked_user", new_user.name)
		
		# If user existed but we needed to ensure role
		if self.create_user == 1 and self.email:
			# We use self.email here because self.linked_user might have been set/unset during validate
			target_user = self.email
			if frappe.db.exists("User", target_user):
				user_doc = frappe.get_doc("User", target_user)
				roles = [r.role for r in user_doc.roles]
				if "Driver" not in roles:
					user_doc.append("roles", {"role": "Driver"})
					user_doc.save(ignore_permissions=True)
				
				# Ensure link is set if it wasn't
				if self.linked_user != target_user:
					frappe.db.set_value(self.doctype, self.name, "linked_user", target_user)
		



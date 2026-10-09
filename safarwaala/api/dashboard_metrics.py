import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_vendor_pending_balance(filters=None):
	"""What is still owed to the session user's vendor, across submitted bookings.

	Driver money is deliberately not tracked: the vendor pays its own drivers, so a driver
	has no balance with us. A Driver session therefore gets 0.
	"""
	user = frappe.session.user
	if user == "Administrator":
		# Everything still owed to every vendor.
		rows = frappe.get_all(
			"Bookings",
			filters={"docstatus": ["<", 2], "assigned_to": ["is", "set"]},
			fields=["vendor_outstanding"],
		)
		return flt(sum(flt(r["vendor_outstanding"]) for r in rows), 2)

	vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
	if not vendor:
		return 0

	rows = frappe.get_all(
		"Bookings",
		filters={"assigned_to": vendor, "docstatus": ["<", 2]},
		fields=["vendor_outstanding"],
	)
	return flt(sum(flt(r["vendor_outstanding"]) for r in rows), 2)

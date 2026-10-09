from frappe import _


def get_data(data=None):
	return {
		"transactions": [
			{
				"label": _("Fleet"),
				"items": ["Cars", "Drivers"]
			},
			{
				"label": _("Operations"),
				"items": ["Bookings", "Duty Slips"]
			},
			{
				"label": _("Accounts"),
				"items": ["Payments"]
			}
		],
		"non_standard_fieldnames": {
			"Cars": "belongs_to_vendor",
			"Drivers": "owner_vendor",
			"Bookings": "assigned_to",
			# Outbound payments settle with the vendor through the generic party link.
			"Payments": "party",
		}
	}

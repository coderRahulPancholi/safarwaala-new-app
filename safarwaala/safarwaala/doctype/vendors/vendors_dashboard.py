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
				"items": ["OutStation Bookings", "Duty Slips"]
			},
            {
                "label": _("Accounts"),
                "items": ["Driver Payment", "Customer Invoice"]
            }
		],
        "non_standard_fieldnames": {
            "Cars": "belongs_to_vendor",
            "Drivers": "owner_vendor",
            "OutStation Bookings": "assigned_to",
            "Driver Payment": "vendor",
        }
	}

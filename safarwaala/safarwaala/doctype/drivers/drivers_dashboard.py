from frappe import _


def get_data(data=None):
	# Drivers are paid by their vendor, so there is no driver-money section here.
	return {
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Bookings", "Duty Slips"]
			}
		],
		"non_standard_fieldnames": {
			"Bookings": "driver",
			"Duty Slips": "driver"
		},
		"charts": [
			{
				"label": _("Bookings by Month"),
				"items": ["Bookings"],
				"timespan": "Last Year",
				"color": "#7FA3B5",
				"type": "Bar",
				"group_by_type": "Count",
				"aggregate_function": "Count",
				"based_on": "creation"
			}
		]
	}

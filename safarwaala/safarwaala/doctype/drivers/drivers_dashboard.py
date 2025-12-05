from frappe import _

def get_data(data=None):
	return {
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["OutStation Bookings", "Duty Slips"]
			},
            {
                "label": _("Earnings"),
                "items": ["Driver Payment"]
            }
		],
        "non_standard_fieldnames": {
            "OutStation Bookings": "driver",
            "Duty Slips": "driver",
            "Driver Payment": "driver"
        },
        "charts": [
            {
                "label": _("Bookings by Month"),
                "items": ["OutStation Bookings"],
                "timespan": "Last Year",
                "color": "#7FA3B5",
                "type": "Bar",
                "group_by_type": "Count",
                "aggregate_function": "Count",
                "based_on": "creation" 
            }
        ]
	}

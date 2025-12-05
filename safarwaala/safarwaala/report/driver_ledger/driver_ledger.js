// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.query_reports["Driver Ledger"] = {
	"filters": [
        {
            "fieldname": "driver",
            "label": __("Driver"),
            "fieldtype": "Link",
            "options": "Drivers",
            "reqd": 1,
            "get_query": function() {
                // If user is Vendor, only show own drivers
                return {
                     query: "safarwaala.api.permission.get_driver_condition"
                };
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ]
};

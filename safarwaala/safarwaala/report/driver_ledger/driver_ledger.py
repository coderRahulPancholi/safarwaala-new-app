# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 180
		},
		{
			"fieldname": "description",
			"label": _("Description"),
			"fieldtype": "Data",
			"width": 250
		},
		{
			"fieldname": "earned",
			"label": _("Earned (Credit)"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "paid",
			"label": _("Paid (Debit)"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "balance",
			"label": _("Balance"),
			"fieldtype": "Currency",
			"width": 120
		}
	]

def get_data(filters):
    if not filters.get("driver"):
        return []

    data = []
    
    # 1. Get Earnings from Duty Slips (Sum of Expenses)
    ds_filters = {"driver": filters.get("driver"), "docstatus": 1}
    duty_slips = frappe.get_all("Duty Slips", filters=ds_filters, fields=["name", "return_datetime"])
    
    for ds in duty_slips:
        # Sum expenses
        expense_amount = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabTrip Expenses Item`
            WHERE parent = %s
        """, (ds.name,))
        
        amt = expense_amount[0][0] or 0
        if amt > 0:
            data.append({
                "date": ds.return_datetime,
                "voucher_type": "Duty Slips",
                "voucher_no": ds.name,
                "description": "Duty Slip Expenses",
                "earned": amt,
                "paid": 0,
                "timestamp": ds.return_datetime 
            })

    # 2. Get Payments from Driver Payment
    pymt_filters = {"driver": filters.get("driver"), "docstatus": 1}
    payments = frappe.get_all("Driver Payment", filters=pymt_filters, fields=["name", "payment_date", "amount", "details"])
    
    for p in payments:
        data.append({
            "date": p.payment_date,
            "voucher_type": "Driver Payment",
            "voucher_no": p.name,
            "description": p.details or "Payment",
            "earned": 0,
            "paid": p.amount,
            "timestamp": p.payment_date 
        })
        
    data.sort(key=lambda x: str(x.get("timestamp") or ""))
    
    balance = 0
    for row in data:
        balance += (row.get("earned") or 0) - (row.get("paid") or 0)
        row["balance"] = balance
        
    return data

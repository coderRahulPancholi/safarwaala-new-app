# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, time_diff_in_hours, ceil, nowdate

class Bookings(Document):
    pass
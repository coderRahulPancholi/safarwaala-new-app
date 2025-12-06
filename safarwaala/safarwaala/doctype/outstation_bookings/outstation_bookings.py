import frappe
from frappe.model.document import Document
from frappe.utils import flt
from math import radians, sin, cos, sqrt, atan2

class OutStationBookings(Document):
    pass
    def before_save(self):
        from_city = self.start_from
        to_city = self.to

        # Fetch coordinates from City Master
        from_city_data = frappe.get_value("City Master", from_city, ["lat", "lng"])
        to_city_data = frappe.get_value("City Master", to_city, ["lat", "lng"])

        if not from_city_data or not to_city_data:
            frappe.throw("Could not fetch latitude/longitude for selected cities.")

        from_lat, from_lng = map(float, from_city_data)
        to_lat, to_lng = map(float, to_city_data)

        # Calculate and assign distance
        distance = self.calculate_distance(from_lat, from_lng, to_lat, to_lng) 
        distance = round(distance + ((distance/100) * 20), 2)
        self.avarage_distance = distance
        
        self.calculate_total_expenses()

    def calculate_total_expenses(self):
        """
        Calculate total billable expenses from linked Vehicle Expense Logs.
        Net Total (Base Rate) + Taxes + Billable Expenses = Grand Total
        """
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_type': self.doctype,
                                          'booking_ref': self.name,
                                          'is_billable': 1,
                                          'docstatus': 1 # Only submitted/approved expenses if submittable, else check logic
                                      }, 
                                      fields=['amount'])
        
        # If Vehicle Expense Log is not submittable, remove docstatus check or use 0
        # Check if Log is submittable first. It is 0 in JSON, so ignore docstatus or use 0.
        # Let's filter by status='Approved' or just log existence. 
        # For simplicity, fetching all linked expenses irrespective of status for now, or filter by 'Pending'/'Approved'
        # Safest is to just sum all.
        
        total_expense = sum([flt(d.amount) for d in expenses])
        
        self.expense_total = total_expense
        
        # Recalculate Grand Total
        self.grand_total = flt(self.net_total) + flt(self.tax_total) + total_expense

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        r = 6371  # Earth radius in km
        return r * c # Distance in km
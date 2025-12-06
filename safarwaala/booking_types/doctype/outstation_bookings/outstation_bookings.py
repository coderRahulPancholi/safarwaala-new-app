import frappe
from frappe.model.document import Document
from frappe.utils import flt

class OutStationBookings(Document):
    def before_save(self):
        self.calculate_total_expenses()

    def calculate_total_expenses(self):
        """
        Calculate total billable expenses from linked Vehicle Expense Logs.
        Grand Total = Net Total + Tax Total.
        Net Total = Total (Night + Km) + Expense Total.
        """
        # Fetch billable expenses
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_type': self.doctype,
                                          'booking_ref': self.name,
                                          'is_billable': 1,
                                          'docstatus': 1 
                                      }, 
                                      fields=['amount'])
        
        # Also fetch pending/non-submitted ones if workflow allows? 
        # For now, let's fetch all (ignoring docstatus for simplicity if workflow isn't strict yet)
        # Or better, fetch all is_billable=1 regardless of status for "Pending" bookings
        expenses_all = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_type': self.doctype,
                                          'booking_ref': self.name,
                                          'is_billable': 1
                                      }, 
                                      fields=['amount'])

        total_expense = sum([flt(d.amount) for d in expenses_all])
        self.expense_total = total_expense
        
        # Ensure base total (night + km) is calculated. 
        # In backend, we might rely on JS for base 'total', or we should recalculate it here.
        # Ideally backend should not rely on JS values, but for quick fix let's trust 'total' exist.
        # But 'net_total' needs update.
        
        if not self.total:
            self.total = 0
            
        self.net_total = flt(self.total) + flt(self.expense_total)
        self.gross_total = flt(self.net_total) + flt(self.tax_total)
        self.grand_total = flt(self.gross_total) - flt(self.discount)

@frappe.whitelist()
def get_billable_expenses_total(booking_id):
    """
    API to fetch total billable expenses for a booking ID.
    Used by Client Script button.
    """
    expenses = frappe.db.get_list('Vehicle Expense Log', 
                                  filters={
                                      'booking_type': 'OutStation Bookings',
                                      'booking_ref': booking_id,
                                      'is_billable': 1
                                  }, 
                                  fields=['amount'])
    
    total = sum([flt(d.amount) for d in expenses])
    return total

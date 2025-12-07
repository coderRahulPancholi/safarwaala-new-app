import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, ceil

class OutStationBookings(Document):
    def before_save(self):
        self.calculate_charges()
        self.calculate_taxes()
        self.calculate_total_expenses()

    def calculate_taxes(self):
        self.tax_total = 0
        for row in self.get("tax_and_charges", []):
            self.tax_total += flt(row.amount)

    def calculate_charges(self):
        if not self.departure_datetime or not self.return_datetime:
            return

        start = get_datetime(self.departure_datetime)
        end = get_datetime(self.return_datetime)
        
        # Calculate Days & Nights
        duration_in_seconds = (end - start).total_seconds()
        days = ceil(duration_in_seconds / (24 * 3600))
        if days < 1: days = 1 # Minimum 1 day
        
        nights = days - 1
        
        self.days = days
        self.nights = nights
        
        # Calculate Night Charges
        night_rate = flt(self.night_rate)
        self.night_charges = nights * night_rate
        
        # Calculate Distance Logic
        start_km = flt(self.start_km)
        end_km = flt(self.end_km)
        self.diffrence_km = end_km - start_km
        if self.diffrence_km < 0: self.diffrence_km = 0
        
        # Min KM Calculation
        min_km_per_day = flt(self.min_km_per_day)
        self.min_km = min_km_per_day * days
        
        # Chargeable KM Logic: Default to Max(Actual, Min), but respect Manual Override
        calculated_chargeable = max(self.diffrence_km, self.min_km)
        
        # If Chargeable KM is not set (or 0), apply formatted calculation.
        # This respects frontend values (which might be auto-calc or manual).
        if not flt(self.chargeable_km):
             self.chargeable_km = calculated_chargeable
            
        # KM Amount (Always derived from Chargeable Km)
        per_km_rate = flt(self.per_km_rate)
        self.km_amount = flt(self.chargeable_km) * per_km_rate
        
        # Total
        self.total = flt(self.night_charges) + flt(self.km_amount)

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

    def on_submit(self):
        self.create_customer_invoice()
        self.create_driver_payment()

    def create_customer_invoice(self):
        if self.invoice: return # Already created
        
        invoice = frappe.get_doc({
            "doctype": "Customer Invoice",
            "customer": self.customer,
            "invoice_date": frappe.utils.nowdate(),
            "invoice_due_date": frappe.utils.nowdate(),
            "invoice_item": [{
                "booking_type": self.doctype,
                "booking_id": self.name,
                "amount": self.grand_total
            }],
            "gross_total": self.grand_total,
            "grand_total": self.grand_total,
            "payable_amount": self.grand_total
        })
        invoice.insert(ignore_permissions=True)
        self.db_set("invoice", invoice.name)
        frappe.msgprint(f"Customer Invoice {invoice.name} created.")

    def create_driver_payment(self):
        # Calculate Expenses paid by Driver
        driver_expenses = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabVehicle Expense Log`
            WHERE booking_type=%s AND booking_ref=%s AND paid_by='Driver' AND docstatus=1
        """, (self.doctype, self.name))
        
        total_expenses = flt(driver_expenses[0][0]) if driver_expenses and driver_expenses[0][0] else 0.0
        
        # Total Payment = Night Charges + Expenses
        total_payment = flt(self.night_charges) + total_expenses
        
        if total_payment <= 0: return

        # Fetch Vendor linked to Driver
        vendor = frappe.db.get_value("Drivers", self.driver, "owner_vendor")
        
        payment = frappe.get_doc({
            "doctype": "Driver Payment",
            "booking_type": self.doctype,
            "booking_id": self.name,
            "driver": self.driver,
            "vendor": vendor,
            "amount": total_payment,
            "payment_date": frappe.utils.nowdate(),
            "details": f"Auto-generated on Booking Completion. Night Charges: {self.night_charges}, Expenses: {total_expenses}"
        })
        payment.insert(ignore_permissions=True)
        frappe.msgprint(f"Driver Payment {payment.name} created for amount {total_payment}")

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

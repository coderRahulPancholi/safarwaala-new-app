import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, time_diff_in_hours, nowdate

class LocalBookings(Document):
    def before_save(self):
        self.calculate_charges()
        self.calculate_taxes()
        self.calculate_total_expenses()

    def calculate_taxes(self):
        self.tax_total = 0
        for row in self.get("tax_and_charges", []):
            self.tax_total += flt(row.amount)

    def calculate_charges(self):
        """
        Calculate Local Booking Charges:
        Base = Min Hours * Per Hour Rate
        Extra Hours = Max(0, Actual - Min) * Per Hour Rate
        Extra Km = Max(0, Actual - Min) * Per Km Rate
        Night Charges = Nights * Night Rate
        """
        # Fetch rates if missing (though mapped in JSON, sometimes good to ensure)
        if not self.per_hour_rate or not self.min_hours:
            if self.car_modal:
                car_modal = frappe.get_doc("Car Modals", self.car_modal)
                self.per_hour_rate = car_modal.local_hour_rate
                self.min_hours = car_modal.min_local_hour
                self.min_km = car_modal.min_local_km
                self.per_km_rate = car_modal.local_km_rate
                self.night_rate = car_modal.night_rate

        # 1. Base Charges
        # The logic: Min Hours X Hour Rate is the minimum package price.
        # This covers usage up to Min Hours.
        # It also implicitly covers Min Km (typically).
        base_h = flt(self.min_hours)
        rate_h = flt(self.per_hour_rate)
        self.base_charges = base_h * rate_h

        # 2. Running Details
        if self.start_km is not None and self.end_km is not None:
            self.total_km = flt(self.end_km) - flt(self.start_km)
            if self.total_km < 0: self.total_km = 0
        else:
            self.total_km = 0

        if self.pickup_datetime and self.return_datetime:
            pickup = get_datetime(self.pickup_datetime)
            drop = get_datetime(self.return_datetime)
            self.total_hours = time_diff_in_hours(drop, pickup)
            if self.total_hours < 0: self.total_hours = 0
        else:
            self.total_hours = 0

        # 3. Extra Charges
        # Extra Hours
        extra_h = flt(self.total_hours) - base_h
        if extra_h < 0: extra_h = 0
        self.extra_hours = extra_h
        self.extra_hour_charges = self.extra_hours * rate_h

        # Extra Km
        base_km = flt(self.min_km)
        extra_k = flt(self.total_km) - base_km
        if extra_k < 0: extra_k = 0
        self.extra_km = extra_k
        rate_k = flt(self.per_km_rate)
        self.extra_km_charges = self.extra_km * rate_k

        # 4. Night Charges
        # Use manually entered nights if available, else 0
        self.night_charges = flt(self.nights) * flt(self.night_rate)

        # 5. Total
        self.total_charges = (
            flt(self.base_charges) +
            flt(self.extra_hour_charges) +
            flt(self.extra_km_charges) +
            flt(self.night_charges)
        )

    def calculate_total_expenses(self):
        # Fetch billable expenses linked to this booking
        # Assuming Vehicle Expense Log links via 'booking_ref' and 'booking_type'
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_type': self.doctype,
                                          'booking_ref': self.name,
                                          'is_billable': 1
                                      }, 
                                      fields=['amount'])
        
        self.trip_expenses_total = sum([flt(d.amount) for d in expenses])
        
        # Grand Total
        self.grand_total = (
            flt(self.total_charges) +
            flt(self.trip_expenses_total) +
            flt(self.tax_total)
        )

    def on_submit(self):
        # Submit Expenses
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_ref': self.name,
                                          'docstatus': 0
                                      })
        for expense in expenses:
            frappe.get_doc("Vehicle Expense Log", expense.name).submit()

        self.create_customer_invoice()
        self.create_driver_payment()

    def create_customer_invoice(self):
        if self.invoice: return

        # Check for expenses paid by customer
        customer_expenses = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabVehicle Expense Log`
            WHERE booking_type=%s AND booking_ref=%s AND paid_by='Customer' AND docstatus=1
        """, (self.doctype, self.name))
        
        customer_paid = flt(customer_expenses[0][0]) if customer_expenses and customer_expenses[0][0] else 0.0

        invoice = frappe.get_doc({
            "doctype": "Customer Invoice",
            "customer": self.customer,
            "invoice_date": nowdate(),
            "invoice_due_date": nowdate(),
            "invoice_item": [{
                "booking_type": self.doctype,
                "booking_id": self.name,
                "amount": self.grand_total
            }],
            "gross_total": self.grand_total,
            "grand_total": self.grand_total,
            "paid_amount": customer_paid,
            "payable_amount": self.grand_total - customer_paid
        })
        invoice.insert(ignore_permissions=True)
        self.db_set("invoice", invoice.name)
        frappe.msgprint(f"Customer Invoice {invoice.name} created.")

    def create_driver_payment(self):
        if frappe.db.exists("Driver Payment", {"booking_id": self.name}):
            return

        # Fetch Driver Expenses
        driver_expenses = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabVehicle Expense Log`
            WHERE booking_type=%s AND booking_ref=%s AND paid_by='Driver' AND docstatus=1
        """, (self.doctype, self.name))
        
        total_expenses = flt(driver_expenses[0][0]) if driver_expenses and driver_expenses[0][0] else 0.0
        
        # Payment Logic:
        # For Local: Payment might be % of Base + Extra?
        # Or just Night + Expenses like Outstation?
        # User said "fit into already implemented flow". 
        # In Outstation, Driver Payment = Night Charges + Expenses. 
        # Base/Km charges go to Vendor/Company?
        # Assuming similar model: Driver gets Night Charges (allowance) + Reimbursement.
        
        total_payment = flt(self.night_charges) + total_expenses
        
        if total_payment <= 0: return

        vendor = frappe.db.get_value("Drivers", self.driver, "owner_vendor")
        
        payment = frappe.get_doc({
            "doctype": "Driver Payment",
            "booking_type": self.doctype,
            "booking_id": self.name,
            "driver": self.driver,
            "vendor": vendor,
            "amount": total_payment,
            "payment_date": nowdate(),
            "details": f"Local Booking {self.name}. Night: {self.night_charges}, Exp: {total_expenses}"
        })
        payment.insert(ignore_permissions=True)
        frappe.msgprint(f"Driver Payment {payment.name} created.")

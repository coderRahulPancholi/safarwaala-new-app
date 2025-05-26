from frappe.model.document import Document
from datetime import datetime, timedelta


class RoutineBookings(Document):
    def before_insert(self):
        if self.departure_datetime and self.return_datetime:
            # Parse as dates only
            start = datetime.strptime(str(self.departure_datetime), "%Y-%m-%d").date()
            end = datetime.strptime(str(self.return_datetime), "%Y-%m-%d").date()

            current_date = start
            # while current_date <= end:
            #     obj = {
            #         "for_date": current_date,
            #     }
            #     if self.daily_fixed_price:
            #         obj["amount"] = self.daily_fixed_price
            #     if self.car_modal:
            #         obj["car_modal"] = self.car_modal
            #     if self.car:
            #         obj["car"] = self.car
            #     if self.assigned_to:
            #         obj["assigned_to"] = self.assigned_to
            #     if self.driver:
            #         obj["driver"] = self.driver
            #     self.append("routine_data", obj)
            #     current_date += timedelta(days=1)

    def before_save(self):
        if self.routine_data:
            total = 0
            for row in self.routine_data:
                if row.amount:
                    if not row.is_absent:
                          total += row.amount
            self.grand_total = total

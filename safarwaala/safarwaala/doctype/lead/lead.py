import frappe
from frappe.model.document import Document

class Lead(Document):
    def validate(self):
        if not self.status:
            self.status = "Open"
        
        # Auto-set source if missing
        if not self.source:
             self.source = "Website"

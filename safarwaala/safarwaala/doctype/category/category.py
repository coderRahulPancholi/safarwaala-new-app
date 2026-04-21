# Copyright (c) 2026, Safarwaala and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document


class Category(Document):
    def before_save(self):
        if not self.slug and self.category_name:
            self.slug = re.sub(r"[\s_]+", "-", self.category_name.lower().strip())

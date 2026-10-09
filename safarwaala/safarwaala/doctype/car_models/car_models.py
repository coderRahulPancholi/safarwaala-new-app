# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CarModels(Document):
	def validate(self):
		self._normalise_gallery()

	def _normalise_gallery(self):
		"""Keep the gallery to exactly one primary image.

		Callers read the thumbnail as "the primary row", so zero primaries would leave
		the card blank and several would make the choice depend on row order. Trim blank
		URLs first, then keep the first flagged row (or the first row) as primary.
		"""
		rows = [row for row in (self.images or []) if (row.image_url or "").strip()]
		for index, row in enumerate(rows, start=1):
			row.image_url = row.image_url.strip()
			row.idx = index

		self.images = rows
		if not rows:
			return

		primary = next((row for row in rows if row.is_primary), rows[0])
		for row in rows:
			row.is_primary = 1 if row is primary else 0

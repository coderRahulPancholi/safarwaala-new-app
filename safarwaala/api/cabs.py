"""
Cab (Car Models) API endpoints for the Safarwaala frontend (safarwaala_user).

Exists because the gallery lives in a child table. Frappe's generic
``/api/resource/Car Models`` list endpoint cannot return child rows, so the
frontend would need one extra request per car to show a thumbnail. This module
returns every model with its images already attached, in a single query pair.
"""

import frappe

CAR_FIELDS = (
	"name",
	"model_name",
	"category",
	"transmission",
	"seating_capacity",
	"luggage_capacity",
	"doors",
	"fuel_type",
	"per_km_rate",
	"minimum_km_per_day",
	"hourly_rate",
	"night_surcharge",
	"local_km_rate",
)


@frappe.whitelist(allow_guest=True)
def get_car_models():
	"""All car models, each with its ordered image gallery.

	Shape per row: the Car Models fields plus
	``images: [{url, caption, is_primary}]`` and ``thumbnail`` (the primary
	image URL, or ``None`` when the model has no photos yet).
	"""
	cars = frappe.get_all(
		"Car Models",
		fields=list(CAR_FIELDS),
		order_by="category asc, per_km_rate asc, model_name asc",
	)
	if not cars:
		return []

	# One query for every gallery rather than one per car.
	rows = frappe.get_all(
		"Car Model Image",
		filters={"parent": ("in", [car["name"] for car in cars])},
		fields=["parent", "image_url", "caption", "is_primary"],
		order_by="parent asc, is_primary desc, idx asc",
	)

	galleries = {}
	for row in rows:
		galleries.setdefault(row["parent"], []).append(
			{
				"url": row["image_url"],
				"caption": row["caption"] or "",
				"is_primary": bool(row["is_primary"]),
			}
		)

	for car in cars:
		images = galleries.get(car["name"], [])
		car["images"] = images
		car["thumbnail"] = images[0]["url"] if images else None

	return cars

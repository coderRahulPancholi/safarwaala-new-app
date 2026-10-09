// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

// All fare maths lives on the server (safarwaala.safarwaala.booking_policy). The form only
// triggers a save so the controller recomputes rates, charges, taxes and grand_total.

frappe.ui.form.on("Bookings", {
    onload(frm) {
        frm.set_query("car", function () {
            const filters = {};
            if (frm.doc.assigned_to) {
                filters.belongs_to_vendor = frm.doc.assigned_to;
            }
            if (frm.doc.car_model) {
                filters.car_model = frm.doc.car_model;
            }
            return { filters: filters };
        });

        frm.set_query("driver", function () {
            const filters = {};
            if (frm.doc.assigned_to) {
                filters.owner_vendor = frm.doc.assigned_to;
            }
            return { filters: filters };
        });
    },

    refresh(frm) {
        update_min_km_label(frm);

        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__("Recalculate Fare"), function () {
                frm.save();
            });
        }

        if (!frm.is_new()) {
            frm.add_custom_button(
                __("Make Duty Slip"),
                function () {
                    frappe.new_doc("Duty Slips", {
                        booking_type: frm.doc.doctype,
                        booking_id: frm.doc.name,
                        driver: frm.doc.driver,
                        car: frm.doc.car,
                        car_model: frm.doc.car_model,
                        from_location: frm.doc.pickup_address,
                        to_location: frm.doc.drop_address,
                        departure_datetime: frm.doc.pickup_datetime,
                        return_datetime: frm.doc.return_datetime,
                    });
                },
                __("Create")
            );
        }
    },

    booking_type(frm) {
        update_min_km_label(frm);
    },
});

function update_min_km_label(frm) {
    const label = frm.doc.booking_type === "Outstation" ? __("Total Min Km") : __("Min Km");
    frm.set_df_property("min_km", "label", label);
}

frappe.ui.form.on("Tax and Charges", {
    amount(frm) {
        update_tax_total(frm);
    },
    rate(frm) {
        update_tax_total(frm);
    },
    tax_and_charges_remove(frm) {
        update_tax_total(frm);
    },
});

// Display-only; the server recomputes every tax row on save.
function update_tax_total(frm) {
    let tax = 0;
    (frm.doc.tax_and_charges || []).forEach((row) => {
        tax += row.amount || 0;
    });
    frm.set_value("tax_total", tax);
}

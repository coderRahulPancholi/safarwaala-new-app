// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bookings", {
    onload(frm) {
        if (frm.doc.car_model) {
             frm.trigger('car_model');
        }

        frm.set_query('car', function() {
            var filters = {};
            if (frm.doc.assigned_to) {
                filters.belongs_to_vendor = frm.doc.assigned_to;
            }
            if (frm.doc.car_model) {
                filters.modal = frm.doc.car_model;
            }
            return { filters: filters };
        });

        frm.set_query('driver', function() {
            var filters = {};
            if (frm.doc.assigned_to) {
                filters.owner_vendor = frm.doc.assigned_to;
            }
            return { filters: filters };
        });
    },

    refresh(frm) {
        frm.add_custom_button(__("Calculate Expenses"), function() {
            frm.save();
        });

        if (frm.doc.docstatus === 1) {
             if(!frm.doc.invoice) {
                frm.add_custom_button(__("Make Invoice"), function() {
                    frappe.confirm('Create Customer Invoice?', () => {
                        frappe.call({
                            method: "create_customer_invoice",
                            doc: frm.doc,
                            callback: function() { frm.reload(); }
                        });
                    });
                }, __("Create"));
            }

            frm.add_custom_button(__("Make Driver Payment"), function() {
                frappe.confirm('Create Driver Payment?', () => {
                    frappe.call({
                        method: "create_driver_payment",
                        doc: frm.doc,
                        callback: function() { frm.reload(); }
                    });
                });
            }, __("Create"));
        }

        frm.add_custom_button(__("Make Duty Slip"), function() {
            frappe.new_doc("Duty Slips", {
                booking_type: frm.doc.doctype,
                booking_id: frm.doc.name,
                driver: frm.doc.driver,
                car: frm.doc.car,
                car_model: frm.doc.car_model,
                from: (frm.doc.booking_type === "Outstation") ? frm.doc.from_city : frm.doc.pickup_location,
                to: (frm.doc.booking_type === "Outstation") ? frm.doc.to_city : frm.doc.drop_location,
                departure_datetime: frm.doc.pickup_datetime,
                return_datetime: frm.doc.return_datetime
            });
        }, __("Create"));
    },

    booking_type(frm) { 
        frm.trigger('car_model'); 
        calculate_charges(frm); 
    },
    car_model(frm) {
        if (!frm.doc.car_model) return;
        
        if (frm.doc.booking_type === "Package") {
            frm.set_value('night_rate', 0);
            calculate_charges(frm);
            return;
        }

        frappe.db.get_doc('Car Modals', frm.doc.car_model).then(car => {
            if (frm.doc.booking_type === "Local") {
                frm.set_value('min_hours', car.min_local_hour);
                frm.set_value('min_km', car.min_local_km);
                frm.set_value('per_hour_rate', car.local_hour_rate);
                frm.set_value('per_km_rate', car.local_km_rate);
                frm.set_value('night_rate', car.night_rate);
                frm.set_df_property('min_km', 'label', 'Min Km');
            } 
            else if (frm.doc.booking_type === "Outstation") {
                frm.set_value('per_km_rate', car.per_km_rate);
                frm.set_value('night_rate', car.night_rate);
                
                frm.min_km_day = car.min_km_day;
                frm.set_df_property('min_km', 'label', 'Total Min Km');
            }
            calculate_charges(frm);
        });
    },

    pickup_datetime(frm) { calculate_charges(frm); },
    return_datetime(frm) { calculate_charges(frm); },
    start_km(frm) { calculate_charges(frm); },
    end_km(frm) { calculate_charges(frm); },
    
    per_hour_rate(frm) { calculate_charges(frm); },
    per_km_rate(frm) { calculate_charges(frm); },
    min_hours(frm) { calculate_charges(frm); },
    night_rate(frm) { calculate_charges(frm); },

    min_km(frm) {
        if (!frm._calculating) update_totals_from_current(frm);
    },
    night_charges(frm) {
        if (!frm._calculating) update_totals_from_current(frm);
    }
});

function calculate_charges(frm) {
    if (frm._calculating) return;
    frm._calculating = true;
    try {
        if (frm.doc.booking_type === "Local") {
            calculate_local(frm);
        } else if (frm.doc.booking_type === "Outstation") {
            calculate_outstation(frm);
        } else if (frm.doc.booking_type === "Package") {
            calculate_package(frm);
        }
    } finally {
        frm._calculating = false;
    }
}

function calculate_local(frm) {
    const total_hours = get_hours_diff(frm.doc.pickup_datetime, frm.doc.return_datetime);
    
    const start_km = frm.doc.start_km || 0;
    const end_km = frm.doc.end_km || 0;
    let total_km = 0;
    if (end_km > start_km) total_km = end_km - start_km;
    frm.set_value("total_km", total_km);

    const min_hours = frm.doc.min_hours || 0;
    const min_km = frm.doc.min_km || 0;
    const per_hour_rate = frm.doc.per_hour_rate || 0;
    const per_km_rate = frm.doc.per_km_rate || 0;

    const base_amount = min_hours * per_hour_rate;
    frm.set_value("base_amount", base_amount);

    let extra_hours = 0;
    if (total_hours > min_hours) extra_hours = total_hours - min_hours;
    const extra_hour_charges = extra_hours * per_hour_rate;
    frm.set_value("extra_hour_charges", extra_hour_charges);

    let extra_km = 0;
    if (total_km > min_km) extra_km = total_km - min_km;
    const extra_km_charges = extra_km * per_km_rate;
    frm.set_value("extra_km_charges", extra_km_charges);

    update_totals(frm, base_amount + extra_hour_charges + extra_km_charges);
}

function calculate_outstation(frm) {
    const start = frappe.datetime.str_to_obj(frm.doc.pickup_datetime);
    const end = frappe.datetime.str_to_obj(frm.doc.return_datetime);
    let days = 1;
    let nights = 0;
    if (start && end) {
        const diff = end - start;
        days = Math.ceil(diff / (1000 * 60 * 60 * 24));
        if (days < 1) days = 1;
        nights = days - 1;
        if (nights < 0) nights = 0;
    }

    const night_rate = frm.doc.night_rate || 0;
    const night_charges = nights * night_rate;
    frm.set_value('night_charges', night_charges);

    const start_km = frm.doc.start_km || 0;
    const end_km = frm.doc.end_km || 0;
    let total_km = 0;
    if (end_km > start_km) total_km = end_km - start_km;
    frm.set_value("total_km", total_km);

    if (frm.min_km_day) {
        const total_min_km = frm.min_km_day * days;
        frm.set_value('min_km', total_min_km);
    }
    
    const min_km = frm.doc.min_km || 0; 
    let chargeable_km = total_km;
    if (total_km < min_km) chargeable_km = min_km;

    const per_km_rate = frm.doc.per_km_rate || 0;
    
    const base_amount = chargeable_km * per_km_rate;
    frm.set_value("base_amount", base_amount);
    
    frm.set_value("extra_km_charges", 0);
    frm.set_value("extra_hour_charges", 0);

    update_totals(frm, base_amount);
}

function calculate_package(frm) {
    const start_km = frm.doc.start_km || 0;
    const end_km = frm.doc.end_km || 0;
    let total_km = 0;
    if (end_km > start_km) total_km = end_km - start_km;
    frm.set_value("total_km", total_km);

    const start = frappe.datetime.str_to_obj(frm.doc.pickup_datetime);
    const end   = frappe.datetime.str_to_obj(frm.doc.return_datetime);
    let nights = 0;
    if (start && end) {
        const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
        nights = Math.max(days - 1, 0);
    }
    const night_rate = frm.doc.night_rate || 0;
    frm.set_value('night_charges', nights * night_rate);

    frm.set_value('min_hours', 0);
    frm.set_value('min_km', 0);
    frm.set_value('per_hour_rate', 0);
    frm.set_value('per_km_rate', 0);
    frm.set_value('base_amount', 0);
    frm.set_value('extra_km_charges', 0);
    frm.set_value('extra_hour_charges', 0);
}

function update_totals_from_current(frm) {
    if (frm.doc.booking_type === "Package") return;

    const base = frm.doc.base_amount || 0;
    const extra_km = frm.doc.extra_km_charges || 0;
    const extra_hr = frm.doc.extra_hour_charges || 0;
    update_totals(frm, base + extra_km + extra_hr);
}

function update_totals(frm, partial_total) {
    if (frm.doc.booking_type === "Package") return;

    const night_charges = frm.doc.night_charges || 0;
    const total_charges = partial_total + night_charges;
    
    const tax_total = frm.doc.tax_total || 0;
    const expense_total = frm.doc.billable_expense_total || 0;
    
    frm.set_value("grand_total", total_charges + tax_total + expense_total);
}

function get_hours_diff(start_str, end_str) {
    if (!start_str || !end_str) return 0;
    const start = frappe.datetime.str_to_obj(start_str);
    const end = frappe.datetime.str_to_obj(end_str);
    const diff_ms = end - start;
    let h = diff_ms / (1000 * 60 * 60);
    return (h < 0) ? 0 : h;
}

frappe.ui.form.on("Tax and Charges", {
    amount(frm) { calculate_taxes(frm); },
    rate(frm) { calculate_taxes(frm); }
});

function calculate_taxes(frm) {
    let tax = 0;
    (frm.doc.tax_and_charges || []).forEach(row => {
        tax += row.amount || 0;
    });
    frm.set_value("tax_total", tax);
    calculate_charges(frm);
}
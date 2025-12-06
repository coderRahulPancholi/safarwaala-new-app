// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("OutStation Bookings", {
  onload(frm) {
    // Set dynamic filter for Car
    frm.set_query('car', function() {
        var filters = {};
        if (frm.doc.assigned_to) {
            filters.belongs_to_vendor = frm.doc.assigned_to;
        }
        if (frm.doc.car_modal) {
            filters.modal = frm.doc.car_modal;
        }
        return { filters: filters };
    });

    // Set dynamic filter for Driver
    frm.set_query('driver', function() {
        var filters = {};
        if (frm.doc.assigned_to) {
            filters.owner_vendor = frm.doc.assigned_to;
        }
        return { filters: filters };
    });
  },

  assigned_to(frm) {
    // Reset dependent fields
    frm.set_value('car', '');
    frm.set_value('driver', '');
  },

  car_modal(frm) {
     // Reset dependent field
     frm.set_value('car', '');
  },

  refresh(frm) {
    let query_args = {
      filters: { docstatus: ["!=", 2], booking_id: frm.doc.name },
    };
    frm.add_custom_button("Fetch From Duty Slips", () => {
      const d = new frappe.ui.form.MultiSelectDialog({
        doctype: "Duty Slips",
        target: frm,
        setters: {
          booking_id: frm.doc.name,
        },
        add_filters_group: 1,
        get_query() {
          return {
            filters: {
              docstatus: ["!=", 2],
              booking_id: frm.doc.name,
            },
          };
        },

        async action(selections) {
          // Wait for all duty slip docs to be fetched
          for (const name of selections) {
            const doc = await frappe.db.get_doc("Duty Slips", name);
            
            // Update Booking with Actuals from Duty Slip
            if(doc.start_km) frm.set_value('start_km', doc.start_km);
            if(doc.end_km) frm.set_value('end_km', doc.end_km);
            if(doc.departure_datetime) frm.set_value('departure_datetime', doc.departure_datetime);
            if(doc.return_datetime) frm.set_value('return_datetime', doc.return_datetime);

            // Expenses fetching removed as per new logic (Vehicle Expense Log used instead)
          }

          d.dialog.hide();
          frappe.msgprint(__("Details fetched from Duty Slips."));
        },
      });
      
    });

    frm.add_custom_button(__("Fetch Billable Expenses"), function() {
        frappe.call({
            method: "safarwaala.booking_types.doctype.outstation_bookings.outstation_bookings.get_billable_expenses_total",
            args: {
                booking_id: frm.doc.name
            },
            callback: function(r) {
                if (r.message != null) {
                    frm.set_value("expense_total", r.message);
                    
                     // Recalculate Totals
                    if(frm.doc.night_charges !== undefined && frm.doc.km_amount !== undefined) {
                         frm.set_value("total", frm.doc.night_charges + frm.doc.km_amount);
                    }
                    // Calculate net total with the new expense total
                    frm.set_value("net_total", frm.doc.total + r.message);
                    // Recalculate Gross and Grand
                    frm.set_value("gross_total", frm.doc.net_total + frm.doc.tax_total);
                    frm.set_value("grand_total", frm.doc.gross_total - frm.doc.discount);
                    
                    frappe.msgprint(__("Expenses fetched and totals updated."));
                }
            }
        });
    });

    frm.add_custom_button(
      __("Make Invoice"),
      function () {
        frappe.new_doc("Customer Invoice", {
          customer: frm.doc.customer,
          invoice_item: [
            {
              booking_type: frm.doc.doctype,
              booking_id: frm.doc.name,
              amount: frm.doc.total + frm.doc.tax_total, // Use 'amount' as per schema
            },
          ],
        });
      },
      __("Create")
    );
    frm.add_custom_button(
      __("Make Duty Slip"),
      function () {
        frappe.new_doc("Duty Slips", {
          booking_type: frm.doc.doctype,
          booking_id: frm.doc.name,
          driver: frm.doc.driver,
          car: frm.doc.car,
          car_modal: frm.doc.car_modal,
          from: frm.doc.start_from, 
          to: frm.doc.to,
          departure_datetime: frm.doc.departure_datetime,
          return_datetime: frm.doc.return_datetime,
        });
      },
      __("Create")
    );

    frm.add_custom_button(
      __("Make Driver Payment"),
      function () {
        frappe.new_doc("Driver Payment", {
          booking_type: frm.doc.doctype, 
          booking_id: frm.doc.name,
          driver: frm.doc.driver,
          vendor: frm.doc.assigned_to,
          amount: frm.doc.expense_total || 0,
          details: "Allowance + Expenses for " + frm.doc.name
        });
      },
      __("Create")
    );
  },
  start_km(frm) {
    calculateDiffrence(frm);
    update_tax_total(frm);
    calculate_days_night(frm);
  },
  end_km(frm) {
    calculateDiffrence(frm);
    update_tax_total(frm);
    calculate_days_night(frm);
  },
  per_km_rate(frm) {
    calculateKmAmount(frm);
    update_tax_total(frm);
    calculate_days_night(frm);
  },
  diffrence_km(frm) {
    calculateKmAmount(frm);
    update_tax_total(frm);
    calculate_days_night(frm);
  },
  km_amount(frm) {
    update_tax_total(frm);
  },
  departure_datetime(frm) {
    calculate_days_night(frm);
    calculateNetAmount(frm);
  },
  return_datetime(frm) {
    calculate_days_night(frm);
    calculateNetAmount(frm);
  },
  before_save(frm) {
     // calcualte_expense_total(frm); // Legacy function relying on trip_expenses table
  },
});

const calculateDiffrence = (frm) => {
  const start_km = frm.doc.start_km;
  const end_km = frm.doc.end_km;
  const diffrence = end_km - start_km;
  frm.set_value("diffrence_km", diffrence);
  if (diffrence > frm.doc.min_km) {
    frm.set_value("chargeable_km", diffrence);
  } else {
    frm.set_value("chargeable_km", frm.doc.min_km);
  }
  calculateKmAmount(frm);
  calculateNetAmount(frm);
};
const calculateKmAmount = (frm) => {
  const diffrence = frm.doc.chargeable_km;
  const rate = frm.doc.per_km_rate;
  const amount = diffrence * rate;
  frm.set_value("km_amount", amount);
  update_tax_total(frm);
  calculateNetAmount(frm);
};
const calculateNetAmount = (frm) => {
  frm.set_value("total", frm.doc.night_charges + frm.doc.km_amount);
  update_tax_total(frm);
};

function calculate_days_night(frm) {
  const start = frappe.datetime.str_to_obj(frm.doc.departure_datetime);
  const end = frappe.datetime.str_to_obj(frm.doc.return_datetime);
  let timeDiff = end - start;
  let days = Math.ceil(timeDiff / (1000 * 60 * 60 * 24)); // inclusive
  let nights = days - 1;

  const minimum_km = frm.doc.min_km_per_day * days;
  const nights_fare = frm.doc.night_rate * nights;

  frm.set_value("night_charges", nights_fare);
  frm.set_value("min_km", minimum_km);
  frm.set_value("days", days);
  frm.set_value("nights", nights);
  calculateDiffrence(frm);
  calculateNetAmount(frm);
}

function calculate_expense_total(frm) {
  let total = 0;
  (frm.doc.trip_expenses || []).forEach((row) => {
    total += row.amount || 0;
  });

  frm.set_value("expense_total", total);
  frm.refresh_field("expense_total");
  calculate_all_totals(frm);
}
function calculate_all_totals(frm) {
  frm.set_value("total", frm.doc.night_charges + frm.doc.km_amount);
  frm.set_value("net_total", frm.doc.total + frm.doc.expense_total);
  frm.set_value("gross_total", frm.doc.net_total + frm.doc.tax_total);
  frm.set_value("grand_total", frm.doc.gross_total - frm.doc.discount);
}

frappe.ui.form.on("Tax and Charges", {
  apply_on(frm) {
    update_tax_total(frm);
  },
  amount(frm) {
    update_tax_total(frm);
  },
  rate(frm) {
    update_tax_total(frm);
  },
});

function update_tax_total(frm) {
  let prev_total = frm.doc.total || 0;
  let tax_total = 0;

  frm.doc.tax_and_charges.forEach((row, index) => {
    if (row.apply_on === "Prev Row") {
      row.total = prev_total + row.amount;
    } else if (row.apply_on === "Actual") {
      row.total = row.amount + frm.doc.total;
    }
    prev_total += row.amount;
    tax_total += row.amount;
  });

  frm.refresh_field("tax_and_charges");
  frm.set_value("tax_total", tax_total);
}

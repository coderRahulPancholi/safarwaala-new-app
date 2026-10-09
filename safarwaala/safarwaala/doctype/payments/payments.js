// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

// Direction decides the party type; keep the form from offering an impossible combination.
const DIRECTION_PARTY = {
    Inbound: "Customer",
    Outbound: "Vendors",
};

frappe.ui.form.on("Payments", {
    refresh(frm) {
        apply_direction(frm);
    },

    payment_direction(frm) {
        apply_direction(frm);
        // The old party belongs to the other side of the ledger.
        frm.set_value("party", null);
        frm.set_value("party_name", null);
    },

    booking(frm) {
        if (!frm.doc.booking || !frm.doc.payment_direction) return;

        const field = frm.doc.payment_direction === "Inbound" ? "customer" : "assigned_to";
        frappe.db.get_value("Bookings", frm.doc.booking, field, (r) => {
            if (r && r[field]) {
                frm.set_value("party", r[field]);
            }
        });
    },
});

const apply_direction = (frm) => {
    const party_type = DIRECTION_PARTY[frm.doc.payment_direction];
    if (party_type && frm.doc.party_type !== party_type) {
        frm.set_value("party_type", party_type);
    }
    // Party type is derived, never chosen by hand.
    frm.set_df_property("party_type", "read_only", Boolean(party_type));

    // Only offer bookings that actually involve the selected party.
    frm.set_query("booking", function () {
        const filters = {};
        if (frm.doc.party && frm.doc.payment_direction === "Inbound") {
            filters.customer = frm.doc.party;
        } else if (frm.doc.party && frm.doc.payment_direction === "Outbound") {
            filters.assigned_to = frm.doc.party;
        }
        return { filters: filters };
    });
};

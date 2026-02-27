// Copyright (c) 2026, nts and contributors
// For license information, please see license.txt

nts.ui.form.on("Delivery Challan", {
    refresh: function (frm) {
        // Add "Mark as Received" button for submitted challans
        if (frm.doc.docstatus === 1 &&
            ["Sent", "Partially Received"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Mark as Received"), function () {
                nts.confirm(
                    __("This will create a return stock entry and mark all items as received. Continue?"),
                    function () {
                        nts.call({
                            method: "delivery_challan.delivery_challan.doctype.delivery_challan.delivery_challan.mark_as_received",
                            args: {
                                name: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: __("Processing..."),
                            callback: function (r) {
                                if (r.message) {
                                    frm.reload_doc();
                                    nts.show_alert({
                                        message: __("Material received. Days outside: {0}", [r.message.days_outside]),
                                        indicator: "green"
                                    });
                                }
                            }
                        });
                    }
                );
            }, __("Actions")).addClass("btn-primary");
        }

        // View linked stock entries
        if (frm.doc.outgoing_stock_entry) {
            frm.add_custom_button(__("Outgoing Stock Entry"), function () {
                nts.set_route("Form", "Stock Entry", frm.doc.outgoing_stock_entry);
            }, __("View"));
        }

        if (frm.doc.incoming_stock_entry) {
            frm.add_custom_button(__("Incoming Stock Entry"), function () {
                nts.set_route("Form", "Stock Entry", frm.doc.incoming_stock_entry);
            }, __("View"));
        }

        // Set dashboard info
        if (frm.doc.days_outside && frm.doc.status === "Received") {
            frm.dashboard.add_indicator(
                __("Days Outside: {0}", [frm.doc.days_outside]),
                frm.doc.days_outside > 30 ? "orange" : "green"
            );
        }
    },

    company: function (frm) {
        // Clear and refetch warehouse when company changes
        frm.set_value("from_warehouse", "");
        frm.set_value("to_warehouse", "");

        if (frm.doc.company) {
            set_subcontracted_warehouse(frm);
        }
    },

    from_warehouse: function (frm) {
        // Set warehouse filter for company
        set_subcontracted_warehouse(frm);
    },

    setup: function (frm) {
        // Set query filters
        frm.set_query("from_warehouse", function () {
            return {
                filters: {
                    "company": frm.doc.company,
                    "is_group": 0
                }
            };
        });

        frm.set_query("supplier", function () {
            return {
                filters: {
                    "disabled": 0
                }
            };
        });

        frm.set_query("item_code", "items", function () {
            return {
                filters: {
                    "disabled": 0,
                    "is_stock_item": 1
                }
            };
        });
    }
});

function set_subcontracted_warehouse(frm) {
    if (frm.doc.company && !frm.doc.to_warehouse) {
        nts.call({
            method: "nts.client.get_value",
            args: {
                doctype: "Warehouse",
                filters: {
                    "warehouse_name": ["like", "%subcontract%"],
                    "company": frm.doc.company,
                    "is_group": 0,
                    "disabled": 0
                },
                fieldname: "name"
            },
            callback: function (r) {
                if (r.message && r.message.name) {
                    frm.set_value("to_warehouse", r.message.name);
                }
            }
        });
    }
}

nts.ui.form.on("Delivery Challan Item", {
    work_order: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.work_order) {
            nts.call({
                method: "nts.client.get",
                args: {
                    doctype: "Work Order",
                    name: row.work_order
                },
                callback: function (r) {
                    if (r.message && r.message.required_items) {
                        let required_items = r.message.required_items;
                        if (required_items.length > 0) {
                            // Set the first item in the current row
                            let first_item = required_items[0];

                            // Note: setting item_code will trigger its own fetch for item_name, uom, description
                            nts.model.set_value(cdt, cdn, "item_code", first_item.item_code);
                            nts.model.set_value(cdt, cdn, "qty", first_item.required_qty);

                            // For the remaining items, add new rows
                            for (let i = 1; i < required_items.length; i++) {
                                let new_row = frm.add_child("items");
                                new_row.work_order = row.work_order;
                                new_row.item_code = required_items[i].item_code;
                                new_row.qty = required_items[i].required_qty;

                                // Manually trigger item_code fetch for the new row
                                nts.call({
                                    method: "nts.client.get_value",
                                    args: {
                                        doctype: "Item",
                                        filters: { name: new_row.item_code },
                                        fieldname: ["stock_uom", "description"]
                                    },
                                    callback: function (r2) {
                                        if (r2.message) {
                                            nts.model.set_value(new_row.doctype, new_row.name, "uom", r2.message.stock_uom);
                                            nts.model.set_value(new_row.doctype, new_row.name, "description", r2.message.description);
                                        }
                                    }
                                });
                            }
                            frm.refresh_field("items");
                            nts.show_alert({
                                message: __("Fetched {0} BOM items from Work Order {1}", [required_items.length, row.work_order]),
                                indicator: "green"
                            });
                        }
                    }
                }
            });
        }
    },

    item_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            nts.call({
                method: "nts.client.get_value",
                args: {
                    doctype: "Item",
                    filters: { name: row.item_code },
                    fieldname: ["stock_uom", "description"]
                },
                callback: function (r) {
                    if (r.message) {
                        nts.model.set_value(cdt, cdn, "uom", r.message.stock_uom);
                        nts.model.set_value(cdt, cdn, "description", r.message.description);
                    }
                }
            });
        }
    }
});

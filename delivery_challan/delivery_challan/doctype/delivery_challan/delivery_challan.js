// Copyright (c) 2026, nts and contributors
// For license information, please see license.txt

nts.ui.form.on("Delivery Challan", {
    refresh: function (frm) {
        // Hide activity heatmap and connections, keep stats
        $(frm.wrapper).find(".form-heatmap, .form-links").hide();
        // Receive Items button (partial or full)
        if (frm.doc.docstatus === 1 &&
            ["Sent", "Partially Received"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Receive Items"), function () {
                show_receive_dialog(frm);
            }, __("Actions")).addClass("btn-primary");
        }

        // Dashboard indicators
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === "Sent" && frm.doc.sent_date) {
                let days = nts.datetime.get_day_diff(nts.datetime.nowdate(), frm.doc.sent_date);
                let color = days > 30 ? "red" : days > 14 ? "orange" : "blue";
                frm.dashboard.add_indicator(__("Outside for {0} days", [days]), color);
            }
            if (frm.doc.status === "Partially Received") {
                let total = 0, received = 0;
                (frm.doc.items || []).forEach(item => {
                    total += item.qty;
                    received += (item.qty_received || 0);
                });
                let pct = total > 0 ? Math.round((received / total) * 100) : 0;
                frm.dashboard.add_indicator(__("{0}% Received", [pct]), "orange");
            }
            if (frm.doc.days_outside && frm.doc.status === "Received") {
                frm.dashboard.add_indicator(
                    __("Days Outside: {0}", [frm.doc.days_outside]),
                    frm.doc.days_outside > 30 ? "orange" : "green"
                );
            }
        }

        // View linked stock entries
        if (frm.doc.outgoing_stock_entry) {
            frm.add_custom_button(__("Outgoing Stock Entry"), function () {
                nts.set_route("Form", "Stock Entry", frm.doc.outgoing_stock_entry);
            }, __("View"));
        }
        if (frm.doc.incoming_stock_entry) {
            let entries = frm.doc.incoming_stock_entry.split(",");
            entries.forEach(function (se) {
                se = se.trim();
                if (se) {
                    frm.add_custom_button(__("Return: {0}", [se]), function () {
                        nts.set_route("Form", "Stock Entry", se);
                    }, __("View"));
                }
            });
        }
    },

    company: function (frm) {
        frm.set_value("from_warehouse", "");
        frm.set_value("to_warehouse", "");
        if (frm.doc.company) {
            set_subcontracted_warehouse(frm);
        }
    },

    from_warehouse: function (frm) {
        set_subcontracted_warehouse(frm);
    },

    setup: function (frm) {
        frm.set_query("from_warehouse", function () {
            return {
                filters: {
                    "company": frm.doc.company,
                    "is_group": 0
                }
            };
        });

        frm.set_query("supplier", function () {
            return { filters: { "disabled": 0 } };
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

function show_receive_dialog(frm) {
    let fields = [
        {
            fieldtype: "HTML",
            fieldname: "items_html",
            label: __("Items to Receive")
        }
    ];

    // Build item rows for dialog
    let pending_items = [];
    (frm.doc.items || []).forEach(function (item) {
        let pending = item.qty - (item.qty_received || 0);
        if (pending > 0) {
            pending_items.push({
                name: item.name,
                item_code: item.item_code,
                total_qty: item.qty,
                received: item.qty_received || 0,
                pending: pending
            });
            let label = item.item_code + " (Pending: " + pending + ")";
            let desc = "Total: " + item.qty + " | Already Received: " + (item.qty_received || 0);
            if (item.operation) {
                desc += " | Operation: " + item.operation;
            }
            fields.push({
                fieldtype: "Float",
                fieldname: "qty_" + item.name,
                label: label,
                default: pending,
                description: desc
            });
        }
    });

    if (pending_items.length === 0) {
        nts.msgprint(__("All items have already been received."));
        return;
    }

    let d = new nts.ui.Dialog({
        title: __("Receive Items"),
        fields: fields,
        size: "large",
        primary_action_label: __("Receive"),
        primary_action: function (values) {
            let received_items = [];
            pending_items.forEach(function (item) {
                let qty = values["qty_" + item.name] || 0;
                if (qty > 0) {
                    received_items.push({
                        name: item.name,
                        qty: qty
                    });
                }
            });

            if (received_items.length === 0) {
                nts.msgprint(__("Please enter at least one quantity"));
                return;
            }

            d.hide();
            nts.call({
                method: "delivery_challan.delivery_challan.doctype.delivery_challan.delivery_challan.receive_items",
                args: {
                    name: frm.doc.name,
                    received_items: JSON.stringify(received_items)
                },
                freeze: true,
                freeze_message: __("Processing receipt..."),
                callback: function (r) {
                    if (r.message) {
                        frm.reload_doc();
                        nts.show_alert({
                            message: __("Items received successfully"),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    });

    d.show();
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
                            let first_item = required_items[0];
                            nts.model.set_value(cdt, cdn, "item_code", first_item.item_code);
                            nts.model.set_value(cdt, cdn, "qty", first_item.required_qty);

                            for (let i = 1; i < required_items.length; i++) {
                                let new_row = frm.add_child("items");
                                new_row.work_order = row.work_order;
                                new_row.item_code = required_items[i].item_code;
                                new_row.qty = required_items[i].required_qty;

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

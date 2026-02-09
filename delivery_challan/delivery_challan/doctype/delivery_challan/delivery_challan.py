# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

import nts
from nts import _
from nts.model.document import Document
from nts.utils import now_datetime, date_diff, getdate, today


class DeliveryChallan(Document):
	def validate(self):
		self.validate_items()
		self.set_subcontracted_warehouse()

	def validate_items(self):
		if not self.items:
			nts.throw(_("Please add at least one item"))
		
		for item in self.items:
			if item.qty <= 0:
				nts.throw(_("Quantity must be greater than 0 for item {0}").format(item.item_code))

	def set_subcontracted_warehouse(self):
		"""Auto-set the to_warehouse to a warehouse with 'subcontract' in name"""
		if not self.to_warehouse:
			warehouse = nts.db.get_value(
				"Warehouse",
				filters={
					"warehouse_name": ["like", "%subcontract%"],
					"company": self.company,
					"is_group": 0,
					"disabled": 0
				},
				fieldname="name"
			)
			
			if not warehouse:
				# Try without company filter
				warehouse = nts.db.get_value(
					"Warehouse",
					filters={
						"warehouse_name": ["like", "%subcontract%"],
						"is_group": 0,
						"disabled": 0
					},
					fieldname="name"
				)
			
			if warehouse:
				self.to_warehouse = warehouse
			else:
				nts.throw(_("No warehouse found with 'subcontract' in the name. Please create one."))

	def on_submit(self):
		self.create_outgoing_stock_entry()
		self.update_status("Sent")
		self.db_set("sent_date", now_datetime())

	def on_cancel(self):
		self.cancel_linked_stock_entries()
		self.update_status("Cancelled")

	def update_status(self, status):
		self.db_set("status", status)

	def create_outgoing_stock_entry(self):
		"""Create a Material Transfer stock entry from source to subcontracted warehouse"""
		stock_entry = nts.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = self.company
		stock_entry.from_warehouse = self.from_warehouse
		stock_entry.to_warehouse = self.to_warehouse
		stock_entry.posting_date = today()
		stock_entry.delivery_challan = self.name
		stock_entry.remarks = _("Material sent via Delivery Challan {0}").format(self.name)
		
		for item in self.items:
			stock_entry.append("items", {
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": item.uom,
				"s_warehouse": self.from_warehouse,
				"t_warehouse": self.to_warehouse
			})
		
		stock_entry.insert()
		stock_entry.submit()
		
		self.db_set("outgoing_stock_entry", stock_entry.name)
		nts.msgprint(_("Stock Entry {0} created for material transfer").format(
			nts.utils.get_link_to_form("Stock Entry", stock_entry.name)
		))

	def cancel_linked_stock_entries(self):
		"""Cancel linked stock entries when challan is cancelled"""
		for field in ["outgoing_stock_entry", "incoming_stock_entry"]:
			stock_entry_name = self.get(field)
			if stock_entry_name:
				stock_entry = nts.get_doc("Stock Entry", stock_entry_name)
				if stock_entry.docstatus == 1:
					stock_entry.cancel()
					nts.msgprint(_("Cancelled Stock Entry {0}").format(stock_entry_name))

	@nts.whitelist()
	def mark_as_received(self, items=None):
		"""Mark material as received and create return stock entry"""
		if self.status not in ["Sent", "Partially Received"]:
			nts.throw(_("Can only mark as received when status is Sent or Partially Received"))
		
		if self.incoming_stock_entry:
			nts.throw(_("Material has already been received. Stock Entry: {0}").format(
				self.incoming_stock_entry
			))
		
		# Create return stock entry
		self.create_incoming_stock_entry()
		
		# Update items as received
		for item in self.items:
			nts.db.set_value("Delivery Challan Item", item.name, {
				"qty_received": item.qty,
				"is_received": 1
			})
		
		# Calculate days outside
		days = 0
		if self.sent_date:
			days = date_diff(today(), getdate(self.sent_date))
		
		self.db_set({
			"status": "Received",
			"received_date": now_datetime(),
			"days_outside": days
		})
		
		nts.msgprint(_("Material marked as received. Days outside: {0}").format(days))

	def create_incoming_stock_entry(self):
		"""Create a Material Transfer stock entry from subcontracted warehouse back to source"""
		stock_entry = nts.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = self.company
		stock_entry.from_warehouse = self.to_warehouse  # Reverse direction
		stock_entry.to_warehouse = self.from_warehouse
		stock_entry.posting_date = today()
		stock_entry.delivery_challan = self.name
		stock_entry.remarks = _("Material received back via Delivery Challan {0}").format(self.name)
		
		for item in self.items:
			stock_entry.append("items", {
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": item.uom,
				"s_warehouse": self.to_warehouse,
				"t_warehouse": self.from_warehouse
			})
		
		stock_entry.insert()
		stock_entry.submit()
		
		self.db_set("incoming_stock_entry", stock_entry.name)
		nts.msgprint(_("Return Stock Entry {0} created").format(
			nts.utils.get_link_to_form("Stock Entry", stock_entry.name)
		))


@nts.whitelist()
def mark_as_received(name, items=None):
	"""Whitelist method to mark delivery challan as received"""
	doc = nts.get_doc("Delivery Challan", name)
	doc.mark_as_received(items)
	return {"status": "success", "days_outside": doc.days_outside}

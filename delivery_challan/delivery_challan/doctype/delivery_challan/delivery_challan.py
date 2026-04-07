# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

import json
import nts
from nts import _
from nts.model.document import Document
from nts.utils import now_datetime, date_diff, getdate, today, flt
import traceback


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
		self.detect_pending_operations()
		self.update_status("Sent")
		self.db_set("sent_date", now_datetime())

	def on_cancel(self):
		self.cancel_linked_stock_entries()
		self.update_status("Cancelled")

	def update_status(self, status):
		self.db_set("status", status)

	# ─── Operation Detection ───────────────────────────────────────────

	def detect_pending_operations(self):
		"""For each item with a Work Order, detect the next pending SUBCONTRACTED operation."""
		wo_cache = {}
		
		for item in self.items:
			if not item.work_order:
				continue
			
			if item.work_order not in wo_cache:
				wo_cache[item.work_order] = self._get_next_subcontracted_operation(item.work_order)
			
			op_info = wo_cache[item.work_order]
			if op_info:
				nts.db.set_value("Delivery Challan Item", item.name, {
					"operation": op_info.get("operation"),
					"operation_idx": op_info.get("idx"),
					"follows_prod_qty": op_info.get("follows_prod_qty") or 0,
					"operation_completed": 0
				})
		
		if wo_cache:
			ops_found = [v for v in wo_cache.values() if v]
			if ops_found:
				op_names = [o["operation"] for o in ops_found]
				nts.msgprint(
					_("Linked to subcontracted operation(s): {0}").format(", ".join(op_names)),
					indicator="blue"
				)

	def _is_subcontracted_workstation(self, workstation_name):
		"""Check if a workstation name contains 'subcontract' (case-insensitive)."""
		if not workstation_name:
			return False
		return "subcontract" in workstation_name.lower()

	def _get_next_subcontracted_operation(self, work_order_name):
		"""Find the next pending operation that has a subcontracted workstation."""
		try:
			wo = nts.get_doc("Work Order", work_order_name)
			if wo.docstatus != 1:
				return None
			
			operations = wo.get("operations") or []
			if not operations:
				return None
			
			for idx, op_row in enumerate(operations):
				# Only consider operations with subcontracted workstation
				workstation = op_row.get("workstation") or ""
				if not self._is_subcontracted_workstation(workstation):
					continue
				
				completed_qty = flt(op_row.get("completed_qty") or 0)
				# Read fresh from DB
				try:
					if op_row.get("name"):
						vals = nts.db.get_value(
							"Work Order Operation", op_row.get("name"),
							["completed_qty"], as_dict=True
						)
						if vals:
							completed_qty = flt(vals.get("completed_qty") or 0)
				except Exception:
					pass
				
				# Determine required qty
				required_qty = flt(
					op_row.get("operation_qty") or 
					op_row.get("for_quantity") or 
					op_row.get("qty") or 
					op_row.get("required_qty") or 0
				)
				if required_qty <= 0:
					required_qty = flt(wo.get("qty") or wo.get("production_qty") or 0)
				
				# Calculate pending
				if idx == 0:
					pending = max(0.0, required_qty - completed_qty)
				else:
					prev_op = operations[idx - 1]
					prev_completed = flt(prev_op.get("completed_qty") or 0)
					try:
						if prev_op.get("name"):
							vals = nts.db.get_value(
								"Work Order Operation", prev_op.get("name"),
								["completed_qty"], as_dict=True
							)
							if vals:
								prev_completed = flt(vals.get("completed_qty") or 0)
					except Exception:
						pass
					pending = max(0.0, prev_completed - completed_qty)
				
				if pending > 0:
					# Fetch follows_production_qty from Operation master
					follows_prod_qty = 0
					operation_name = op_row.get("operation") or ""
					if operation_name:
						follows_prod_qty = nts.db.get_value("Operation", operation_name, "follows_production_qty") or 0
					
					return {
						"operation": operation_name,
						"idx": idx,
						"pending_qty": pending,
						"workstation": workstation,
						"follows_prod_qty": follows_prod_qty
					}
			
			return None
		except Exception:
			nts.log_error(traceback.format_exc(), "DC detect pending operation")
			return None

	# ─── Stock Entry Creation ──────────────────────────────────────────

	def create_outgoing_stock_entry(self):
		"""Create a Material Transfer stock entry from source to subcontracted warehouse"""
		stock_entry = nts.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = self.company
		stock_entry.from_warehouse = self.from_warehouse
		stock_entry.to_warehouse = self.to_warehouse
		stock_entry.posting_date = today()
		stock_entry.remarks = _("Material sent via Delivery Challan {0}").format(self.name)
		
		for item in self.items:
			# If follows_prod_qty is checked, the DC 'qty' represents the Product Qty.
			# But we must transfer the equivalent RM Qty.
			# RM required per product = (production_qty / qty) if follows_prod_qty is false
			# if follows_prod_qty is true, item.qty is product qty, so RM to transfer = (actual RM per product) * item.qty
			
			transfer_qty = flt(item.qty)
			if item.follows_prod_qty and flt(item.production_qty) > 0:
				# We need to find the actual RM qty needed from the WO
				try:
					wo = nts.get_doc("Work Order", item.work_order)
					for wo_item in wo.required_items:
						if wo_item.item_code == item.item_code:
							rm_per_product = flt(wo_item.required_qty) / flt(wo.qty or wo.production_qty or 1)
							transfer_qty = flt(item.qty) * rm_per_product
							break
				except Exception:
					pass
			
			stock_entry.append("items", {
				"item_code": item.item_code,
				"qty": transfer_qty,
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
		if self.outgoing_stock_entry:
			try:
				se = nts.get_doc("Stock Entry", self.outgoing_stock_entry)
				if se.docstatus == 1:
					se.cancel()
					nts.msgprint(_("Cancelled Stock Entry {0}").format(self.outgoing_stock_entry))
			except Exception:
				nts.log_error(traceback.format_exc(), "DC cancel outgoing SE")
		
		if self.incoming_stock_entry:
			for se_name in self.incoming_stock_entry.split(","):
				se_name = se_name.strip()
				if se_name:
					try:
						se = nts.get_doc("Stock Entry", se_name)
						if se.docstatus == 1:
							se.cancel()
							nts.msgprint(_("Cancelled Stock Entry {0}").format(se_name))
					except Exception:
						nts.log_error(traceback.format_exc(), "DC cancel incoming SE")

	# ─── Receive Items (Partial) ───────────────────────────────────────

	@nts.whitelist()
	def receive_items(self, received_items):
		"""Receive specific quantities of items (supports partial).
		
		Stock entry transfers RM back at RM qty.
		Operation reporting uses the received qty.
		"""
		if self.status not in ["Sent", "Partially Received"]:
			nts.throw(_("Can only receive items when status is Sent or Partially Received"))
		
		if isinstance(received_items, str):
			received_items = json.loads(received_items)
		
		# Validate
		items_to_receive = []
		for entry in received_items:
			row = nts.get_doc("Delivery Challan Item", entry.get("name"))
			recv_qty = flt(entry.get("qty"))
			pending = flt(row.qty) - flt(row.qty_received)
			
			if recv_qty <= 0:
				continue
			
			if recv_qty > pending + 0.001:
				nts.throw(_("Cannot receive {0} for {1}. Pending qty is {2}").format(
					recv_qty, row.item_code, pending
				))
			
			items_to_receive.append({
				"row": row,
				"recv_qty": recv_qty
			})
		
		if not items_to_receive:
			nts.throw(_("Please enter quantities to receive"))
		
		# Create return stock entry (always uses RM qty — material transfer back)
		stock_entry = nts.new_doc("Stock Entry")
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = self.company
		stock_entry.from_warehouse = self.to_warehouse
		stock_entry.to_warehouse = self.from_warehouse
		stock_entry.posting_date = today()
		stock_entry.remarks = _("Material received back via Delivery Challan {0}").format(self.name)
		
		# We will fetch WIP warehouse for Work Order items
		wo_wip_cache = {}

		for entry in items_to_receive:
			row = entry["row"]
			recv_qty = entry["recv_qty"]
			
			# Determine target warehouse
			target_warehouse = self.from_warehouse
			if row.work_order:
				if row.work_order not in wo_wip_cache:
					wip_wh = nts.db.get_value("Work Order", row.work_order, "wip_warehouse")
					wo_wip_cache[row.work_order] = wip_wh or self.from_warehouse
				target_warehouse = wo_wip_cache[row.work_order]
			
			# Logic matching outgoing stock entry:
			# If follows_prod_qty is true, recv_qty is the Product Qty. Convert to RM qty for stock.
			transfer_qty = recv_qty
			if row.follows_prod_qty and flt(row.production_qty) > 0:
				try:
					wo = nts.get_doc("Work Order", row.work_order)
					for wo_item in wo.required_items:
						if wo_item.item_code == row.item_code:
							rm_per_product = flt(wo_item.required_qty) / flt(wo.qty or wo.production_qty or 1)
							transfer_qty = recv_qty * rm_per_product
							break
				except Exception:
					pass
					
			stock_entry.append("items", {
				"item_code": row.item_code,
				"qty": transfer_qty,
				"uom": row.uom,
				"s_warehouse": self.to_warehouse,
				"t_warehouse": target_warehouse
			})
		
		stock_entry.insert()
		stock_entry.submit()
		
		# Update item received quantities
		for entry in items_to_receive:
			row = entry["row"]
			new_received = flt(row.qty_received) + entry["recv_qty"]
			is_fully_received = 1 if new_received >= flt(row.qty) else 0
			nts.db.set_value("Delivery Challan Item", row.name, {
				"qty_received": new_received,
				"is_received": is_fully_received
			})
		
		# Append to incoming stock entries list
		existing = self.incoming_stock_entry or ""
		if existing:
			new_list = existing + ", " + stock_entry.name
		else:
			new_list = stock_entry.name
		self.db_set("incoming_stock_entry", new_list)
		
		# Check if all items are fully received
		self.reload()
		all_received = all(flt(item.qty_received) >= flt(item.qty) for item in self.items)
		
		if all_received:
			days = 0
			if self.sent_date:
				days = date_diff(today(), getdate(self.sent_date))
			self.db_set({
				"status": "Received",
				"received_date": now_datetime(),
				"days_outside": days
			})
			nts.msgprint(_("All items received. Days outside: {0}").format(days))
			
			# Complete linked subcontracted operations
			self._complete_linked_operations()
		else:
			self.db_set("status", "Partially Received")
			nts.msgprint(_("Partial receipt recorded. Stock Entry: {0}").format(
				nts.utils.get_link_to_form("Stock Entry", stock_entry.name)
			))
		
		return {"status": "success", "stock_entry": stock_entry.name}

	# ─── Operation Completion ──────────────────────────────────────────

	def _complete_linked_operations(self):
		"""When all items are received, complete linked subcontracted WO operations."""
		# Group by (work_order, operation_idx) to complete each once
		wo_ops = {}
		for item in self.items:
			if not item.work_order or not item.operation or item.operation_completed:
				continue
			
			key = (item.work_order, item.operation_idx)
			if key not in wo_ops:
				wo_ops[key] = {
					"work_order": item.work_order,
					"operation": item.operation,
					"operation_idx": item.operation_idx,
					"production_qty": flt(item.production_qty),
					"item_names": []
				}
			wo_ops[key]["item_names"].append(item.name)
		
		if not wo_ops:
			return
		
		employee_number = self._get_employee_number()
		
		for key, op_info in wo_ops.items():
			try:
				self._report_operation_complete(
					work_order=op_info["work_order"],
					operation=op_info["operation"],
					operation_idx=op_info["operation_idx"],
					employee_number=employee_number,
					production_qty=op_info["production_qty"]
				)
				
				# Mark items as operation completed
				for item_name in op_info["item_names"]:
					nts.db.set_value("Delivery Challan Item", item_name, "operation_completed", 1)
				
				nts.msgprint(
					_("Operation '{0}' completed for Work Order {1}").format(
						op_info["operation"], op_info["work_order"]
					),
					indicator="green"
				)
			except Exception as e:
				nts.log_error(traceback.format_exc(), "DC complete operation failed")
				nts.msgprint(
					_("Could not auto-complete operation '{0}' for WO {1}: {2}").format(
						op_info["operation"], op_info["work_order"], str(e)
					),
					indicator="orange"
				)

	def _report_operation_complete(self, work_order, operation, operation_idx, employee_number, production_qty):
		"""Call the reporting app's report_operation API with the actual pending qty."""
		try:
			from reporting.reporting.api.work_order_ops import report_operation
		except ImportError:
			nts.msgprint(
				_("Reporting app not available. Operation '{0}' not auto-completed.").format(operation),
				indicator="yellow"
			)
			return None
		
		# Calculate the actual pending qty for this operation
		pending_qty = self._get_operation_pending_qty(work_order, operation_idx)
		
		if pending_qty <= 0:
			# Already completed, just mark our items
			return {"ok": True, "message": "Operation already completed"}
		
		# Use production_qty or pending_qty — whichever is available and valid
		produced_qty = pending_qty
		if production_qty and production_qty > 0:
			# Cap at pending to avoid over-production
			produced_qty = min(flt(production_qty), pending_qty)
		
		result = report_operation(
			work_order=work_order,
			op_index=operation_idx,
			operation_name=operation,
			employee_number=employee_number,
			produced_qty=produced_qty,
			process_loss=0,
			posting_datetime=now_datetime(),
			rejection_reason=None,
			_auto_complete=True
		)
		
		if not result or not result.get("ok"):
			msg = result.get("message", "Unknown error") if result else "No response"
			nts.throw(_("Operation reporting failed: {0}").format(msg))
		
		return result

	def _get_operation_pending_qty(self, work_order_name, operation_idx):
		"""Calculate the actual pending qty for a specific operation."""
		try:
			wo = nts.get_doc("Work Order", work_order_name)
			operations = wo.get("operations") or []
			idx = int(operation_idx)
			
			if idx < 0 or idx >= len(operations):
				return 0
			
			op_row = operations[idx]
			
			completed_qty = flt(op_row.get("completed_qty") or 0)
			try:
				if op_row.get("name"):
					vals = nts.db.get_value(
						"Work Order Operation", op_row.get("name"),
						["completed_qty"], as_dict=True
					)
					if vals:
						completed_qty = flt(vals.get("completed_qty") or 0)
			except Exception:
				pass
			
			required_qty = flt(
				op_row.get("operation_qty") or
				op_row.get("for_quantity") or
				op_row.get("qty") or
				op_row.get("required_qty") or 0
			)
			if required_qty <= 0:
				required_qty = flt(wo.get("qty") or wo.get("production_qty") or 0)
			
			if idx == 0:
				return max(0.0, required_qty - completed_qty)
			else:
				prev_op = operations[idx - 1]
				prev_completed = flt(prev_op.get("completed_qty") or 0)
				try:
					if prev_op.get("name"):
						vals = nts.db.get_value(
							"Work Order Operation", prev_op.get("name"),
							["completed_qty"], as_dict=True
						)
						if vals:
							prev_completed = flt(vals.get("completed_qty") or 0)
				except Exception:
					pass
				return max(0.0, prev_completed - completed_qty)
		except Exception:
			nts.log_error(traceback.format_exc(), "DC get pending qty")
			return 0

	def _get_employee_number(self):
		"""Get the employee number for the current user."""
		emp = nts.db.get_value(
			"Employee",
			{"user_id": nts.session.user},
			["name", "employee_name", "employee_number"],
			as_dict=True
		)
		if emp and emp.get("employee_number"):
			return emp.get("employee_number")
		if emp and emp.get("name"):
			return emp.get("name")
		return nts.session.user


@nts.whitelist()
def receive_items(name, received_items):
	"""Whitelist method for partial receiving"""
	doc = nts.get_doc("Delivery Challan", name)
	return doc.receive_items(received_items)

@nts.whitelist()
def get_next_subcontracted_operation(work_order_name):
	"""Whitelist method for JS to fetch next pending subcontracted operation details."""
	doc = nts.new_doc("Delivery Challan")
	return doc._get_next_subcontracted_operation(work_order_name)

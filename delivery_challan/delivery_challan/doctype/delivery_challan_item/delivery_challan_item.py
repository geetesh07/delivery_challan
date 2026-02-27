# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

# import nts
from nts.model.document import Document


class DeliveryChallanItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		description: DF.TextEditor | None
		is_received: DF.Check
		item_code: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty: DF.Float
		qty_received: DF.Float
		uom: DF.Link | None
	# end: auto-generated types

	pass

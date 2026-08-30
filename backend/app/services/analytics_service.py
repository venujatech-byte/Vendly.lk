from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.serialization import serialize_snapshot


ORDER_STATUSES = (
    "needs-confirmation",
    "confirmed",
    "packed",
    "shipped",
    "delivered",
    "returned",
    "cancelled",
)


def as_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def month_key(year, month):
    return f"{year:04d}-{month:02d}"


def recent_months(now, count=12):
    months = []
    year = now.year
    month = now.month

    for offset in range(count - 1, -1, -1):
        absolute_month = (year * 12 + month - 1) - offset
        selected_year, selected_month_index = divmod(absolute_month, 12)
        months.append(month_key(selected_year, selected_month_index + 1))

    return months


def delivered_financials(order):
    product_revenue = max(
        order.get("subtotalMinor", 0) - order.get("discountTotalMinor", 0),
        0,
    )
    cost_of_goods = sum(
        item.get("unitCostMinor", 0) * item.get("quantity", 0)
        for item in order.get("items", [])
    )
    return product_revenue, cost_of_goods, product_revenue - cost_of_goods


def delivered_item_financials(order):
    """Allocate an order discount across its items and return integer totals.

    The final item receives the rounding remainder, so product revenue always
    adds up to the delivered order's product revenue exactly.
    """
    items = order.get("items", [])
    line_totals = [max(int(item.get("lineTotalMinor", 0) or 0), 0) for item in items]
    subtotal = sum(line_totals)
    discount = min(max(int(order.get("discountTotalMinor", 0) or 0), 0), subtotal)
    allocated = 0
    results = []

    for index, (item, line_total) in enumerate(zip(items, line_totals)):
        item_discount = (
            discount - allocated
            if index == len(items) - 1
            else (discount * line_total // subtotal if subtotal else 0)
        )
        allocated += item_discount
        quantity = max(int(item.get("quantity", 0) or 0), 0)
        cost = max(int(item.get("unitCostMinor", 0) or 0), 0) * quantity
        revenue = max(line_total - item_discount, 0)
        results.append({
            "item": item,
            "quantity": quantity,
            "revenueMinor": revenue,
            "costOfGoodsMinor": cost,
            "grossProfitMinor": revenue - cost,
        })

    return results


def percentage(part, whole):
    """Return a dashboard-friendly percentage without risking division by zero."""
    return round((part / whole) * 100, 1) if whole else 0


def recent_order_summary(order):
    """Keep the Overview payload small while retaining useful order context."""
    customer = order.get("customerSnapshot", {})
    return {
        "id": order.get("id", ""),
        "orderNumber": order.get("orderNumber", "Order"),
        "customerName": customer.get("name") or "Customer",
        "itemCount": order.get("itemCount") or sum(
            item.get("quantity", 0) for item in order.get("items", [])
        ),
        "totalAmountMinor": order.get("totalAmountMinor", 0),
        "fulfilmentStatus": order.get(
            "fulfilmentStatus",
            "needs-confirmation",
        ),
        "createdAt": order.get("createdAt"),
    }


def _product_unit_cost(product):
    """Return the current weighted unit cost for a product's available stock."""
    variants = product.get("variantSummaries") or []
    stocked_variants = [
        variant for variant in variants
        if max(int(variant.get("stockAvailable", 0) or 0), 0) > 0
    ]
    if not stocked_variants:
        return max(int(product.get("costPriceMinor", 0) or 0), 0)

    stocked_units = sum(
        max(int(variant.get("stockAvailable", 0) or 0), 0)
        for variant in stocked_variants
    )
    stocked_cost = sum(
        max(int(variant.get("stockAvailable", 0) or 0), 0)
        * max(int(variant.get("costPriceMinor", 0) or 0), 0)
        for variant in stocked_variants
    )
    return stocked_cost // stocked_units if stocked_units else 0


def build_dead_stock_report(products, orders, now=None, stale_days=60):
    """Find stocked products that have never sold or have been idle too long.

    Only delivered orders count as sales. Returned, cancelled and incomplete
    orders must not make an inactive product appear healthy.
    """
    now = now or datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=90)
    last_sales = {}
    recent_units = defaultdict(int)

    for order in orders:
        if order.get("fulfilmentStatus") != "delivered":
            continue
        sold_at = as_datetime(order.get("createdAt"))
        if not sold_at:
            continue
        for item in order.get("items", []):
            product_id = item.get("productId")
            if not product_id:
                continue
            if product_id not in last_sales or sold_at > last_sales[product_id]:
                last_sales[product_id] = sold_at
            if sold_at >= recent_cutoff:
                recent_units[product_id] += max(int(item.get("quantity", 0) or 0), 0)

    rows = []
    for product in products:
        if product.get("status", "active") != "active":
            continue
        product_id = product.get("id")
        stock = max(int(product.get("availableStock", 0) or 0), 0)
        if not product_id or stock <= 0:
            continue

        last_sold_at = last_sales.get(product_id)
        days_since_sale = (now - last_sold_at).days if last_sold_at else None
        if last_sold_at and days_since_sale < stale_days:
            continue

        unit_cost = _product_unit_cost(product)
        selling_price = max(int(product.get("sellingPriceMinor", 0) or 0), 0)
        margin = percentage(selling_price - unit_cost, selling_price)
        media = product.get("media") or []
        image_url = next(
            (item.get("url") or item.get("path") for item in media
             if item.get("type", "image") == "image"),
            "",
        )
        if not image_url:
            image_url = next(
                (variant.get("imageUrl", "") for variant in
                 product.get("variantSummaries", []) if variant.get("imageUrl")),
                "",
            )

        if last_sold_at is None:
            state = "never-sold"
            recommendation = "Launch a promotion or bundle"
        elif days_since_sale >= 120:
            state = "critical"
            recommendation = "Discount or clear this stock"
        else:
            state = "stale"
            recommendation = "Promote to recent customers"

        rows.append({
            "id": product_id,
            "name": product.get("name") or "Product",
            "sku": product.get("skuPrefix") or "—",
            "categoryName": product.get("categoryName") or "Uncategorized",
            "imageUrl": image_url,
            "availableStock": stock,
            "unitCostMinor": unit_cost,
            "sellingPriceMinor": selling_price,
            "tiedUpCostMinor": stock * unit_cost,
            "grossMarginPercent": margin,
            "lastSoldAt": last_sold_at,
            "daysSinceLastSale": days_since_sale,
            "unitsSoldLast90Days": recent_units[product_id],
            "state": state,
            "recommendation": recommendation,
        })

    rows.sort(
        key=lambda row: (
            row["state"] == "never-sold",
            row["daysSinceLastSale"] or 999999,
            row["tiedUpCostMinor"],
        ),
        reverse=True,
    )
    return {
        "summary": {
            "productCount": len(rows),
            "stockUnits": sum(row["availableStock"] for row in rows),
            "tiedUpCostMinor": sum(row["tiedUpCostMinor"] for row in rows),
            "neverSoldCount": sum(row["state"] == "never-sold" for row in rows),
        },
        "staleAfterDays": stale_days,
        "products": rows,
    }


def calculate_analytics(
    orders,
    products,
    customers=None,
    unread_notification_count=0,
    now=None,
    warranty_claims=None,
):
    now = now or datetime.now(timezone.utc)
    customers = customers or []
    warranty_claims = warranty_claims or []
    status_counts = {status: 0 for status in ORDER_STATUSES}
    product_revenue_minor = 0
    cost_of_goods_minor = 0
    gross_profit_minor = 0
    top_products = defaultdict(
        lambda: {
            "name": "Product",
            "quantity": 0,
            "revenueMinor": 0,
            "costOfGoodsMinor": 0,
            "grossProfitMinor": 0,
            "warrantyDeductionsMinor": 0,
        },
    )
    day_keys = [
        (now.date() - timedelta(days=offset)).isoformat()
        for offset in range(6, -1, -1)
    ]
    daily_counts = {key: 0 for key in day_keys}
    selected_months = recent_months(now)
    monthly_revenue = {key: 0 for key in selected_months}

    for order in orders:
        status = order.get("fulfilmentStatus", "needs-confirmation")
        if status in status_counts:
            status_counts[status] += 1

        created_at = as_datetime(order.get("createdAt"))
        if created_at and created_at.date().isoformat() in daily_counts:
            daily_counts[created_at.date().isoformat()] += 1

        if status != "delivered":
            continue

        revenue, cost, profit = delivered_financials(order)
        product_revenue_minor += revenue
        cost_of_goods_minor += cost
        gross_profit_minor += profit

        if created_at:
            key = month_key(created_at.year, created_at.month)
            if key in monthly_revenue:
                monthly_revenue[key] += revenue

        for item_financials in delivered_item_financials(order):
            item = item_financials["item"]
            product_id = item.get("productId", "unknown")
            summary = top_products[product_id]
            summary["id"] = product_id
            summary["name"] = item.get("name", "Product")
            summary["quantity"] += item_financials["quantity"]
            summary["revenueMinor"] += item_financials["revenueMinor"]
            summary["costOfGoodsMinor"] += item_financials["costOfGoodsMinor"]
            summary["grossProfitMinor"] += item_financials["grossProfitMinor"]

    active_orders = [
        order
        for order in orders
        if order.get("fulfilmentStatus") != "cancelled"
    ]
    total_order_value = sum(
        order.get("totalAmountMinor", 0) for order in active_orders
    )
    low_stock_count = sum(
        product.get("stockStatus") == "low-stock" for product in products
    )
    out_of_stock_count = sum(
        product.get("stockStatus") == "out-of-stock" for product in products
    )
    completed_orders = status_counts["delivered"] + status_counts["returned"]
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    current_week_orders = 0
    previous_week_orders = 0

    for order in orders:
        created_at = as_datetime(order.get("createdAt"))
        if not created_at:
            continue
        if created_at >= seven_days_ago:
            current_week_orders += 1
        elif created_at >= fourteen_days_ago:
            previous_week_orders += 1

    weekly_order_change = (
        percentage(current_week_orders - previous_week_orders, previous_week_orders)
        if previous_week_orders
        else (100 if current_week_orders else 0)
    )
    recent_orders = sorted(
        orders,
        key=lambda order: as_datetime(order.get("createdAt"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:5]

    # A supplier-paid claim has no financial cost to the seller. A shop warranty
    # refunds the claimed item value, while a shop repair costs only its repair fee.
    warranty_deductions_minor = sum(
        claim.get("revenueImpactMinor", 0)
        for claim in warranty_claims
        # This analytics endpoint currently reports online delivered revenue.
        # Physical-shop deductions are applied to the Shop Orders revenue card.
        if claim.get("status") != "cancelled" and claim.get("sourceType") == "online-order"
    )
    product_revenue_minor = max(product_revenue_minor - warranty_deductions_minor, 0)
    gross_profit_minor -= warranty_deductions_minor

    for claim in warranty_claims:
        if (
            claim.get("status") == "cancelled"
            or claim.get("sourceType") != "online-order"
        ):
            continue
        impact = max(int(claim.get("revenueImpactMinor", 0) or 0), 0)
        item = claim.get("item") or {}
        product_id = item.get("productId")
        if not product_id or not impact:
            continue
        summary = top_products[product_id]
        summary["id"] = product_id
        summary["name"] = item.get("name") or summary["name"]
        summary["warrantyDeductionsMinor"] += impact
        summary["revenueMinor"] = max(summary["revenueMinor"] - impact, 0)
        summary["grossProfitMinor"] -= impact

    product_profitability = []
    for summary in top_products.values():
        product_profitability.append({
            **summary,
            "grossMarginPercent": percentage(
                summary["grossProfitMinor"],
                summary["revenueMinor"],
            ),
        })

    return {
        "orderCounts": {"all": len(orders), **status_counts},
        "inventory": {
            "productCount": len(products),
            "totalUnits": sum(product.get("availableStock", 0) for product in products),
            "lowStockCount": low_stock_count,
            "outOfStockCount": out_of_stock_count,
        },
        "customers": {"total": len(customers)},
        "financials": {
            "productRevenueMinor": product_revenue_minor,
            "warrantyDeductionsMinor": warranty_deductions_minor,
            "costOfGoodsMinor": cost_of_goods_minor,
            "grossProfitMinor": gross_profit_minor,
            "averageOrderValueMinor": (
                total_order_value // len(active_orders) if active_orders else 0
            ),
        },
        "performance": {
            "ordersToday": daily_counts[now.date().isoformat()],
            "currentWeekOrders": current_week_orders,
            "weeklyOrderChangePercent": weekly_order_change,
            "deliverySuccessPercent": percentage(
                status_counts["delivered"],
                completed_orders,
            ),
            "returnRatePercent": percentage(
                status_counts["returned"],
                completed_orders,
            ),
            "grossMarginPercent": percentage(
                gross_profit_minor,
                product_revenue_minor,
            ),
        },
        "dailyOrders": [
            {"date": key, "count": daily_counts[key]} for key in day_keys
        ],
        "monthlyRevenue": [
            {"month": key, "revenueMinor": monthly_revenue[key]}
            for key in selected_months
        ],
        "topProducts": sorted(
            top_products.values(),
            key=lambda item: (item["quantity"], item["revenueMinor"]),
            reverse=True,
        )[:5],
        "productProfitability": sorted(
            product_profitability,
            key=lambda item: (item["grossProfitMinor"], item["revenueMinor"]),
            reverse=True,
        )[:5],
        "deadStock": build_dead_stock_report(products, orders, now=now),
        "recentOrders": [
            recent_order_summary(order) for order in recent_orders
        ],
        "workCentre": {
            "needsConfirmation": status_counts["needs-confirmation"],
            "needsPacking": status_counts["confirmed"],
            "lowStockProducts": low_stock_count,
            "outOfStockProducts": out_of_stock_count,
            "unreadNotifications": unread_notification_count,
        },
    }


def get_business_analytics(database, business_id):
    business_reference = database.collection("businesses").document(business_id)
    orders = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("orders")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1000)
        .stream()
    ]
    products = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("products").limit(1000).stream()
    ]
    customers = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("customers").limit(1000).stream()
    ]
    notifications = [
        snapshot.to_dict()
        for snapshot in business_reference.collection("notifications").limit(100).stream()
    ]
    warranty_claims = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("warrantyClaims").limit(1000).stream()
    ]
    return calculate_analytics(
        orders,
        products,
        customers,
        unread_notification_count=sum(
            not notification.get("isRead") for notification in notifications
        ),
        warranty_claims=warranty_claims,
    )


def _minor_units(value):
    """Coerce saved money values without allowing malformed data to break analytics."""
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _customer_name(record):
    customer = record.get("customerSnapshot") or {}
    return customer.get("name") or record.get("customerName") or "Walk-in customer"


def _item_names(record):
    names = [item.get("name") for item in record.get("items", []) if item.get("name")]
    return ", ".join(dict.fromkeys(names)) or "Sale"


def _latest_status_time(record, status):
    history = record.get("statusHistory") or []
    matching = [entry for entry in history if entry.get("to") == status]
    if matching:
        return matching[-1].get("changedAt") or record.get("updatedAt")
    return record.get("updatedAt") or record.get("createdAt")


def build_transaction_ledger(
    orders,
    shop_sales,
    warranty_claims,
    inventory_transactions=None,
):
    """Build a read-only sales ledger from the system's source documents.

    Every sale is recorded as a credit. A returned/cancelled online order or a
    voided shop sale receives a matching debit so its net effect is zero.
    Warranty costs and purchased inventory are debit adjustments. Inventory
    debits come only from positive stock-in audit records that carry their cost
    at the time of receipt. This keeps the ledger auditable while leaving the
    order, sale and stock write paths as the single source of truth.
    """
    entries = []

    def add_entry(**entry):
        entry["amountMinor"] = _minor_units(entry.get("amountMinor"))
        entry["createdAt"] = entry.get("createdAt")
        entries.append(entry)

    for order in orders:
        total_minor = _minor_units(order.get("totalAmountMinor"))
        status = order.get("fulfilmentStatus", "needs-confirmation")
        reference = order.get("orderNumber") or order.get("id") or "Order"
        shared = {
            "sourceId": order.get("id", ""),
            "sourceType": "online-order",
            "reference": reference,
            "customerName": _customer_name(order),
            "description": _item_names(order),
            "paymentMethod": order.get("paymentMethod", "cod"),
            "paymentStatus": order.get("paymentStatus", "unpaid"),
        }
        add_entry(
            **shared,
            id=f"order:{order.get('id') or reference}:sale",
            transactionType="online-order",
            label="Online order",
            direction="credit",
            amountMinor=total_minor,
            status=status,
            createdAt=order.get("createdAt"),
        )
        if status in {"returned", "cancelled"}:
            add_entry(
                **shared,
                id=f"order:{order.get('id') or reference}:{status}",
                transactionType=status,
                label="Order return" if status == "returned" else "Order cancellation",
                direction="debit",
                amountMinor=total_minor,
                status=status,
                createdAt=_latest_status_time(order, status),
            )

    for sale in shop_sales:
        total_minor = _minor_units(sale.get("totalAmountMinor"))
        status = sale.get("status", "completed")
        reference = sale.get("saleNumber") or sale.get("id") or "Shop sale"
        shared = {
            "sourceId": sale.get("id", ""),
            "sourceType": "shop-sale",
            "reference": reference,
            "customerName": _customer_name(sale),
            "description": _item_names(sale),
            "paymentMethod": sale.get("paymentMethod", "cash"),
            "paymentStatus": "paid" if status != "voided" else "voided",
        }
        add_entry(
            **shared,
            id=f"shop-sale:{sale.get('id') or reference}:sale",
            transactionType="shop-sale",
            label="Shop sale",
            direction="credit",
            amountMinor=total_minor,
            status=status,
            createdAt=sale.get("createdAt"),
        )
        if status == "voided":
            add_entry(
                **shared,
                id=f"shop-sale:{sale.get('id') or reference}:voided",
                transactionType="voided-sale",
                label="Voided shop sale",
                direction="debit",
                amountMinor=total_minor,
                status="voided",
                createdAt=sale.get("voidedAt") or sale.get("updatedAt"),
            )

    for claim in warranty_claims:
        impact_minor = _minor_units(claim.get("revenueImpactMinor"))
        add_entry(
            id=f"warranty:{claim.get('id') or claim.get('claimNumber', '')}",
            sourceId=claim.get("id", ""),
            sourceType=claim.get("sourceType", "warranty-claim"),
            reference=claim.get("claimNumber") or claim.get("sourceNumber") or "Warranty",
            customerName=claim.get("customerName") or "Customer",
            description=(claim.get("item") or {}).get("name") or claim.get("reason") or "Warranty claim",
            paymentMethod="adjustment",
            paymentStatus=claim.get("status", "open"),
            transactionType="warranty-adjustment",
            label="Warranty adjustment",
            direction="debit",
            amountMinor=impact_minor,
            status=claim.get("status", "open"),
            createdAt=claim.get("createdAt"),
        )

    for stock_entry in inventory_transactions or []:
        quantity = int(stock_entry.get("quantity") or 0)
        total_cost_minor = _minor_units(stock_entry.get("totalCostMinor"))
        if (
            quantity <= 0
            or total_cost_minor <= 0
            or stock_entry.get("ledgerImpact") != "inventory-debit"
        ):
            continue

        product_name = stock_entry.get("productName") or "Inventory item"
        sku = stock_entry.get("variantSku") or ""
        reference = stock_entry.get("reference") or product_name
        add_entry(
            id=f"inventory:{stock_entry.get('id') or stock_entry.get('variantId', '')}",
            sourceId=stock_entry.get("id", ""),
            sourceType="inventory-transaction",
            reference=reference,
            customerName="Inventory",
            description=(
                f"{product_name} · {sku} · {quantity} unit(s)"
                if sku
                else f"{product_name} · {quantity} unit(s)"
            ),
            paymentMethod="inventory-purchase",
            paymentStatus="recorded",
            transactionType="inventory-purchase",
            label="Inventory purchase",
            direction="debit",
            amountMinor=total_cost_minor,
            status="received",
            createdAt=stock_entry.get("createdAt"),
        )

    entries.sort(
        key=lambda entry: as_datetime(entry.get("createdAt"))
        or datetime.min.replace(tzinfo=timezone.utc),
    )
    running_balance = 0
    for entry in entries:
        if entry["direction"] == "credit":
            running_balance += entry["amountMinor"]
        else:
            running_balance -= entry["amountMinor"]
        entry["balanceMinor"] = running_balance

    total_credit = sum(
        entry["amountMinor"] for entry in entries if entry["direction"] == "credit"
    )
    total_debit = sum(
        entry["amountMinor"] for entry in entries if entry["direction"] == "debit"
    )
    entries.reverse()
    return {
        "summary": {
            "transactionCount": len(entries),
            "creditMinor": total_credit,
            "debitMinor": total_debit,
            "netMinor": total_credit - total_debit,
        },
        "entries": entries,
    }


def get_business_ledger(database, business_id):
    business_reference = database.collection("businesses").document(business_id)
    orders = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("orders").limit(1000).stream()
    ]
    shop_sales = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("shopSales").limit(1000).stream()
    ]
    warranty_claims = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("warrantyClaims").limit(1000).stream()
    ]
    inventory_transactions = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("inventoryTransactions")
        .limit(2000)
        .stream()
    ]
    return build_transaction_ledger(
        orders,
        shop_sales,
        warranty_claims,
        inventory_transactions,
    )

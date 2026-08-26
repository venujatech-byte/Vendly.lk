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
        lambda: {"name": "Product", "quantity": 0, "revenueMinor": 0},
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

        for item in order.get("items", []):
            product_id = item.get("productId", "unknown")
            summary = top_products[product_id]
            summary["id"] = product_id
            summary["name"] = item.get("name", "Product")
            summary["quantity"] += item.get("quantity", 0)
            summary["revenueMinor"] += item.get("lineTotalMinor", 0)

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

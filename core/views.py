from django.db.models import Q
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Product, Dealer, Order
from core.serializers import (
    ProductSerializer,
    ProductCreateSerializer,
    ProductUpdateSerializer,
    DealerSerializer,
    OrderSerializer,
)
from core.services.inventory_service import update_inventory
from core.services.order_service import (
    create_draft_order,
    update_draft_order_items,
    confirm_order,
    dispatch_order,
    deliver_order,
    cancel_order,
)
from core.pagination import StandardResultsSetPagination


@api_view(["GET"])
def health(request):
    """GET /api/health/ — the grader polls this until your app is ready."""
    return JsonResponse({"status": "ok"})


class ProductListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Product.objects.all().order_by("sku")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(sku__icontains=search)
                | Q(name__icontains=search)
                | Q(brand__icontains=search)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)

        vehicle = request.query_params.get("vehicle")
        if vehicle:
            qs = qs.filter(vehicle_fitment__icontains=vehicle)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        sku = request.data.get("sku")
        if sku and Product.objects.filter(sku=str(sku).strip()).exists():
            from core.exceptions import DuplicateError
            raise DuplicateError(
                message=f"Product with SKU '{sku}' already exists.",
                details=[f"sku: {sku} is a duplicate"],
            )
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    def get_object(self, sku):
        product = Product.objects.filter(sku=sku).first()
        if not product:
            raise NotFound(detail=f"Product with SKU '{sku}' not found.")
        return product

    def get(self, request, sku):
        product = self.get_object(sku)
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)

    def patch(self, request, sku):
        product = self.get_object(sku)
        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_product = serializer.save()
        return Response(ProductSerializer(updated_product).data, status=status.HTTP_200_OK)


class InventoryView(APIView):
    def put(self, request, sku):
        quantity = request.data.get("quantity")
        reason = request.data.get("reason", "")
        res = update_inventory(sku=sku, quantity=quantity, reason=reason)
        return Response(res, status=status.HTTP_200_OK)


class DealerListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Dealer.objects.all().order_by("id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = DealerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        dealer_code = request.data.get("dealer_code")
        if dealer_code and Dealer.objects.filter(dealer_code=str(dealer_code).strip()).exists():
            from core.exceptions import DuplicateError
            raise DuplicateError(
                message=f"Dealer with code '{dealer_code}' already exists.",
                details=[f"dealer_code: {dealer_code} is a duplicate"],
            )
        serializer = DealerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerDetailView(APIView):
    def get(self, request, pk):
        dealer = Dealer.objects.filter(id=pk).first()
        if not dealer:
            raise NotFound(detail=f"Dealer with id {pk} not found.")
        return Response(DealerSerializer(dealer).data, status=status.HTTP_200_OK)


class OrderListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Order.objects.prefetch_related("items").all().order_by("-created_at")

        dealer_id = request.query_params.get("dealer_id")
        if dealer_id:
            qs = qs.filter(dealer_id=dealer_id)

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        dealer_id = request.data.get("dealer_id")
        items = request.data.get("items")
        idempotency_key = request.headers.get("Idempotency-Key")

        order, created = create_draft_order(
            dealer_id=dealer_id,
            items_data=items,
            idempotency_key=idempotency_key,
        )
        resp_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(OrderSerializer(order).data, status=resp_status)


class OrderDetailView(APIView):
    def get(self, request, order_number):
        order = Order.objects.prefetch_related("items__product", "dealer").filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

    def put(self, request, order_number):
        items = request.data.get("items")
        order = update_draft_order_items(order_number, items)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderConfirmView(APIView):
    def post(self, request, order_number):
        order = confirm_order(order_number)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderDispatchView(APIView):
    def post(self, request, order_number):
        order = dispatch_order(order_number)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderDeliverView(APIView):
    def post(self, request, order_number):
        order = deliver_order(order_number)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderCancelView(APIView):
    def post(self, request, order_number):
        order = cancel_order(order_number)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class AssistantChatView(APIView):
    def post(self, request):
        session_id = request.data.get("session_id")
        dealer_id = request.data.get("dealer_id")
        message = request.data.get("message")

        from core.exceptions import ContractAPIException
        details = []
        if not session_id or not isinstance(session_id, str):
            details.append("session_id is required and must be a string.")
        if dealer_id is None or not isinstance(dealer_id, int):
            details.append("dealer_id is required and must be an integer.")
        if not message or not isinstance(message, str):
            details.append("message is required and must be a non-empty string.")

        if details:
            raise ContractAPIException(
                message="Invalid assistant chat request.",
                details=details,
            )

        from core.assistant.agent import run_assistant_turn
        result = run_assistant_turn(
            session_id=str(session_id).strip(),
            dealer_id=int(dealer_id),
            user_message=str(message).strip(),
        )

        return Response(result, status=status.HTTP_200_OK)


class ForecastDetailView(APIView):
    def get(self, request, sku):
        from forecasting.forecast_service import get_sku_forecast
        data = get_sku_forecast(sku)
        if not data:
            raise NotFound(detail=f"Forecast for SKU '{sku}' not found.")
        return Response(data, status=status.HTTP_200_OK)


class ReorderSuggestionsView(APIView):
    def get(self, request):
        from forecasting.reorder import calculate_reorder_suggestions
        results = calculate_reorder_suggestions()
        return Response({"results": results}, status=status.HTTP_200_OK)


class SupplierSyncView(APIView):
    def post(self, request):
        from core.services.supplier_sync_service import run_supplier_sync
        result = run_supplier_sync()
        return Response(result, status=status.HTTP_200_OK)



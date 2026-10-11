from django.urls import path
from core import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("products/", views.ProductListCreateView.as_view(), name="product-list-create"),
    path("products/<str:sku>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("inventory/<str:sku>/", views.InventoryView.as_view(), name="inventory-update"),
    path("dealers/", views.DealerListCreateView.as_view(), name="dealer-list-create"),
    path("dealers/<int:pk>/", views.DealerDetailView.as_view(), name="dealer-detail"),
    path("orders/", views.OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<str:order_number>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("assistant/chat/", views.AssistantChatView.as_view(), name="assistant-chat"),
]

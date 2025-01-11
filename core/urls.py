from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.add_supplier, name='add_supplier'),
    path('stock/movement/', views.add_stock_movement, name='add_stock_movement'),
    path('stock/levels/', views.check_stock_levels, name='check_stock_levels'),
    path('sales/', views.sale_order_list, name='sale_order_list'),
    path('sales/create/', views.create_sale_order, name='create_sale_order'),
    re_path(r'^sales/(?P<order_id>[a-f0-9]{24})/cancel/$', views.cancel_sale_order, name='cancel_sale_order'),
    re_path(r'^sales/(?P<order_id>[a-f0-9]{24})/complete/$', views.complete_sale_order, name='complete_sale_order'),
    path('products/<str:product_id>/delete/', views.delete_product, name='delete_product'),
    path('suppliers/<str:supplier_id>/delete/', views.delete_supplier, name='delete_supplier'),
    path('sales/<str:order_id>/delete/', views.delete_sale_order, name='delete_sale_order'),
    path('stock/movement/<str:movement_id>/delete/', views.delete_stock_movement, name='delete_stock_movement'),
    path('products/<str:product_id>/edit/', views.edit_product, name='edit_product'),
    path('suppliers/<str:supplier_id>/edit/', views.edit_supplier, name='edit_supplier'),
] 
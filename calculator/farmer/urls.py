from django.urls import path
from . import views


app_name = "farmer"

urlpatterns = [
    path('', views.home, name='home'),
    path('import/', views.show_import_form, name='show_import_form'),
    path('import_management_orders/', views.import_management_orders, name='import_management_orders'),
    path('orders_list/', views.orders_list, name='orders_list'),
    path('order_details/<str:order_id>/', views.order_details, name='order_details'),
    path('calculate_plan/<str:order_id>/', views.calculate_production_plan, name='calculate_plan'),
    path('multi-product-production-plan/', views.MultiProductProductionPlanView.as_view(),
         name='multi_product_production_plan'),

    path('save-production-plan-multi/', views.SaveProductionPlanView.as_view(), name='save_production_plan_multi'),
    path('save_production_plan/<int:order_id>/', views.save_production_plan, name='save_production_plan'),
    path('success/', views.success_page, name='success_page'),
    path('departments/',  views.ProductionDepartmentsListView.as_view(), name='production_departments_list'),
    path('products/',  views.ProductsListView.as_view(), name='products_list'),
    path('raw_materials/', views.RawMaterialStockListView.as_view(), name='raw_material_stock_list'),
    path('stocks/',  views.StockListView.as_view(), name='stock_list'),
    path('recipes/',  views.RecipesListView.as_view(), name='recipes_list'),
    path('plans/',  views.ProductionPlansListView.as_view(), name='production_plans_list'),

]

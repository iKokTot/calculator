
from django.contrib import admin
from .models import ProductionDepartment, Product, ManagementOrder, Stock, RawMaterialStock, Recipe, ProductionPlan

class ProductionDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'average_output')
    search_fields = ('name', 'product_type')

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'production_department', 'is_active')
    search_fields = ('name',)
    list_filter = ('production_department', 'is_active')

class ManagementOrderAdmin(admin.ModelAdmin):
    list_display = ('Order_id', 'product_code', 'start_date', 'end_date', 'quantity')
    search_fields = ('Order_id', 'product_code__name')
    list_filter = ('start_date', 'end_date')

class StockAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class RawMaterialStockAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'stok_id')
    search_fields = ('name',)
    list_filter = ('stok_id',)

class RecipeAdmin(admin.ModelAdmin):
    list_display = ('product', 'raw_material', 'required_quantity')
    search_fields = ('product__name', 'raw_material__name')

class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'planned_quantity')
    search_fields = ('order__Order_id', 'product__name')

admin.site.register(ProductionDepartment, ProductionDepartmentAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ManagementOrder, ManagementOrderAdmin)
admin.site.register(Stock, StockAdmin)
admin.site.register(RawMaterialStock, RawMaterialStockAdmin)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(ProductionPlan, ProductionPlanAdmin)

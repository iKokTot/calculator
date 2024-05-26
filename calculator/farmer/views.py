import json
from docx import Document
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from .models import ProductionDepartment, Product, RawMaterialStock, Stock, Recipe, ProductionPlan, ManagementOrder
from django.shortcuts import render, get_object_or_404,redirect
from django.core.exceptions import ValidationError
from django.db.models import Sum, F
from django.db import transaction
from collections import defaultdict
import os
import tempfile
from zipfile import ZipFile

@require_POST
def import_management_orders(request):
    try:
        json_file = request.FILES.get('json_file')
        if not json_file.name.endswith('.json'):
            return JsonResponse({'error': 'Неверный формат файла. Требуется JSON.'}, status=400)

        data = json.load(json_file)
        for item in data:
            # Проверка на дубликаты перед созданием
            if ManagementOrder.objects.filter(product_code=item['product_code'], start_date=item['start_date']).exists():
                return JsonResponse({'error': f'Заявка с кодом продукта {item["product_code"]} на дату {item["start_date"]} уже существует.'}, status=400)
            try:
                ManagementOrder.objects.create(
                    product_code=item['product_code'],
                    start_date=item['start_date'],
                    end_date=item['end_date'],
                    quantity=item['quantity']
                )
            except (KeyError, TypeError, ValidationError) as e:
                return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({'success': 'Данные успешно импортированы.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




def orders_list(request):
    orders = ManagementOrder.objects.values('Order_id').annotate(total=Count('id')).order_by('Order_id')
    return render(request, 'farmer/orders_list.html', {'orders': orders})

def order_details(request, order_id):
    # Получаем все заказы с данным Order_id
    orders = ManagementOrder.objects.filter(Order_id=order_id).select_related('product_code')
    # Получаем все рецепты для продуктов в заказах
    recipes = Recipe.objects.filter(product__in=[order.product_code for order in orders]).select_related('raw_material')
    # Передаем order_id, коллекцию заказов и рецепты в шаблон
    return render(request, 'farmer/order_details.html', {
        'orders': orders,
        'order_id': order_id,
        'recipes': recipes,
    })

def home(request):
    return render(request, 'farmer/home.html')

def show_import_form(request):
    return render(request, 'farmer/import.html')


def calculate_production_plan(request, order_id):
    # Получаем все заявки с данным order_id
    orders = ManagementOrder.objects.filter(Order_id=order_id).select_related('product_code', 'product_code__production_department')

    # Словарь для хранения общего необходимого количества каждого сырья
    total_required_materials = defaultdict(int)

    # Собираем информацию о необходимом количестве сырья для всех продуктов
    for order in orders:
        product = order.product_code
        required_quantity = order.quantity
        recipes = Recipe.objects.filter(product=product)

        for recipe in recipes:
            total_required_materials[recipe.raw_material.name] += recipe.required_quantity * required_quantity

    # Используем транзакцию для проверки наличия сырья и возможных операций с базой данных
    with transaction.atomic():
        # Словарь для хранения информации о возможности производства для каждого заказа
        production_possibility = {}
        materials_shortage = {}
        raw_materials_stock = RawMaterialStock.objects.filter(name__in=total_required_materials.keys())
        stock_dict = {stock.name: stock.quantity for stock in raw_materials_stock}

        # Проверяем наличие сырья на складе и корректируем остатки по мере использования
        for order in orders:
            product = order.product_code
            required_quantity = order.quantity
            recipes = Recipe.objects.filter(product=product)
            sufficient_resources = True
            shortages = {}

            for recipe in recipes:
                material_name = recipe.raw_material.name
                required_amount = recipe.required_quantity * required_quantity
                available_quantity = stock_dict.get(material_name, 0)

                if available_quantity < required_amount:
                    shortages[material_name] = required_amount - available_quantity
                    sufficient_resources = False
                else:
                    # Временно вычитаем необходимое количество из доступного
                    stock_dict[material_name] -= required_amount

            # Проверяем возможность выполнения заказов
            if sufficient_resources:
                production_department = product.production_department
                production_time = (order.end_date - order.start_date).days
                monthly_output = production_department.average_output
                required_months = required_quantity / monthly_output

                if production_time < required_months * 30:
                    delay = (required_months * 30) - production_time
                    production_possibility[product.name] = f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"
                else:
                    production_possibility[product.name] = f"Можно произвести {required_quantity} единиц за {required_months:.2f} месяцев"
            else:
                shortage_info = ', '.join([f"{material}: недостает {amount} ед." for material, amount in shortages.items()])
                production_possibility[product.name] = f"Недостаточно сырья: {shortage_info}"

    # Отображаем результаты расчёта
    context = {
        'orders': orders,
        'production_possibility': production_possibility,
    }
    return render(request, 'farmer/production_plan.html', context)

def success_page(request):
    return render(request, 'farmer/success_page.html')

def save_production_plan(request, order_id):
    if request.method == 'POST':
        # Получаем все заявки с данным order_id
        orders = ManagementOrder.objects.filter(Order_id=order_id).select_related('product_code', 'product_code__production_department')

        # Словарь для хранения информации о возможности производства для каждого заказа
        production_possibility = {}
        production_plans = []
        manager_report = []

        # Словарь для хранения общего необходимого количества каждого сырья
        total_required_materials = defaultdict(int)
        for order in orders:
            product = order.product_code
            required_quantity = order.quantity
            recipes = Recipe.objects.filter(product=product)
            for recipe in recipes:
                total_required_materials[recipe.raw_material.name] += recipe.required_quantity * required_quantity

        raw_materials_stock = RawMaterialStock.objects.filter(name__in=total_required_materials.keys())
        stock_dict = {stock.name: stock.quantity for stock in raw_materials_stock}

        for order in orders:
            product = order.product_code
            required_quantity = order.quantity
            recipes = Recipe.objects.filter(product=product)
            sufficient_resources = True
            shortages = {}

            for recipe in recipes:
                material_name = recipe.raw_material.name
                required_amount = recipe.required_quantity * required_quantity
                available_quantity = stock_dict.get(material_name, 0)

                if available_quantity < required_amount:
                    shortages[material_name] = required_amount - available_quantity
                    sufficient_resources = False
                else:
                    stock_dict[material_name] -= required_amount

            if sufficient_resources:
                production_department = product.production_department
                production_time = (order.end_date - order.start_date).days
                monthly_output = production_department.average_output
                required_months = required_quantity / monthly_output

                if production_time < required_months * 30:
                    delay = (required_months * 30) - production_time
                    production_possibility[product.name] = f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"
                    manager_report.append((product.name, f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"))
                else:
                    production_possibility[product.name] = f"Можно произвести {required_quantity} единиц за {required_months:.2f} месяцев"
                    production_plans.append(ProductionPlan(order=order, product=product, planned_quantity=required_quantity))
            else:
                shortage_info = ', '.join([f"{material}: недостает {amount} ед." for material, amount in shortages.items()])
                production_possibility[product.name] = f"Недостаточно сырья: {shortage_info}"
                manager_report.append((product.name, f"Недостаточно сырья: {shortage_info}"))

        # Сохраняем производственный план в базе данных
        ProductionPlan.objects.bulk_create(production_plans)

        # Генерируем документы
        temp_dir = tempfile.mkdtemp()
        department_files = generate_department_documents(production_plans, temp_dir)
        manager_report_file = generate_manager_report(manager_report, temp_dir)

        # Создаем zip-архив с документами
        zip_path = os.path.join(temp_dir, 'production_plan_documents.zip')
        with ZipFile(zip_path, 'w') as zip_file:
            for file_path in department_files:
                zip_file.write(file_path, os.path.basename(file_path))
            zip_file.write(manager_report_file, os.path.basename(manager_report_file))

        # Отправляем архив пользователю
        with open(zip_path, 'rb') as zip_file:
            response = HttpResponse(zip_file.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename=production_plan_documents.zip'
            return response

def generate_department_documents(production_plans, temp_dir):
    department_plans = defaultdict(list)
    for plan in production_plans:
        department_plans[plan.product.production_department.name].append(plan)

    file_paths = []
    for department, plans in department_plans.items():
        document = Document()
        document.add_heading(f'План производства для отдела {department}', 0)

        for plan in plans:
            document.add_heading(plan.product.name, level=1)
            document.add_paragraph(f'Запланированное количество: {plan.planned_quantity}')
            document.add_paragraph(f'Дата начала: {plan.order.start_date}')
            document.add_paragraph(f'Дата окончания: {plan.order.end_date}')

        file_path = os.path.join(temp_dir, f'{department}_production_plan.docx')
        document.save(file_path)
        file_paths.append(file_path)

    return file_paths

def generate_manager_report(manager_report, temp_dir):
    document = Document()
    document.add_heading('Отчет для менеджеров', 0)

    for product_name, issue in manager_report:
        document.add_heading(product_name, level=1)
        document.add_paragraph(issue)

    file_path = os.path.join(temp_dir, 'manager_report.docx')
    document.save(file_path)
    return file_path

class ProductionDepartmentsListView(ListView):
    model = ProductionDepartment
    template_name = 'farmer/production_departments_list.html'
    context_object_name = 'departments'

class ProductsListView(ListView):
    model = Product
    template_name = 'farmer/products_list.html'
    context_object_name = 'products'

class RawMaterialStockListView(ListView):
    model = RawMaterialStock
    template_name = 'farmer/raw_material_stock_list.html'
    context_object_name = 'raw_materials'

class StockListView(ListView):
    model = Stock
    template_name = 'farmer/stock_list.html'
    context_object_name = 'stocks'

class RecipesListView(ListView):
    model = Recipe
    template_name = 'farmer/recipes_list.html'
    context_object_name = 'recipes'

class ProductionPlansListView(ListView):
    model = ProductionPlan
    template_name = 'farmer/production_plans_list.html'
    context_object_name = 'plans'

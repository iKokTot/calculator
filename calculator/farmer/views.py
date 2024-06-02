import json
from datetime import datetime, timedelta
from itertools import groupby
from operator import attrgetter

from django.utils.dateformat import DateFormat
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
    orders = ManagementOrder.objects.filter(Order_id=order_id).select_related('product_code',
                                                                              'product_code__production_department')

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

                # Определяем текущую загруженность производства
                overlapping_orders = ProductionPlan.objects.filter(
                    product__production_department=production_department,
                    order__end_date__gte=order.start_date,
                    order__start_date__lte=order.end_date
                )

                current_load = 0
                for overlapping_order in overlapping_orders:
                    overlap_days = (min(overlapping_order.order.end_date, order.end_date) - max(
                        overlapping_order.order.start_date, order.start_date)).days
                    overlap_months = overlap_days / 30
                    current_load += overlapping_order.planned_quantity / overlap_months

                available_capacity = monthly_output - current_load
                if required_quantity > available_capacity * required_months:
                    delay = (required_quantity / available_capacity) - required_months
                    production_possibility[
                        product.name] = f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"
                else:
                    production_possibility[
                        product.name] = f"Можно произвести {required_quantity} единиц за {required_months:.2f} месяцев"
            else:
                shortage_info = ', '.join(
                    [f"{material}: недостает {amount} ед." for material, amount in shortages.items()])
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
        orders = ManagementOrder.objects.filter(Order_id=order_id).select_related('product_code',
                                                                                  'product_code__production_department')

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
        stock_dict = {stock.name: stock for stock in raw_materials_stock}

        for order in orders:
            product = order.product_code
            required_quantity = order.quantity
            recipes = Recipe.objects.filter(product=product)
            sufficient_resources = True
            shortages = {}

            for recipe in recipes:
                material_name = recipe.raw_material.name
                required_amount = recipe.required_quantity * required_quantity
                available_quantity = stock_dict[material_name].quantity

                if available_quantity < required_amount:
                    shortages[material_name] = required_amount - available_quantity
                    sufficient_resources = False
                else:
                    stock_dict[material_name].quantity -= required_amount

            if sufficient_resources:
                production_department = product.production_department
                production_time = (order.end_date - order.start_date).days
                monthly_output = production_department.average_output
                required_months = required_quantity / monthly_output

                if production_time < required_months * 30:
                    delay = (required_months * 30) - production_time
                    production_possibility[
                        product.name] = f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"
                    manager_report.append((product.name,
                                           f"Производственный отдел не сможет уложиться в сроки, просрочка составит {delay:.2f} дней"))
                else:
                    production_possibility[
                        product.name] = f"Можно произвести {required_quantity} единиц за {required_months:.2f} месяцев"
                    production_plans.append(
                        ProductionPlan(order=order, product=product, planned_quantity=required_quantity))
            else:
                shortage_info = ', '.join(
                    [f"{material}: недостает {amount} ед." for material, amount in shortages.items()])
                production_possibility[product.name] = f"Недостаточно сырья: {shortage_info}"
                manager_report.append((product.name, f"Недостаточно сырья: {shortage_info}"))

        # Обновляем количество сырья на складе
        for stock in stock_dict.values():
            stock.save()

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Допустим, у нас есть данные о производственных заказах
        orders = ManagementOrder.objects.all().select_related('product_code__production_department')

        # Группируем заказы по производственным отделам
        departments = ProductionDepartment.objects.all()
        load_data = []
        for department in departments:
            department_orders = []
            for order in orders:
                if order.product_code.production_department == department:
                    department_orders.append({
                        'order_id': order.Order_id,
                        'product': order.product_code.name,
                        'start_date': order.start_date.strftime('%Y-%m-%d'),
                        'end_date': order.end_date.strftime('%Y-%m-%d'),
                        'quantity': order.quantity,
                        'monthly_output': department.average_output
                    })
            load_data.append({
                'department': department.name,
                'load': department_orders
            })

        # Определяем временной интервал для оси X (1 месяц до текущей даты и 1 месяц после)
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        context['load_data'] = load_data
        context['start_date'] = start_date
        context['end_date'] = end_date
        return context

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plans = self.get_queryset().select_related('order', 'product').order_by('order__Order_id')
        grouped_plans = groupby(plans, key=attrgetter('order'))
        grouped_plans_list = [(order, list(plans)) for order, plans in grouped_plans]
        context['grouped_plans'] = grouped_plans_list
        return context

# models.py

from django.db import models

class ProductionDepartment(models.Model):  # Производственный отдел
    # Название отдела
    name = models.CharField(max_length=100)  # название
    # Тип продуктов, которые производит отдел
    product_type = models.CharField(max_length=100)  # тип продуктов
    # Среднее количество продукции, которое может произвести отдел
    average_output = models.IntegerField()  # среднее количество

    def __str__(self):
        return self.name

class Product(models.Model):  # Продукция
    # Название продукта
    name = models.CharField(max_length=100)  # название
    # Отдел производства, к которому принадлежит продукт
    production_department = models.ForeignKey(ProductionDepartment, on_delete=models.CASCADE)  # производственный отдел
    # Доступность продукта для производства
    is_active = models.BooleanField(default=True)  # активен

    def __str__(self):
        return self.name

class ManagementOrder(models.Model):   # Заявки от менеджеров
    # Код заказа
    Order_id = models.CharField(max_length=100)  # код продукции
    # Код продукции
    product_code = models.ForeignKey(Product, on_delete=models.CASCADE)  # продукт
    # Дата начала производства
    start_date = models.DateField()  # дата начала
    # Дата окончания производства
    end_date = models.DateField()  # дата конца
    # Запланированное количество продукции
    quantity = models.IntegerField()  # количество

    def __str__(self):
        return f"Order {self.Order_id} for {self.product_code.name}"



class Stock(models.Model):  # Остатки на складах
    # Название сырья
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
class RawMaterialStock(models.Model):  # Остатки на складах
    # Название сырья
    name = models.CharField(max_length=100)
    # Количество сырья на складе
    quantity = models.IntegerField()
    # Склад
    stok_id = models.ForeignKey(Stock, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name



class Recipe(models.Model):  # Рецепты
    # Продукт, для которого предназначен рецепт
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # продукт
    # Сырье, необходимое для производства продукта
    raw_material = models.ForeignKey(RawMaterialStock, on_delete=models.CASCADE)  # сырье
    # Необходимое количество сырья для производства продукта
    required_quantity = models.IntegerField()  # необходимое количество

    def __str__(self):
        return f"{self.product} - {self.raw_material}"

class ProductionPlan(models.Model):  # Производственный план
    # Заявка от менеджмента
    order = models.ForeignKey(ManagementOrder, on_delete=models.CASCADE)  # заявка
    # Продукт, который необходимо произвести
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # продукт
    # Планируемое количество продукта к производству
    planned_quantity = models.IntegerField()  # планируемое количество

    def __str__(self):
        return f"{self.order} - {self.product}"


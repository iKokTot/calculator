# forms.py
from django import forms
from .models import Product

class ProductionPlanForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label="Продукт")
    quantity = forms.IntegerField(min_value=1, label="Количество")
    start_date = forms.DateField(widget=forms.SelectDateWidget, label="Дата начала")
    end_date = forms.DateField(widget=forms.SelectDateWidget, label="Дата окончания")

# forms.py
from django import forms
from .models import Product
from django.contrib.auth.models import User
class ProductionPlanForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label="Продукт")
    quantity = forms.IntegerField(min_value=1, label="Количество")
    start_date = forms.DateField(widget=forms.SelectDateWidget, label="Дата начала")
    end_date = forms.DateField(widget=forms.SelectDateWidget, label="Дата окончания")

class UserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
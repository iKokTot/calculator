from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django import forms

class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

class LoginUser(LoginView):
    form_class = StyledAuthenticationForm
    template_name = 'users/login.html'
    extra_context = {'title': "Авторизация"}


class LogoutButtonView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect(reverse('users:login'))


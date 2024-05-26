from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views
from .views import LogoutButtonView

app_name = "users"

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', LogoutButtonView.as_view(), name='logout'),
]

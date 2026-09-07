from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('zadacha/sozdat/', views.sozdat_zadachu, name='sozdat_zadachu'),
    path('zadacha/<int:pk>/', views.detal_zadachi, name='detal_zadachi'),
    path('zadacha/<int:pk>/prinyat/', views.prinyat_zadachu, name='prinyat_zadachu'),
    path('zadacha/<int:pk>/nachat/', views.nachat_rabotu, name='nachat_rabotu'),
    path('zadacha/<int:pk>/na-proverku/', views.otpravit_na_proverku, name='otpravit_na_proverku'),
    path('zadacha/<int:pk>/proverit/', views.proverit_zadachu, name='proverit_zadachu'),
    path('zadacha/<int:pk>/zagruzit-fail/', views.zagruzit_fail, name='zagruzit_fail'),
    path('uvedomleniya/', views.uvedomleniya, name='uvedomleniya'),
]
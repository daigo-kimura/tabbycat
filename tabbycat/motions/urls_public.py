from django.urls import path

from . import views

urlpatterns = [
    path('', views.PublicMotionsView.as_view(), name='motions-public'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('api/closures/insert/', views.api_insert_closure, name='api_insert_closure'),
    path('api/closures/list/', views.api_list_closures, name='api_list_closures'),
    path('api/closures/update/<int:closure_id>/', views.api_update_closure, name='api_update_closure'),
    path('api/closures/delete/<int:closure_id>/', views.api_delete_closure, name='api_delete_closure'),
]

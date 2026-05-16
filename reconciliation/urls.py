from django.urls import path
from . import views

urlpatterns = [
    path('api/closures/insert/', views.api_insert_closure),
    path('api/closures/extract/', views.api_extract_closure),
    path('api/closures/list/', views.api_list_closures),
    path('api/closures/update/<int:closure_id>/', views.api_update_closure),
    path('api/closures/delete/<int:closure_id>/', views.api_delete_closure),

    path('api/departments/', views.api_list_departments),
    path('api/departments/create/', views.api_create_department),
    path('api/departments/update/<int:dept_id>/', views.api_update_department),
    path('api/departments/delete/<int:dept_id>/', views.api_delete_department),

    path('api/closures/extract-ai/', views.api_extract_closure_ai),
]

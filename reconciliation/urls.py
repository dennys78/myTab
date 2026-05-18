from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('api/auth/login/',   views.api_login),
    path('api/auth/logout/',  views.api_logout),
    path('api/auth/me/',      views.api_me),

    # Gestione utenti (admin)
    path('api/users/',                              views.api_users_list),
    path('api/users/create/',                       views.api_user_create),
    path('api/users/<int:user_id>/delete/',         views.api_user_delete),
    path('api/users/<int:user_id>/update/',         views.api_user_update),
    path('api/users/<int:user_id>/change-password/', views.api_user_change_password),

    # Chiusure
    path('api/closures/insert/',                    views.api_insert_closure),
    path('api/closures/extract/',                   views.api_extract_closure),
    path('api/closures/list/',                      views.api_list_closures),
    path('api/closures/update/<int:closure_id>/',   views.api_update_closure),
    path('api/closures/delete/<int:closure_id>/',   views.api_delete_closure),
    path('api/acquisition-drafts/',                 views.api_acquisition_drafts_list),
    path('api/acquisition-drafts/<int:draft_id>/extract-ai/', views.api_acquisition_draft_extract),

    # Reparti
    path('api/departments/',                        views.api_list_departments),
    path('api/departments/create/',                 views.api_create_department),
    path('api/departments/update/<int:dept_id>/',   views.api_update_department),
    path('api/departments/delete/<int:dept_id>/',   views.api_delete_department),

    # Versamenti
    path('api/versamenti/',                         views.api_versamenti_list),
    path('api/versamenti/create/',                  views.api_versamenti_create),
    path('api/versamenti/<int:vers_id>/delete/',    views.api_versamenti_delete),
    path('api/versamenti/<int:vers_id>/update/',    views.api_versamenti_update),

    # Fondo Cassa
    path('api/fondo-cassa/',                        views.api_fondo_cassa_list),
    path('api/fondo-cassa/create/',                 views.api_fondo_cassa_create),
    path('api/fondo-cassa/<int:mov_id>/delete/',    views.api_fondo_cassa_delete),
    path('api/fondo-cassa/<int:mov_id>/update/',    views.api_fondo_cassa_update),

    # AI + Impostazioni
    path('api/closures/extract-ai/',                views.api_extract_closure_ai),
    path('api/settings/',                           views.api_get_settings),
    path('api/settings/save/',                      views.api_save_settings),
    path('api/settings/telegram/reset-sessions/',   views.api_reset_telegram_sessions),
]

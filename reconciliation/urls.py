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
    path('api/closures/<int:closure_id>/images/upload/', views.api_closure_images_upload),
    path('api/closure-images/<int:image_id>/view/', views.api_closure_image_view),
    path('api/closure-images/<int:image_id>/delete/', views.api_closure_image_delete),
    path('api/acquisition-drafts/',                 views.api_acquisition_drafts_list),
    path('api/acquisition-drafts/mark-seen/',     views.api_acquisition_drafts_mark_seen),
    path('api/acquisition-drafts/<int:draft_id>/extract-ai/', views.api_acquisition_draft_extract),
    path('api/acquisition-drafts/<int:draft_id>/cancel/', views.api_acquisition_draft_cancel),
    path('api/acquisition-draft-images/<int:image_id>/view/', views.api_acquisition_draft_image_view),

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

    # Movimenti cassa (entrate/uscite)
    path('api/movimenti-cassa/',                         views.api_movimenti_cassa_list),
    path('api/movimenti-cassa/create/',                  views.api_movimenti_cassa_create),
    path('api/movimenti-cassa/<int:mov_id>/delete/',     views.api_movimenti_cassa_delete),
    path('api/movimenti-cassa/<int:mov_id>/update/',     views.api_movimenti_cassa_update),

    # Fondo Cassa
    path('api/fondo-cassa/',                        views.api_fondo_cassa_list),
    path('api/fondo-cassa/create/',                 views.api_fondo_cassa_create),
    path('api/fondo-cassa/<int:mov_id>/delete/',    views.api_fondo_cassa_delete),
    path('api/fondo-cassa/<int:mov_id>/update/',    views.api_fondo_cassa_update),

    path('api/companies/',                           views.api_companies_list),
    path('api/companies/switch/',                    views.api_companies_switch),
    path('api/companies/create/',                    views.api_companies_create),
    path('api/companies/<int:company_id>/update/',   views.api_companies_update),

    # AI + Impostazioni
    path('api/closures/extract-ai/',                views.api_extract_closure_ai),
    path('api/acquisition/ai-provider/',            views.api_acquisition_ai_provider),
    path('api/push/vapid-public-key/',              views.api_push_vapid_public_key),
    path('api/push/subscribe/',                     views.api_push_subscribe),
    path('api/push/unsubscribe/',                   views.api_push_unsubscribe),
    path('api/push/status/',                        views.api_push_status),
    path('api/settings/',                           views.api_get_settings),
    path('api/settings/save/',                      views.api_save_settings),
    path('api/settings/telegram/reset-sessions/',   views.api_reset_telegram_sessions),
    path('api/settings/telegram/restart-bot/',      views.api_restart_telegram_bot),
    path('api/settings/images/purge/',              views.api_purge_images),
    path('api/settings/company/purge/',             views.api_purge_company_data),
]

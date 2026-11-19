from django.urls import path
from . import views
from . import ricevute_views
from . import gratta_views
from . import giacenze_views
from . import n8n_tabacchi_views
from . import tabacchi_views
from . import tabauno_portal

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
    path('api/closures/import-tabauno/',            views.api_import_tabauno_closure),
    path('api/tabauno/status/',                     tabauno_portal.api_tabauno_status),
    path('api/tabauno/requests/',                   tabauno_portal.api_tabauno_requests),
    path('api/tabauno/requests/<int:request_id>/',  tabauno_portal.api_tabauno_request_detail),
    path('api/tabauno/agent/token/',                tabauno_portal.api_tabauno_rotate_token),
    path('api/tabauno/agent/next/',                 tabauno_portal.api_tabauno_agent_next),
    path('api/tabauno/agent/result/<int:request_id>/', tabauno_portal.api_tabauno_agent_result),
    path('api/tabauno/agent/ordine-logista/<int:request_id>/', tabauno_portal.api_tabauno_agent_ordine_logista),
    path('api/gratta/preordini/', gratta_views.api_gratta_preordini),
    path('api/gratta/preordini/da-richiesta/<int:request_id>/', gratta_views.api_gratta_preordine_da_richiesta),
    path('api/gratta/preordini/<int:preordine_id>/', gratta_views.api_gratta_preordine_detail),
    path('api/gratta/preordini/<int:preordine_id>/invia/', gratta_views.api_gratta_preordine_invia),
    path('api/gratta/preordini/<int:preordine_id>/json/', gratta_views.api_gratta_preordine_json),
    path('api/gratta/preordini/<int:preordine_id>/stato/', gratta_views.api_gratta_preordine_stato),
    path('api/tabacchi/preordini/', tabacchi_views.api_tabacchi_preordini),
    path('api/tabacchi/preordini/da-richiesta/<int:request_id>/', tabacchi_views.api_tabacchi_preordine_da_richiesta),
    path('api/tabacchi/preordini/<int:preordine_id>/', tabacchi_views.api_tabacchi_preordine_detail),
    path('api/tabacchi/preordini/<int:preordine_id>/csv/', tabacchi_views.api_tabacchi_preordine_csv),
    path('api/tabacchi/preordini/<int:preordine_id>/logista/', tabacchi_views.api_tabacchi_preordine_logista),
    path('api/tabacchi/preordini/<int:preordine_id>/deposita-tabauno/', tabacchi_views.api_tabacchi_preordine_deposita_tabauno),
    path('api/tabacchi/logista/invia/', tabacchi_views.api_tabacchi_logista_invia),
    path('api/tabacchi/logista/job/<int:job_id>/', tabacchi_views.api_tabacchi_logista_job),
    path('api/tabacchi/logista/job/<int:job_id>/foto/', tabacchi_views.api_tabacchi_logista_job_foto),
    path('api/n8n/tabacchi/logista/avvia/', n8n_tabacchi_views.api_n8n_tabacchi_logista_avvia),
    path('api/n8n/tabacchi/logista/job/<int:job_id>/', n8n_tabacchi_views.api_n8n_tabacchi_logista_job),
    path('api/statistiche/giacenze/lettura/', giacenze_views.api_giacenze_lettura),
    path('api/statistiche/giacenze/', giacenze_views.api_giacenze_analisi),
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
    path('api/acquisition-drafts/<int:draft_id>/extract-status/', views.api_acquisition_draft_extract_status),
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

    # Estratto conto cassa (chiusure + versamenti + movimenti)
    path('api/cassa-estratto-conto/',                    views.api_cassa_estratto_conto),

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
    path('api/push/test/',                          views.api_push_test),
    path('api/push/forward-last-closure/',           views.api_push_forward_last_closure),
    path('api/settings/',                           views.api_get_settings),
    path('api/settings/save/',                      views.api_save_settings),
    path('api/settings/telegram/reset-sessions/',   views.api_reset_telegram_sessions),
    path('api/settings/telegram/restart-bot/',      views.api_restart_telegram_bot),
    path('api/settings/images/purge/',              views.api_purge_images),
    path('api/settings/company/purge/',             views.api_purge_company_data),

    # Ricevute
    path('api/ricevute/clienti/',                           ricevute_views.api_clienti),
    path('api/ricevute/clienti/<int:cliente_id>/',            ricevute_views.api_cliente_detail),
    path('api/ricevute/valori-bollati/',                      ricevute_views.api_valori_bollati),
    path('api/ricevute/valori-bollati/<int:valore_id>/',      ricevute_views.api_valore_bollato_detail),
    path('api/ricevute/emesse/',                              ricevute_views.api_ricevute_emesse),
    path('api/ricevute/emesse/<int:ricevuta_id>/',            ricevute_views.api_ricevuta_emessa_detail),
    path('api/ricevute/emesse/<int:ricevuta_id>/pdf/',        ricevute_views.api_ricevuta_pdf),
    path('api/ricevute/emesse/<int:ricevuta_id>/send-email/', ricevute_views.api_ricevuta_send_email),
]

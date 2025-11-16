from django.urls import path, include
from django.views.generic.base import RedirectView
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Vistas principales y de registro de usuario
    path("", views.index, name="index"),
    path("signup/", views.signup, name="signup"),
    path('register/', views.signup, name='register'), # Alias para signup
    path('verify_code/', views.verify_code, name='verify_code'),
    path('user_index/', views.user_index, name='user_index'),


    # Vistas de autenticación de Django (login, logout)
    path('login/', views.CustomLoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Vistas de recuperación de contraseña
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/forgot_password.html',
        email_template_name='registration/password_reset_email.txt',
        html_email_template_name='registration/password_reset_email.html'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(template_name='registration/reset_password.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    path('settings/', views.settings, name='settings'),
    path('change_password/', views.settings, name='change_password'),
    path('delete_account/', views.delete_account, name='delete_account'),


    
    path('ajax/ciudades/<int:region_id>/', views.get_ciudades, name='get_ciudades'),
    # --- Rutas comentadas para funcionalidades futuras o de empresa ---
    path("register_emp/", views.register_emp, name="register_emp"),
    path("validate/", views.Validate, name="validate"),
    path('profile/', views.Profile, name='profile'),
    path('create-cv/', views.create_cv, name='create_cv'),
    path('download-cv-pdf/', views.download_cv_pdf, name='download_cv_pdf'),
    path('download-s3-cv/<int:cv_id>/', views.download_s3_cv, name='download_s3_cv'),
    path('save-cv/', views.save_cv, name='save_cv'),
    path('delete-cv/<int:cv_id>/', views.delete_cv, name='delete_cv'),
    path('cv/<int:cv_id>/edit/', views.edit_cv, name='edit_cv'),
    path('cv/<int:cv_id>/edit-meta/', views.edit_cv_meta, name='edit_cv_meta'),

    path('applications/', views.postulaciones, name='postulaciones'),
    path('perfiles-profesionales/', views.perfiles_profesionales, name='perfiles_profesionales'),
    path('offers/', views.job_offers, name='job_offers'),
		path('offers/<int:id_oferta>',views.job_details,name='job_details'),
    path('company/<int:company_id>/', views.company_profile, name='company_profile'),
    # path('company/users/', views.company_users, name='company_users'),
    # path('company/invitations/', views.company_invitations, name='company_invitations'),
    path('company_index/', views.company_index, name='company_index'),
    path('company/accept-invitation/<str:token>/', views.accept_company_invitation, name='accept_company_invitation'),

    # --- Rutas para Páginas Estáticas ---
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('about-us/', views.about_us, name='about_us'),
    path('contact-us/', views.contact_us, name='contact_us'),
]
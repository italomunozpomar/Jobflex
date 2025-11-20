from multiprocessing.managers import BaseManager
import re
import os
import json
import unicodedata
from urllib.parse import urlparse
import uuid
import boto3
from django.conf import settings as django_settings
import locale
from datetime import datetime, date, timedelta
import calendar
 # Added here
from django.utils import timezone
from datetime import datetime, date, timedelta # Added here
import random
from django.db.models import Count, Q, F
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash, logout
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model # Use get_user_model
from django.core.paginator import Paginator
User = get_user_model() # Define User globally
from django.db import transaction # Add this line
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse # Import reverse here
from django.core.signing import BadSignature
from playwright.sync_api import sync_playwright
from django import forms
from django.views.decorators.http import require_POST

# ... (rest of the imports)

# 1. Importar los formularios y modelos necesarios y limpios
from .forms import SignUpForm, VerificationForm, CandidatoForm, CVCandidatoForm, CompletarPerfilForm, InvitationForm, SetInvitationPasswordForm, CVSubidoForm, OfertaLaboralForm
from .models import CompanyInvitationToken, TipoUsuario, RegistroUsuarios, Candidato, EmpresaUsuario, Empresa, RolesEmpresa, CVCandidato, CVCreado, CVSubido, DatosPersonalesCV, ObjetivoProfesionalCV, EducacionCV, ExperienciaLaboralCV, CertificacionesCV, HabilidadCV, IdiomaCV, ProyectosCV, ReferenciasCV, VoluntariadoCV, Postulacion, Entrevista, ModoOnline, ModoPresencial, TipoNotificacion, Notificaciones, NotificacionCandidato, NotificacionEmpresa, Region, Ciudad, RubroIndustria

# --- 2FA Form ---
class TwoFactorForm(forms.Form):
    code = forms.CharField(label="Código de Verificación", max_length=6, required=True)
from django.http import HttpRequest, JsonResponse, HttpResponse

def send_verification_email(user_email, code, subject_template, html_template_path):
    """
    A helper function to send verification-style emails.
    """
    mail_subject = subject_template.format(code=code)
    message = render_to_string(html_template_path, {'code': code})
    email = EmailMessage(mail_subject, message, to=[user_email])
    email.content_subtype = "html" # Ensure it sends as HTML
    email.send()

@transaction.atomic # Usar una transacción para asegurar la integridad de los datos
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            # 1. Crear el User de Django
            user = form.save(commit=False)
            user.is_active = False  # Activar después de la verificación por correo
            user.save()

            # 2. Obtener o crear el TipoUsuario 'candidato'
            tipo_usuario_candidato, created = TipoUsuario.objects.using('jflex_db').get_or_create(nombre_user='candidato')

            # 3. Crear el RegistroUsuarios en la base de datos jflex_db
            RegistroUsuarios.objects.using('jflex_db').create(
                id_registro=user,
                nombres=form.cleaned_data['nombres'],
                apellidos=form.cleaned_data['apellidos'],
                email=form.cleaned_data['email'],
                tipo_usuario=tipo_usuario_candidato
            )

            # 4. Crear el perfil de Candidato en la base de datos jflex_db
            Candidato.objects.using('jflex_db').create(
                id_candidato=user,
                rut_candidato='', # Dejar vacío por ahora
                fecha_nacimiento='1900-01-01', # Valor por defecto
                telefono='' # Dejar vacío por ahora
            )

            # 5. Enviar correo de verificación (lógica existente)
            code = str(random.randint(100000, 999999))
            request.session['verification_code'] = code
            request.session['user_pk_for_verification'] = user.pk

            send_verification_email(
                form.cleaned_data.get('email'),
                code,
                'Tu código de activación para JobFlex es {code}',
                'registration/code_email.html'
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'redirect_url': reverse('verify_code')})
            return redirect('verify_code')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = SignUpForm()
    return render(request, 'registration/register.html', {'form': form})


def verify_code(request):
    if request.method == 'POST':
        form = VerificationForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']
            stored_code = request.session.get('verification_code')
            user_pk = request.session.get('user_pk_for_verification')

            if entered_code == stored_code:
                try:
                    user = User.objects.get(pk=user_pk)
                    user.is_active = True
                    user.save()
                    # Usar el backend por defecto de Django para el login
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    
                    del request.session['verification_code']
                    del request.session['user_pk_for_verification']

                    messages.success(request, "¡Tu cuenta ha sido activada con éxito!")
                    return redirect('user_index')

                except User.DoesNotExist:
                    form.add_error(None, "Usuario no encontrado.")
            else:
                form.add_error('code', "El código introducido no es correcto.")
    else:
        form = VerificationForm()
    return render(request, 'registration/enter_code.html', {'form': form})


def verify_2fa(request):
    user_pk = request.session.get('2fa_user_pk')
    if not user_pk:
        messages.error(request, "Sesión inválida para verificación 2FA. Por favor, inicia sesión de nuevo.")
        return redirect('login')

    if request.method == 'POST':
        form = TwoFactorForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']
            stored_code = request.session.get('2fa_code')
            
            expiry_str = request.session.get('2fa_code_expiry')
            if not expiry_str or timezone.now() > datetime.fromisoformat(expiry_str):
                messages.error(request, "El código de verificación ha expirado. Por favor, intenta iniciar sesión de nuevo.")
                for key in ['2fa_user_pk', '2fa_code', '2fa_code_expiry']:
                    request.session.pop(key, None)
                return redirect('login')

            if entered_code == stored_code:
                try:
                    user = User.objects.get(pk=user_pk)
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    
                    for key in ['2fa_user_pk', '2fa_code', '2fa_code_expiry']:
                        request.session.pop(key, None)
                            
                    response = redirect('user_index')
                    if request.POST.get('remember_device'):
                        response.set_signed_cookie('trusted_device', user.username, salt='jobflex-2fa-salt', max_age=30*24*60*60)
                    
                    return response
                except User.DoesNotExist:
                    messages.error(request, "Usuario no encontrado durante la verificación 2FA.")
                    return redirect('login')
            else:
                form.add_error(None, "El código introducido no es correcto.")
    else:
        form = TwoFactorForm()
        
    return render(request, 'registration/verify_2fa.html', {'form': form})


@login_required
def toggle_2fa(request):
    """
    Initiates the process of enabling or disabling 2FA by sending a verification code.
    """
    try:
        user_profile = request.user.registrousuarios
        action = 'enable' if not user_profile.autenticacion_dos_factores_activa else 'disable'

        code = str(random.randint(100000, 999999))
        request.session['2fa_change_code'] = code
        request.session['2fa_change_action'] = action
        request.session['2fa_change_expiry'] = (timezone.now() + timedelta(minutes=10)).isoformat()

        send_verification_email(
            request.user.email,
            code,
            'Tu Código de Seguridad de JobFlex',
            'registration/2fa_code_email.html'
        )
        messages.info(request, "Te hemos enviado un código al correo para confirmar el cambio.")
        return redirect('verify_2fa_change')

    except RegistroUsuarios.DoesNotExist:
        messages.error(request, "No se encontró tu perfil de registro.")
        return redirect('settings')

def verify_2fa_change(request):
    """
    Verifies the code to finalize enabling or disabling 2FA.
    """
    if request.method == 'POST':
        form = TwoFactorForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']
            stored_code = request.session.get('2fa_change_code')
            action = request.session.get('2fa_change_action')
            expiry_str = request.session.get('2fa_change_expiry')

            if not all([stored_code, action, expiry_str]):
                messages.error(request, "La sesión ha expirado o es inválida. Por favor, inténtalo de nuevo.")
                return redirect('settings')
            
            if timezone.now() > datetime.fromisoformat(expiry_str):
                messages.error(request, "El código ha expirado. Por favor, inténtalo de nuevo.")
                return redirect('settings')

            if entered_code == stored_code:
                try:
                    user_profile = request.user.registrousuarios
                    if action == 'enable':
                        user_profile.autenticacion_dos_factores_activa = True
                        messages.success(request, "¡Has activado la autenticación de dos factores!")
                    elif action == 'disable':
                        user_profile.autenticacion_dos_factores_activa = False
                        messages.success(request, "Has desactivado la autenticación de dos factores.")
                    
                    user_profile.save(using='jflex_db')

                    for key in ['2fa_change_code', '2fa_change_action', '2fa_change_expiry']:
                        if key in request.session:
                            del request.session[key]
                    
                    return redirect('settings')
                except RegistroUsuarios.DoesNotExist:
                    messages.error(request, "No se encontró tu perfil de registro.")
                    return redirect('settings')
            else:
                form.add_error(None, "El código no es correcto.")
    else:
        form = TwoFactorForm()

    return render(request, 'registration/verify_2fa_change.html', {'form': form})

def index(req):
    if req.user.is_authenticated:
        return redirect('user_index')
    
    all_regions = Region.objects.all()
    all_modalidades = Modalidad.objects.all()
    all_jornadas = Jornada.objects.all()
    context = {
        'all_regions': all_regions,
        'all_modalidades': all_modalidades,
        'all_jornadas': all_jornadas,
    }
    return render(req, 'index.html', context)

def upload_to_s3(file, bucket_name, object_key):
    s3 = boto3.client(
        's3',
        aws_access_key_id=django_settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=django_settings.AWS_SECRET_ACCESS_KEY,
    )
    if hasattr(file, 'seek'):
        file.seek(0)
    extra_args = {'ContentType': file.content_type}
    s3.upload_fileobj(file, bucket_name, object_key, ExtraArgs=extra_args)
    # La URL del objeto no cambia en su formato base
    file_url = f"https://{bucket_name}.s3.{django_settings.AWS_S3_REGION_NAME}.amazonaws.com/{object_key}"
    return file_url

def sanitize_company_folder_name(name: str) -> str:
    if not name:
        return "Empresa"
    if not isinstance(name, str):
        if hasattr(name, 'name'):
            name = name.name  # e.g., InMemoryUploadedFile
        else:
            try:
                name = name.decode('utf-8')  # type: ignore[attr-defined]
            except AttributeError:
                name = str(name)
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    cleaned = re.sub(r'[^A-Za-z0-9]+', ' ', normalized).strip()
    sanitized = re.sub(r'\s+', '_', cleaned)
    return sanitized or "Empresa"

def build_company_asset_key(company_obj, asset_folder: str, filename: str) -> str:
    base_folder = sanitize_company_folder_name(
        getattr(company_obj, 'nombre_comercial', '') or 
        getattr(company_obj, 'razon_social', '') or 
        getattr(company_obj, 'rut_empresa', 'Empresa')
    )
    return f"Empresas/{base_folder}/{asset_folder}/{filename}"

#helper, also used on postulaciones
def application_status(qs,dt_format='%d-%m-%Y'):
    processed_applications = []
    app:Postulacion
    for app in qs:
        display_status = ""
        status_class = ""
        status_icon = ""

        if app.estado_postulacion == 'rechazada':
            display_status = "Rechazado"
            status_class = "bg-red-100 text-red-800"
            status_icon = "fa-ban" # Signo de denegado
        elif app.estado_postulacion == 'aceptada':
            display_status = "Aceptado"
            status_class = "bg-green-100 text-green-800"
            status_icon = "fa-check-circle" # Checkmark
        elif app.estado_postulacion == 'entrevista':
            display_status = "Agendado"
            status_class = "bg-purple-100 text-purple-800"
            status_icon = "fa-calendar-alt" # Calendar icon
        elif app.estado_postulacion == 'en proceso':
            display_status = "En Revisión"
            status_class = "bg-yellow-100 text-yellow-800"
            status_icon = "fa-clock" # Reloj
        elif app.estado_postulacion == 'enviada':
            if app.cv_visto:
                display_status = "CV Visto"
                status_class = "bg-green-100 text-green-800" # Verde para CV visto
                status_icon = "fa-eye" # Ojo
            else:
                display_status = "Enviado"
                status_class = "bg-blue-100 text-blue-800" # Azul para Enviado
                status_icon = "fa-paper-plane" # Icono de enviado
        else:
            display_status = "Desconocido"
            status_class = "bg-gray-100 text-gray-800"
            status_icon = "fa-question-circle"

        processed_applications.append({
            'id': app.id_postulacion,
            'job_title': app.oferta.titulo_puesto,
            'company_name': app.oferta.empresa.nombre_comercial,
            'date_applied': app.fecha_postulacion.strftime(dt_format),
            'status': display_status,
            'status_class': status_class,
            'status_icon': status_icon,
            'job_jornada': app.oferta.jornada.tipo_jornada if app.oferta.jornada else 'N/A',
            'job_modalidad': app.oferta.modalidad.tipo_modalidad if app.oferta.modalidad else 'N/A',
            'cv':app.cv_postulado,
        })
    return processed_applications

@login_required
def user_index(request):
    try:
        registro = RegistroUsuarios.objects.get(id_registro=request.user)
        
        if registro.tipo_usuario and registro.tipo_usuario.nombre_user == 'candidato':
            candidato = request.user.candidato_profile
            show_modal = not all([candidato.rut_candidato, candidato.fecha_nacimiento, candidato.telefono, candidato.ciudad_id])
            
            completar_perfil_form = CompletarPerfilForm(instance=candidato)
            cv_subido_form = CVSubidoForm()

            if request.method == 'POST':
                if 'submit_perfil' in request.POST:
                    completar_perfil_form = CompletarPerfilForm(request.POST, instance=candidato)
                    if completar_perfil_form.is_valid():
                        completar_perfil_form.save()
                        messages.success(request, "¡Gracias por completar tu perfil!")
                        return redirect('user_index')
                
                elif 'submit_cv' in request.POST:
                    cv_subido_form = CVSubidoForm(request.POST, request.FILES)
                    if cv_subido_form.is_valid():
                        file = cv_subido_form.cleaned_data['cv_file']
                        
                        username = request.user.username
                        filename = f"{uuid.uuid4().hex[:8]}_{file.name}"
                        s3_key = f"CVs/{username}/{filename}"

                        file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)

                        cv_candidato = CVCandidato.objects.create(
                            candidato=candidato,
                            nombre_cv=cv_subido_form.cleaned_data['nombre_cv'],
                            cargo_asociado=cv_subido_form.cleaned_data['cargo_asociado'],
                            tipo_cv='subido'
                        )
                        
                        CVSubido.objects.create(
                            id_cv_subido=cv_candidato,
                            ruta_archivo=file_url
                        )
                        
                        messages.success(request, "Tu CV ha sido subido y organizado exitosamente en S3.")
                        return redirect('user_index')
            
            # --- Dynamic Stats ---
            total_applications_count = Postulacion.objects.using('jflex_db').filter(candidato=candidato).count()
            total_cvs_count = CVCandidato.objects.using('jflex_db').filter(candidato=candidato).count()

            # --- Smarter "Ofertas Destacadas" Carousel ---
            recommended_offers = []
            latest_cv = CVCandidato.objects.using('jflex_db').filter(candidato=candidato).order_by('-id_cv_user').first()
            
            offers_query = OfertaLaboral.objects.using('jflex_db').filter(estado='activa').select_related('empresa', 'jornada', 'modalidad', 'ciudad')

            if latest_cv and latest_cv.cargo_asociado:
                keywords = latest_cv.cargo_asociado.split()
                q_objects = Q()
                for keyword in keywords:
                    q_objects |= (Q(titulo_puesto__icontains=keyword) | Q(descripcion_puesto__icontains=keyword))
                
                if candidato.ciudad:
                    specific_offers_qs = offers_query.filter(q_objects, ciudad=candidato.ciudad).order_by('-fecha_publicacion')[:5]
                    if specific_offers_qs.exists():
                        offers_query = specific_offers_qs
                    elif candidato.ciudad.region:
                        offers_query = offers_query.filter(q_objects, ciudad__region=candidato.ciudad.region).order_by('-fecha_publicacion')[:5]
                    else:
                        offers_query = offers_query.filter(q_objects).order_by('-fecha_publicacion')[:5]
                else:
                    offers_query = offers_query.filter(q_objects).order_by('-fecha_publicacion')[:5]
            
            if not offers_query.exists():
                offers_query = OfertaLaboral.objects.using('jflex_db').filter(estado='activa').select_related('empresa', 'jornada', 'modalidad', 'ciudad').order_by('-fecha_publicacion')[:5]

            for offer in offers_query[:5]:
                recommended_offers.append({
                    'id': offer.id_oferta,
                    'title': offer.titulo_puesto,
                    'company': offer.empresa.nombre_comercial,
                    'location': offer.ciudad.nombre if offer.ciudad else 'N/A',
                    'modality': offer.modalidad.tipo_modalidad if offer.modalidad else 'N/A',
                    'jornada': offer.jornada.tipo_jornada if offer.jornada else 'N/A',
                    'company_logo': offer.empresa.imagen_perfil
                })

            # --- Profile Completion ---
            profile_fields = [
                ('RUT', candidato.rut_candidato),
                ('Fecha de Nacimiento', candidato.fecha_nacimiento),
                ('Teléfono', candidato.telefono),
                ('URL de LinkedIn', candidato.linkedin_url),
                ('Ciudad', candidato.ciudad),
            ]
            
            has_cv = CVCandidato.objects.using('jflex_db').filter(candidato=candidato).exists()
            is_2fa_active = request.user.registrousuarios.autenticacion_dos_factores_activa

            completed_fields_count = 0
            missing_profile_fields_text = []
            
            for field_name, field_value in profile_fields:
                if field_value and str(field_value).strip() and field_value != date(1900, 1, 1):
                    completed_fields_count += 1
                else:
                    missing_profile_fields_text.append(f"Completa tu {field_name}")

            if has_cv:
                completed_fields_count += 1

            if is_2fa_active:
                completed_fields_count += 1

            total_profile_fields = len(profile_fields) + 2 # Now 5 fields + CV + 2FA
            profile_completion_percentage = int((completed_fields_count / total_profile_fields) * 100) if total_profile_fields > 0 else 0

            # --- Fetch Recent Applications ---
            recent_applications_qs = Postulacion.objects.using('jflex_db').filter(
                candidato=candidato
            ).select_related(
                'oferta__empresa', 'oferta__jornada', 'oferta__modalidad'
            ).order_by('-fecha_postulacion')[:3]

            processed_applications = []
            for app in recent_applications_qs:
                display_status, status_class, status_icon = "", "", ""
                if app.estado_postulacion == 'rechazada':
                    display_status, status_class, status_icon = "Rechazado", "bg-red-100 text-red-800", "fa-ban"
                elif app.estado_postulacion == 'aceptada':
                    display_status, status_class, status_icon = "Aceptado", "bg-green-100 text-green-800", "fa-check-circle"
                elif app.estado_postulacion == 'entrevista':
                    display_status, status_class, status_icon = "Agendado", "bg-purple-100 text-purple-800", "fa-calendar-alt"
                elif app.estado_postulacion == 'en proceso':
                    display_status, status_class, status_icon = "En Revisión", "bg-yellow-100 text-yellow-800", "fa-clock"
                elif app.estado_postulacion in ['enviada', 'Recibida']:
                    if app.cv_visto:
                        display_status, status_class, status_icon = "CV Visto", "bg-green-100 text-green-800", "fa-eye"
                    else:
                        display_status, status_class, status_icon = "Enviado", "bg-blue-100 text-blue-800", "fa-paper-plane"
                else:
                    display_status, status_class, status_icon = "Desconocido", "bg-gray-100 text-gray-800", "fa-question-circle"
                
                processed_applications.append({
                    'id': app.id_postulacion,
                    'job_title': app.oferta.titulo_puesto,
                    'company_name': app.oferta.empresa.nombre_comercial,
                    'date_applied': app.fecha_postulacion.strftime('%d-%m-%Y'),
                    'status': display_status,
                    'status_class': status_class,
                    'status_icon': status_icon,
                    'job_jornada': app.oferta.jornada.tipo_jornada if app.oferta.jornada else 'N/A',
                    'job_modalidad': app.oferta.modalidad.tipo_modalidad if app.oferta.modalidad else 'N/A',
                })
            apps = application_status(recent_applications_qs)
            # for app in recent_applications_qs:
            #     display_status = ""
            #     status_class = ""
            #     status_icon = ""

            #     if app.estado_postulacion == 'rechazada':
            #         display_status = "Rechazado"
            #         status_class = "bg-red-100 text-red-800"
            #         status_icon = "fa-ban" # Signo de denegado
            #     elif app.estado_postulacion == 'aceptada':
            #         display_status = "Aceptado"
            #         status_class = "bg-green-100 text-green-800"
            #         status_icon = "fa-check-circle" # Checkmark
            #     elif app.estado_postulacion == 'entrevista':
            #         display_status = "Agendado"
            #         status_class = "bg-purple-100 text-purple-800"
            #         status_icon = "fa-calendar-alt" # Calendar icon
            #     elif app.estado_postulacion == 'en proceso':
            #         display_status = "En Revisión"
            #         status_class = "bg-yellow-100 text-yellow-800"
            #         status_icon = "fa-clock" # Reloj
            #     elif app.estado_postulacion == 'enviada':
            #         if app.cv_visto:
            #             display_status = "CV Visto"
            #             status_class = "bg-green-100 text-green-800" # Verde para CV visto
            #             status_icon = "fa-eye" # Ojo
            #         else:
            #             display_status = "Enviado"
            #             status_class = "bg-blue-100 text-blue-800" # Azul para Enviado
            #             status_icon = "fa-paper-plane" # Icono de enviado
            #     else:
            #         display_status = "Desconocido"
            #         status_class = "bg-gray-100 text-gray-800"
            #         status_icon = "fa-question-circle"

            #     processed_applications.append({
            #         'id': app.id_postulacion,
            #         'job_title': app.oferta.titulo_puesto,
            #         'company_name': app.oferta.empresa.nombre_comercial,
            #         'date_applied': app.fecha_postulacion.strftime('%d-%m-%Y'),
            #         'status': display_status,
            #         'status_class': status_class,
            #         'status_icon': status_icon,
            #         'job_jornada': app.oferta.jornada.tipo_jornada if app.oferta.jornada else 'N/A',
            #         'job_modalidad': app.oferta.modalidad.tipo_modalidad if app.oferta.modalidad else 'N/A',
            #     })

            # --- Fetch User's CVs for the new section ---
            cv_list = []
            cvs_qs = CVCandidato.objects.using('jflex_db').filter(candidato=candidato).select_related('cvcreado', 'cvsubido').order_by('-id_cv_user')[:3]

            for cv in cvs_qs:
                update_date = None
                if cv.tipo_cv == 'creado' and hasattr(cv, 'cvcreado'):
                    update_date = cv.cvcreado.ultima_actualizacion
                elif cv.tipo_cv == 'subido' and hasattr(cv, 'cvsubido'):
                    update_date = cv.cvsubido.fecha_subido

                cv_list.append({
                    'id_cv_user': cv.id_cv_user,
                    'nombre_cv': cv.nombre_cv,
                    'cargo_asociado': cv.cargo_asociado,
                    'tipo_cv': cv.tipo_cv,
                    'ultima_actualizacion': update_date.strftime('%d-%m-%Y') if update_date else 'N/A',
                })

            context = {
                'show_modal': show_modal, 
                'form': completar_perfil_form,
                'cv_subido_form': cv_subido_form,
                'all_regions': Region.objects.all(),
                'recent_applications': apps, # Add processed applications to context
                'recent_applications': processed_applications,
                'total_applications_count': total_applications_count,
                'total_cvs_count': total_cvs_count,
                'recommended_offers': recommended_offers,
                'profile_completion_percentage': profile_completion_percentage,
                'missing_profile_fields_text': missing_profile_fields_text,
                'has_cv': has_cv,
                'is_2fa_active': is_2fa_active,
                'cv_list': cv_list,
            }
            return render(request, 'user/user_index.html', context)

        elif registro.tipo_usuario and registro.tipo_usuario.nombre_user == 'empresa':
            return redirect('company_index')
        else:
            messages.warning(request, "Tu usuario no tiene un tipo asignado. Contacta a soporte.")
            return redirect('index')

    except (RegistroUsuarios.DoesNotExist, Candidato.DoesNotExist):
        messages.error(request, "No se encontró un perfil para tu usuario.")
        return redirect('index')

@login_required
def toggle_missy_view(request):
    """
    Toggles the 'show_missy' flag in the user's session and redirects back to the user index.
    """
    if 'show_missy' not in request.session:
        request.session['show_missy'] = True  # Default to showing Missy if not set
    else:
        request.session['show_missy'] = not request.session['show_missy']
    request.session.modified = True # Ensure the session is saved
    messages.info(request, "¡Cambio de vista realizado!") # Optional: give feedback to the user
    return redirect('user_index')


from django.core.serializers.json import DjangoJSONEncoder


@login_required
def Profile(request):
    try:
        candidato = Candidato.objects.get(id_candidato=request.user)
    except Candidato.DoesNotExist:
        messages.error(request, "Perfil de candidato no encontrado.")
        return redirect('user_index')

    # Initialize forms outside the if/else block to ensure they are always defined
    form = CandidatoForm(instance=candidato)
    # Add a prefix to the upload form to prevent ID collisions in the template
    cv_subido_form = CVSubidoForm(prefix="upload")

    if request.method == 'POST':
        # Diferenciar entre los formularios
        if 'submit_profile' in request.POST:
            form = CandidatoForm(request.POST, instance=candidato)
            if form.is_valid():
                form.save()
                messages.success(request, "¡Tu perfil ha sido actualizado con éxito!")
                return redirect('profile')
        
        elif 'submit_cv' in request.POST:
            # Use the same prefix when processing the POST data
            cv_subido_form = CVSubidoForm(request.POST, request.FILES, prefix="upload")
            if cv_subido_form.is_valid():
                file = cv_subido_form.cleaned_data['cv_file']
                username = request.user.username
                filename = f"{uuid.uuid4().hex[:8]}_{file.name}"
                s3_key = f"CVs/{username}/{filename}"

                file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)

                cv_candidato = CVCandidato.objects.create(
                    candidato=candidato,
                    nombre_cv=cv_subido_form.cleaned_data['nombre_cv'],
                    cargo_asociado=cv_subido_form.cleaned_data['cargo_asociado'],
                    tipo_cv='subido'
                )
                
                CVSubido.objects.create(
                    id_cv_subido=cv_candidato,
                    ruta_archivo=file_url
                )
                
                messages.success(request, "Tu CV ha sido subido exitosamente.")
                return redirect('profile')

    # --- Lógica de serialización de CVs para la vista previa ---
    from django.db.models.functions import Coalesce

    # Order CVs by the most recent date from either CVCreado or CVSubido
    cvs_qs = CVCandidato.objects.filter(candidato=candidato)        .select_related('cvcreado', 'cvsubido')        .annotate(
            latest_date=Coalesce('cvcreado__ultima_actualizacion', 'cvsubido__fecha_subido')
        )        .order_by('-latest_date')[:3] # Slice to get the latest 3
    cv_list = []
    for cv in cvs_qs:
        cv_item = {
            'id_cv_user': cv.id_cv_user,
            'nombre_cv': cv.nombre_cv,
            'cargo_asociado': cv.cargo_asociado,
            'tipo_cv': cv.tipo_cv,
            'cv_data_json': '{}',
            'url': None,
            'ultima_actualizacion': None
        }

        if cv.tipo_cv == 'creado' and hasattr(cv, 'cvcreado'):
            cv_creado = cv.cvcreado
            cv_item['ultima_actualizacion'] = cv_creado.ultima_actualizacion
            
            def safe_get(obj, attr, default=''):
                return getattr(obj, attr, default) if obj else default

            personal_data_obj = getattr(cv_creado, 'datospersonalescv', None)
            objective_obj = getattr(cv_creado, 'objetivoprofesionalcv', None)

            cv_data = {
                'personalData': {
                    'firstName': safe_get(personal_data_obj, 'primer_nombre'),
                    'secondName': safe_get(personal_data_obj, 'segundo_nombre'),
                    'lastName': safe_get(personal_data_obj, 'apellido_paterno'),
                    'motherLastName': safe_get(personal_data_obj, 'apellido_materno'),
                    'title': safe_get(personal_data_obj, 'titulo_profesional'),
                    'email': safe_get(personal_data_obj, 'email'),
                    'phone': safe_get(personal_data_obj, 'telefono'),
                    'linkedin_link': safe_get(personal_data_obj, 'linkedin')
                },
                'objective': safe_get(objective_obj, 'texto_objetivo'),
                'experience': [
                    {
                        'position': exp.cargo_puesto,
                        'company': exp.empresa,
                        'location': exp.ubicacion,
                        'start_month': exp.fecha_inicio.strftime('%B') if exp.fecha_inicio else '',
                        'start_year': exp.fecha_inicio.year if exp.fecha_inicio else '',
                        'end_month': exp.fecha_termino.strftime('%B') if exp.fecha_termino else '',
                        'end_year': exp.fecha_termino.year if exp.fecha_termino else '',
                        'current_job': exp.trabajo_actual,
                        'is_internship': exp.practica,
                        'total_hours': exp.horas_practica,
                        'description': exp.descripcion_cargo
                    } for exp in ExperienciaLaboralCV.objects.filter(cv_creado=cv_creado)
                ],
                'education': [
                    {
                        'institution': edu.institucion,
                        'degree': edu.carrera_titulo_nivel,
                        'start_year': edu.fecha_inicio.year if edu.fecha_inicio else '',
                        'end_year': edu.fecha_termino.year if edu.fecha_termino else '',
                        'currently_studying': edu.cursando,
                        'notes': edu.comentarios
                    } for edu in EducacionCV.objects.filter(cv_creado=cv_creado)
                ],
                'skills': {
                    'hard': [h.texto_habilidad for h in HabilidadCV.objects.filter(cv_creado=cv_creado, tipo_habilidad='hard')],
                    'soft': [h.texto_habilidad for h in HabilidadCV.objects.filter(cv_creado=cv_creado, tipo_habilidad='soft')]
                },
                'languages': [
                    {
                        'language': lang.nombre_idioma,
                        'level': lang.nivel_idioma
                    } for lang in IdiomaCV.objects.filter(cv_creado=cv_creado)
                ],
                'certifications': [
                    {
                        'cert_name': cert.nombre_certificacion,
                        'issuer': cert.entidad_emisora,
                        'year': cert.fecha_obtencion.year if cert.fecha_obtencion else ''
                    } for cert in CertificacionesCV.objects.filter(cv_creado=cv_creado)
                ],
                'projects': [
                    {
                        'project_name': proj.nombre_proyecto,
                        'period': proj.fecha_proyecto,
                        'role': proj.rol_participacion,
                        'description': proj.descripcion_proyecto,
                        'link': proj.url_proyecto
                    } for proj in ProyectosCV.objects.filter(cv_creado=cv_creado)
                ],
                'volunteering': [
                    {
                        'organization': vol.nombre_organizacion,
                        'role': vol.puesto_rol,
                        'description': vol.descripcion_actividades,
                        'city': vol.ciudad,
                        'country': vol.pais,
                        'region': vol.region_estado_provincia,
                        'start_date': vol.fecha_inicio.isoformat() if vol.fecha_inicio else '',
                        'end_date': vol.fecha_termino.isoformat() if vol.fecha_termino else '',
                        'current': vol.actualmente_activo
                    } for vol in VoluntariadoCV.objects.filter(cv_creado=cv_creado)
                ],
                'references': [
                    {
                        'name': ref.nombre_referente,
                        'position': ref.cargo_referente,
                        'phone': ref.telefono,
                        'email': ref.email,
                        'linkedin_url': ref.url_linkedin
                    } for ref in ReferenciasCV.objects.filter(cv_creado=cv_creado)
                ]
            }
            cv_item['cv_data_json'] = json.dumps(cv_data, cls=DjangoJSONEncoder)
        
        elif cv.tipo_cv == 'subido' and hasattr(cv, 'cvsubido'):
            cv_subido = cv.cvsubido
            cv_item['url'] = cv_subido.ruta_archivo
            cv_item['ultima_actualizacion'] = cv_subido.fecha_subido

        cv_list.append(cv_item)

    # Calcular edad
    today = date.today()
    age = today.year - candidato.fecha_nacimiento.year - ((today.month, today.day) < (candidato.fecha_nacimiento.month, candidato.fecha_nacimiento.day))

    # --- Metrics for Charts ---
    today_local = timezone.localdate() # Get today's date in the current timezone
    
    # Weekly Submissions (last 7 days, including today)
    weekly_submission_labels = []
    weekly_submission_data = []
    
    spanish_day_map = {
        'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue',
        'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
    }

    for i in range(7):
        current_day = today_local - timedelta(days=i)
        day_name = current_day.strftime('%a') # e.g., "Mon"
        display_day_name = spanish_day_map.get(day_name, day_name)
        
        applications_count = Postulacion.objects.using('jflex_db').filter(
            candidato=candidato,
            fecha_postulacion__date=current_day
        ).count()
        
        weekly_submission_labels.insert(0, display_day_name) # Insert at the beginning to reverse order
        weekly_submission_data.insert(0, applications_count) # Insert at the beginning to reverse order

    # CV Usage
    cv_usage_counts = Postulacion.objects.using('jflex_db').filter(candidato=candidato)        .values('cv_postulado__nombre_cv')        .annotate(count=Count('cv_postulado'))        .order_by('-count')

    cv_usage_labels = [item['cv_postulado__nombre_cv'] for item in cv_usage_counts]
    cv_usage_data = [item['count'] for item in cv_usage_counts]
    
    if not cv_usage_labels:
        cv_usage_labels = ['No hay CVs utilizados']
        cv_usage_data = [1] # A small placeholder value for the chart to render

    # Lógica para determinar si se muestra el modal
    show_profile_modal = not candidato.rut_candidato or not candidato.telefono

    context = {
        'form': form,
        'candidato': candidato,
        'age': age,
        'show_profile_modal': show_profile_modal,
        'cv_list': cv_list,
        'cv_subido_form': cv_subido_form,
        'weekly_submission_labels': json.dumps(weekly_submission_labels),
        'weekly_submission_data': json.dumps(weekly_submission_data),
        'cv_usage_labels': json.dumps(cv_usage_labels),
        'cv_usage_data': json.dumps(cv_usage_data),
    }
    return render(request, 'user/profile.html', context)

from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def update_availability(request):
    try:
        candidato = Candidato.objects.get(id_candidato=request.user)
        data = json.loads(request.body)
        status = data.get('status')

        if status == 'available':
            candidato.disponible = True
        elif status == 'unavailable':
            candidato.disponible = False
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid status provided.'}, status=400)
        
        candidato.save()
        return JsonResponse({'status': 'success', 'message': 'Availability updated successfully.'})

    except Candidato.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Candidate profile not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, '¡Tu contraseña ha sido actualizada y has iniciado sesión correctamente!')
        return redirect('user_index')

def social_login_cancelled(request):
    messages.error(request, 'El registro con Google fue cancelado. Por favor, inténtalo de nuevo.')
    return redirect('signup')

from .models import Empresa
from sii.models import EmpresaSII

def Validate(request):
    if request.method == 'POST':
        rut = request.POST.get('rut', '').strip()
        if not rut:
            return render(request, 'company/validation.html', {'error': 'Por favor, ingresa un RUT.'})

        try:
            # Normalizamos el RUT a formato sin puntos y con guión, ej: 76123456-7
            rut_completo = rut.replace('.', '').upper()
            if '-' not in rut_completo:
                rut_completo = f'{rut_completo[:-1]}-{rut_completo[-1]}'

            empresa_sii = EmpresaSII.objects.using('sii').get(rut_completo=rut_completo)
            
            # Comprobar si la empresa ya está registrada en JobFlex
            if Empresa.objects.using('jflex_db').filter(rut_empresa=rut_completo).exists():
                return render(request, 'company/validation.html', {'error': 'Esta empresa ya ha sido registrada en JobFlex.'})

            # Si se encuentra en el SII y no está en JobFlex, mostrar para confirmar
            return render(request, 'company/validation.html', {'company_found': empresa_sii})

        except EmpresaSII.DoesNotExist:
            # Si no se encuentra en la base de datos del SII
            return render(request, 'company/validation.html', {'error': 'El RUT no fue encontrado en los registros del SII.'})
        except Exception as e:
            # Para cualquier otro error inesperado
            return render(request, 'company/validation.html', {'error': f'Ha ocurrido un error inesperado: {e}'})

    return render(request, 'company/validation.html')

from .forms import SignUpForm, VerificationForm, CandidatoForm, EmpresaSignUpForm
from .models import RegistroUsuarios, TipoUsuario, Candidato, Empresa, EmpresaUsuario, RolesEmpresa

@transaction.atomic
def register_emp(request):
    if request.method == 'POST':
        form = EmpresaSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Activar la cuenta directamente
            user.save()

            tipo_usuario_empresa, _ = TipoUsuario.objects.using('jflex_db').get_or_create(nombre_user='empresa')

            RegistroUsuarios.objects.using('jflex_db').create(
                id_registro=user,
                nombres=form.cleaned_data['nombres'],
                apellidos=form.cleaned_data['apellidos'],
                email=form.cleaned_data['email'],
                tipo_usuario=tipo_usuario_empresa
            )

            rut_empresa = form.cleaned_data['rut']
            empresa_sii = EmpresaSII.objects.using('sii').get(rut_completo=rut_empresa)

            nueva_empresa = Empresa.objects.using('jflex_db').create(
                rut_empresa=rut_empresa,
                razon_social=empresa_sii.razon_social,
                nombre_comercial=empresa_sii.razon_social, # Placeholder, se puede cambiar en el onboarding
                resumen_empresa='',
                telefono=''
            )

            rol_representante, _ = RolesEmpresa.objects.using('jflex_db').get_or_create(nombre_rol='Representante')

            EmpresaUsuario.objects.using('jflex_db').create(
                id_empresa_user=user,
                empresa=nueva_empresa,
                rol=rol_representante
            )

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"¡Bienvenido a JobFlex! Tu cuenta para {nueva_empresa.nombre_comercial} ha sido creada.")
            return redirect('company_index')
        else:
            # Si el form no es válido, hay que recuperar el rut para mostrar la info de la empresa
            rut = request.POST.get('rut')
            empresa_sii = EmpresaSII.objects.using('sii').get(rut_completo=rut)
            return render(request, 'company/register_emp.html', {'form': form, 'emp_validation': empresa_sii})

    else: # GET
        rut = request.GET.get('rut')
        if not rut:
            messages.error(request, "No se proporcionó un RUT de empresa.")
            return redirect('validate')

        try:
            empresa_sii = EmpresaSII.objects.using('sii').get(rut_completo=rut)
            if Empresa.objects.using('jflex_db').filter(rut_empresa=rut).exists():
                messages.error(request, "Esta empresa ya ha sido registrada.")
                return redirect('validate')

            form = EmpresaSignUpForm(initial={'rut': rut})
            return render(request, 'company/register_emp.html', {'form': form, 'emp_validation': empresa_sii})
        
        except EmpresaSII.DoesNotExist:
            messages.error(request, "El RUT proporcionado no es válido.")
            return redirect('validate')

def get_ciudades(request, region_id):
    try:
        # This logic is for the search form, which we don't want to break.
        # The form now excludes "Cualquier Región", so this part of the if will not be hit by the modal.
        cualquier_region = Region.objects.get(nombre='Cualquier Región')
        if region_id == cualquier_region.id_region:
            ciudades = list(Ciudad.objects.filter(region=cualquier_region, nombre='Cualquier comuna').values('id_ciudad', 'nombre').order_by('nombre'))
        else:
            # Exclude "Cualquier comuna" for all other regions.
            ciudades = list(Ciudad.objects.filter(region_id=region_id).exclude(nombre='Cualquier comuna').values('id_ciudad', 'nombre').order_by('nombre'))
    except Region.DoesNotExist:
        # Also exclude here in the fallback.
        ciudades = list(Ciudad.objects.filter(region_id=region_id).exclude(nombre='Cualquier comuna').values('id_ciudad', 'nombre').order_by('nombre'))
    
    return JsonResponse(ciudades, safe=False)

import uuid # Add this import at the top

# ... (rest of the imports)

from .forms import SignUpForm, VerificationForm, CandidatoForm, CVCandidatoForm, CompletarPerfilForm, InvitationForm, EmpresaDataForm
from .models import *
from django.http import JsonResponse
import json

# ... (rest of the views)

from django.utils import timezone
@login_required
def company_index(request):
    # 1. Get the current user's company and role
    company = None # Initialize company to None
    user_role = None # Initialize user_role to None

    try:
        empresa_usuario = EmpresaUsuario.objects.select_related('empresa', 'rol').get(id_empresa_user=request.user)
        company = empresa_usuario.empresa
        user_role = empresa_usuario.rol.nombre_rol
    except EmpresaUsuario.DoesNotExist:
        messages.error(request, "No estás asociado a ninguna empresa.")
        return redirect('index') # Redirect to a safe page, or show an error

    is_admin = (user_role == 'Representante' or user_role == 'Administrador')

    # Handle POST requests for user management
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_job_offer' and is_admin:
            job_offer_form = OfertaLaboralForm(request.POST)
            if job_offer_form.is_valid():
                nueva_categoria_str = job_offer_form.cleaned_data.get('nueva_categoria')
                categoria_obj = job_offer_form.cleaned_data.get('categoria')

                if nueva_categoria_str:
                    categoria_obj, created = Categoria.objects.get_or_create(
                        tipo_categoria__iexact=nueva_categoria_str,
                        defaults={'tipo_categoria': nueva_categoria_str}
                    )
                
                # Remove fields that are not part of the OfertaLaboral model
                job_offer_form.cleaned_data.pop('nueva_categoria', None)
                job_offer_form.cleaned_data.pop('categoria', None)
                duracion = job_offer_form.cleaned_data.pop('duracion_oferta')
                fecha_personalizada = job_offer_form.cleaned_data.pop('fecha_cierre_personalizada')

                new_offer = job_offer_form.save(commit=False)
                new_offer.empresa = company
                new_offer.categoria = categoria_obj

                if duracion == 'custom':
                    new_offer.fecha_cierre = fecha_personalizada
                else:
                    new_offer.fecha_cierre = timezone.now() + timedelta(days=int(duracion))
                
                print(f"DEBUG: Creating offer. Selected duration: {duracion}, Calculated fecha_cierre: {new_offer.fecha_cierre}, Fecha Publicacion: {new_offer.fecha_publicacion}")
                new_offer.save()
                messages.success(request, "La oferta de trabajo ha sido creada exitosamente.")
                return redirect('company_index')
            else:
                messages.error(request, "Error al crear la oferta. Por favor, revisa el formulario.")

        elif action == 'edit_job_offer' and is_admin:
            offer_id = request.POST.get('offer_id')
            try:
                # Get the offer to edit
                offer_to_edit = OfertaLaboral.objects.get(pk=offer_id, empresa=company)
                job_offer_form = OfertaLaboralForm(request.POST, instance=offer_to_edit)
                
                if job_offer_form.is_valid():
                    nueva_categoria_str = job_offer_form.cleaned_data.get('nueva_categoria')
                    categoria_obj = job_offer_form.cleaned_data.get('categoria')

                    if nueva_categoria_str:
                        categoria_obj, created = Categoria.objects.get_or_create(
                            tipo_categoria__iexact=nueva_categoria_str,
                            defaults={'tipo_categoria': nueva_categoria_str}
                        )
                    
                    # Remove fields that are not part of the OfertaLaboral model
                    job_offer_form.cleaned_data.pop('nueva_categoria', None)
                    job_offer_form.cleaned_data.pop('categoria', None)
                    duracion = job_offer_form.cleaned_data.pop('duracion_oferta')
                    fecha_personalizada = job_offer_form.cleaned_data.pop('fecha_cierre_personalizada')

                    updated_offer = job_offer_form.save(commit=False)
                    updated_offer.categoria = categoria_obj

                    if duracion == 'custom':
                        updated_offer.fecha_cierre = fecha_personalizada
                    else:
                        updated_offer.fecha_cierre = timezone.now() + timedelta(days=int(duracion))
                    
                    print(f"DEBUG: Updating offer {offer_id}. Selected duration: {duracion}, Calculated fecha_cierre: {updated_offer.fecha_cierre}")
                    updated_offer.save()
                    messages.success(request, "La oferta de trabajo ha sido actualizada exitosamente.")
                    return redirect('company_index')
                else:
                    messages.error(request, "Error al editar la oferta. Por favor, revisa el formulario.")
            except OfertaLaboral.DoesNotExist:
                messages.error(request, "La oferta que intentas editar no existe o no tienes permiso.")
                return redirect('company_index')

        elif action == 'archive_offer' and is_admin:
            offer_id = request.POST.get('offer_id')
            try:
                offer = OfertaLaboral.objects.get(pk=offer_id, empresa=company)
                offer.estado = 'cerrada'
                offer.save()
                messages.success(request, f"La oferta '{offer.titulo_puesto}' ha sido archivada.")
            except OfertaLaboral.DoesNotExist:
                messages.error(request, "La oferta que intentas archivar no existe o no tienes permiso.")
            return redirect('company_index')

        elif action == 'delete_offer' and is_admin:
            offer_id = request.POST.get('offer_id')
            try:
                offer = OfertaLaboral.objects.get(pk=offer_id, empresa=company)
                title = offer.titulo_puesto
                offer.delete()
                messages.success(request, f"La oferta '{title}' ha sido eliminada permanentemente.")
            except OfertaLaboral.DoesNotExist:
                messages.error(request, "La oferta que intentas eliminar no existe o no tienes permiso.")
            return redirect('company_index')

        elif action == 'update_company_data' and is_admin:
            company_data_form = EmpresaDataForm(request.POST, request.FILES, instance=company)
            if company_data_form.is_valid():
                # Save the form instance without committing to get the updated company object
                # but without saving the image fields yet.
                updated_company = company_data_form.save(commit=False)

                # Handle image uploads to S3
                if 'imagen_perfil' in request.FILES:
                    file = request.FILES['imagen_perfil']
                    file_ext = os.path.splitext(file.name)[1].lower()
                    filename = f"logo_{uuid.uuid4().hex[:8]}{file_ext}"
                    s3_key = build_company_asset_key(updated_company, 'Logo', filename)
                    file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)
                    updated_company.imagen_perfil = file_url
                # If no new file is uploaded, the existing value from 'instance=company' will be retained.
                
                if 'imagen_portada' in request.FILES:
                    file = request.FILES['imagen_portada']
                    file_ext = os.path.splitext(file.name)[1].lower()
                    filename = f"banner_{uuid.uuid4().hex[:8]}{file_ext}"
                    s3_key = build_company_asset_key(updated_company, 'Banner', filename)
                    file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)
                    updated_company.imagen_portada = file_url
                # If no new file is uploaded, the existing value from 'instance=company' will be retained.
                
                # Now save the updated company object to the database
                updated_company.save()
                messages.success(request, "Los datos de la empresa han sido actualizados.")
                company = updated_company # Update the company object in the view's scope
                return redirect('company_index')
            else:
                print("DEBUG: EmpresaDataForm errors ->", company_data_form.errors)
                messages.error(request, "Error al actualizar los datos. Por favor, revisa el formulario.")

        elif action == 'invite_user' and is_admin: # Only admins can invite
            form = InvitationForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                role = form.cleaned_data['role'] # This is a RolesEmpresa object

                try:
                    invited_user = User.objects.get(email=email)
                    if EmpresaUsuario.objects.filter(empresa=company, id_empresa_user=invited_user).exists():
                        messages.warning(request, f"El usuario {email} ya es parte de esta empresa.")
                    else:
                        EmpresaUsuario.objects.create(
                            id_empresa_user=invited_user,
                            empresa=company,
                            rol=role
                        )
                        messages.success(request, f"El usuario existente {email} ha sido añadido a la empresa como {role.nombre_rol}.")
                except User.DoesNotExist:
                    username = f"temp_{uuid.uuid4().hex[:10]}"
                    new_user = User.objects.create_user(username=username, email=email, password="temporarypassword123")
                    new_user.is_active = False
                    new_user.first_name = "Invitado"
                    new_user.last_name = "Pendiente"
                    new_user.save()

                    EmpresaUsuario.objects.create(
                        id_empresa_user=new_user,
                        empresa=company,
                        rol=role
                    )
                    
                    invitation_token = uuid.uuid4().hex
                    expires_at = timezone.now() + timedelta(days=1)

                    CompanyInvitationToken.objects.using('jflex_db').create(
                        user_id=new_user.id,
                        company=company,
                        token=invitation_token,
                        expires_at=expires_at
                    )

                    invitation_link = request.build_absolute_uri(
                        reverse('accept_company_invitation', kwargs={'token': invitation_token})
                    )

                    mail_subject = f'Invitación para unirte a {company.nombre_comercial} en JobFlex'
                    message = render_to_string('company/invitation_email.html', {
                        'company_name': company.nombre_comercial,
                        'invitation_link': invitation_link,
                        'invited_email': email,
                    })
                    to_email = email
                    email_message = EmailMessage(mail_subject, message, to=[to_email])
                    email_message.send()

                    messages.success(request, f"Se ha enviado una invitación a {email} para unirse a la empresa como {role.nombre_rol}.")
                
                return redirect('company_index')
            else:
                messages.error(request, "Error al invitar usuario. Por favor, revisa los datos.")
        
        elif action == 'edit_user' and is_admin:
            member_id = request.POST.get('member_id')
            new_role_id = request.POST.get('role')
            try:
                member_to_edit = EmpresaUsuario.objects.get(pk=member_id, empresa=company)
                new_role = RolesEmpresa.objects.get(pk=new_role_id)
                member_to_edit.rol = new_role
                member_to_edit.save()
                messages.success(request, f"Rol de {member_to_edit.id_empresa_user.email} actualizado a {new_role.nombre_rol}.")
            except (EmpresaUsuario.DoesNotExist, RolesEmpresa.DoesNotExist):
                messages.error(request, "Error al editar el usuario o rol no válido.")
            return redirect('company_index')

        elif action == 'delete_user' and is_admin:
            member_id = request.POST.get('member_id')
            try:
                member_to_delete = EmpresaUsuario.objects.get(pk=member_id, empresa=company)
                if (member_to_delete.rol.nombre_rol == 'Representante' or member_to_delete.rol.nombre_rol == 'Administrador'):
                    admin_count = EmpresaUsuario.objects.filter(empresa=company, rol__nombre_rol__in=['Representante', 'Administrador']).count()
                    if admin_count <= 1:
                        messages.error(request, "No puedes eliminar al último administrador/representante de la empresa.")
                        return redirect('company_index')

                email_deleted = member_to_delete.id_empresa_user.email
                member_to_delete.delete()
                messages.success(request, f"Usuario {email_deleted} eliminado de la empresa.")
            except EmpresaUsuario.DoesNotExist:
                messages.error(request, "Error al eliminar usuario. No encontrado.")
            return redirect('company_index')

    # For GET requests or after POST handling, prepare context
    # At this point, 'company' is guaranteed to be defined from the initial try-except block,
    # or potentially updated by a successful POST request.

    # Explicitly check for and clear problematic default filenames just before context creation
    # This needs to happen AFTER any potential POST updates to 'company'
    if company.imagen_perfil and ('codelco_default640x360.png' in company.imagen_perfil or 'logo_color.png' in company.imagen_perfil):
        company.imagen_perfil = ""
    if company.imagen_portada and ('codelco_default640x360.png' in company.imagen_portada or 'logo_color.png' in company.imagen_portada):
        company.imagen_portada = ""

    logo_value = company.imagen_perfil
    banner_value = company.imagen_portada

    def coerce_to_url(value):
        if not value:
            return ""
        if isinstance(value, str):
            return value
        if hasattr(value, 'url'):
            return getattr(value, 'url', '') or ""
        if hasattr(value, 'name'):
            return getattr(value, 'name', '') or ""
        try:
            return value.decode('utf-8')  # type: ignore[attr-defined]
        except AttributeError:
            return str(value)

    logo_url = coerce_to_url(logo_value)
    banner_url = coerce_to_url(banner_value)

    if logo_url and not urlparse(logo_url).scheme:
        logo_url = ""
    if banner_url and not urlparse(banner_url).scheme:
        banner_url = ""

    empresa_usuarios_qs = EmpresaUsuario.objects.using('jflex_db').filter(empresa=company).select_related('rol')
    
    user_ids = [eu.id_empresa_user_id for eu in empresa_usuarios_qs]
    users_from_default = User.objects.using('default').filter(pk__in=user_ids)
    user_map = {user.pk: user for user in users_from_default}

    members_for_template = []
    for eu in empresa_usuarios_qs:
        user_obj = user_map.get(eu.id_empresa_user_id)
        if user_obj:
            members_for_template.append({
                'pk': eu.pk,
                'user_full_name': user_obj.get_full_name(),
                'user_email': user_obj.email,
                'role': eu.rol,
                'role_display': eu.rol.nombre_rol,
            })
    
    members_for_template.sort(key=lambda x: x['user_email'])

    invitation_form = InvitationForm()
    company_data_form = EmpresaDataForm(instance=company, prefix="modal")
    job_offer_form = OfertaLaboralForm()
    
    # Get only the categories that are actually used by the company's offers for the filter dropdown
    used_category_ids = OfertaLaboral.objects.filter(empresa=company).values_list('categoria_id', flat=True).distinct()
    categorias_for_filter = Categoria.objects.filter(id_categoria__in=used_category_ids)

    # Build the offers queryset with filters
    all_offers = OfertaLaboral.objects.filter(empresa=company)

    q_filter = request.GET.get('q', None)
    categoria_filter = request.GET.get('categoria', None)
    estado_filter = request.GET.get('estado', None)

    if q_filter:
        all_offers = all_offers.filter(titulo_puesto__icontains=q_filter)
    if categoria_filter:
        all_offers = all_offers.filter(categoria_id=categoria_filter)
    if estado_filter:
        all_offers = all_offers.filter(estado=estado_filter)

    all_offers = all_offers.select_related('categoria', 'jornada', 'modalidad').annotate(
        candidate_count=Count('postulacion')
    ).order_by('-fecha_publicacion')

    # Pre-process offers for duplication
    for offer in all_offers:
        # Calculate duration for duplication
        if offer.fecha_cierre and offer.fecha_publicacion:
            duration_days = (offer.fecha_cierre - offer.fecha_publicacion).days
            if duration_days == 7:
                offer.calculated_duration = '7'
            elif duration_days == 14:
                offer.calculated_duration = '14'
            elif duration_days == 21:
                offer.calculated_duration = '21'
            elif duration_days == 30:
                offer.calculated_duration = '30'
            else:
                offer.calculated_duration = 'custom'
        else:
            offer.calculated_duration = '' # Default to empty if dates are missing

        try:
            habilidades_list = json.loads(offer.habilidades_clave)
            offer.habilidades_str = ",".join([item['value'] for item in habilidades_list])
        except (json.JSONDecodeError, TypeError):
            offer.habilidades_str = ""
        try:
            beneficios_list = json.loads(offer.beneficios)
            offer.beneficios_str = ",".join([item['value'] for item in beneficios_list])
        except (json.JSONDecodeError, TypeError):
            offer.beneficios_str = ""

    # Dashboard Metrics
    # Note: These metrics will now reflect the filtered offer list.
    # If they should always show totals, the base query should be used.
    # For now, reflecting the filter is acceptable.
    active_jobs_count = all_offers.filter(estado='activa').count()
    new_applicants_count = Postulacion.objects.filter(
        oferta__empresa=company, 
        fecha_postulacion__gte=timezone.now() - timedelta(days=7)
    ).count()
    total_users_count = len(members_for_template)

    # Get upcoming interviews for the list on the right
    upcoming_interviews_qs = Entrevista.objects.filter(
        postulacion__oferta__empresa=company,
        fecha_entrevista__gte=timezone.now().date()
    ).select_related(
        'postulacion__candidato',
        'postulacion__oferta',
        'modoonline',
        'modopresencial'
    ).order_by('fecha_entrevista', 'hora_entrevista')[:5] # Limit to next 5

    interview_candidate_user_ids = [interview.postulacion.candidato.id_candidato_id for interview in upcoming_interviews_qs]
    interview_users_from_default = User.objects.using('default').filter(pk__in=interview_candidate_user_ids)
    interview_user_map = {user.pk: user for user in interview_users_from_default}

    upcoming_interviews_list = []
    for interview in upcoming_interviews_qs:
        candidate_user = interview_user_map.get(interview.postulacion.candidato.id_candidato_id)
        if candidate_user:
            details = {
                'candidate_name': candidate_user.get_full_name(),
                'job_title': interview.postulacion.oferta.titulo_puesto,
                'date': interview.fecha_entrevista,
                'time': interview.hora_entrevista,
                'modality': interview.modalidad,
                'url': None,
                'address': None,
            }
            if interview.modalidad == 'Online' and hasattr(interview, 'modoonline'):
                details['url'] = interview.modoonline.url_reunion
            elif interview.modalidad == 'Presencial' and hasattr(interview, 'modopresencial'):
                details['address'] = interview.modopresencial.direccion
            
            upcoming_interviews_list.append(details)

    # --- Calendar Logic ---
    try:
        current_year = int(request.GET.get('year', timezone.now().year))
        current_month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        current_year = timezone.now().year
        current_month = timezone.now().month

    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(current_year, current_month)
    
    # Fetch all interviews for the given month
    interviews_for_month = Entrevista.objects.filter(
        postulacion__oferta__empresa=company,
        fecha_entrevista__year=current_year,
        fecha_entrevista__month=current_month
    ).select_related('postulacion__candidato')

    # Get user details for the candidates
    calendar_candidate_ids = [i.postulacion.candidato.id_candidato_id for i in interviews_for_month]
    calendar_users = User.objects.using('default').filter(pk__in=calendar_candidate_ids)
    calendar_user_map = {user.pk: user for user in calendar_users}

    interviews_by_day = {}
    for interview in interviews_for_month:
        day = interview.fecha_entrevista.day
        candidate_user = calendar_user_map.get(interview.postulacion.candidato.id_candidato_id)
        if candidate_user:
            if day not in interviews_by_day:
                interviews_by_day[day] = []
            interviews_by_day[day].append({
                'candidate_name': candidate_user.get_full_name(),
                'time': interview.hora_entrevista.strftime('%H:%M')
            })

    # Prepare calendar data for the template
    calendar_grid = []
    today = timezone.now().date()
    for week in month_days:
        week_row = []
        for day_date in week:
            week_row.append({
                'day': day_date.day,
                'is_today': day_date == today,
                'is_current_month': day_date.month == current_month,
                'interviews': interviews_by_day.get(day_date.day, [])
            })
        calendar_grid.append(week_row)

    # Navigation context
    first_day_of_month = date(current_year, current_month, 1)
    prev_month_date = first_day_of_month - timedelta(days=1)
    next_month_date = first_day_of_month + timedelta(days=32) # Go to next month
    
    calendar_context = {
        'grid': calendar_grid,
        'current_month_name': first_day_of_month.strftime('%B %Y').capitalize(),
        'prev_month': {'year': prev_month_date.year, 'month': prev_month_date.month},
        'next_month': {'year': next_month_date.year, 'month': next_month_date.month},
    }

    # Manually serialize rubros to ensure it's a JSON array string
    all_rubros_qs = RubroIndustria.objects.all()
    rubros_list = list(all_rubros_qs.values('pk', 'nombre_rubro'))
    all_rubros_json = json.dumps(rubros_list)

    # --- Dashboard Feeds (New) ---
    company_user_pks = EmpresaUsuario.objects.filter(empresa=company).values_list('id_empresa_user_id', flat=True)
    recent_activities = Notificaciones.objects.filter(
        usuario_destino_id__in=company_user_pks
    ).select_related('tipo_notificacion').order_by('-fecha_envio')[:5]
    
    recent_applicants_qs = Postulacion.objects.filter(
        oferta__empresa=company
    ).select_related('candidato', 'oferta').order_by('-fecha_postulacion')[:5]
    
    applicant_user_ids = [p.candidato.id_candidato_id for p in recent_applicants_qs]
    applicant_users = User.objects.using('default').filter(pk__in=applicant_user_ids)
    applicant_user_map = {user.pk: user.get_full_name() for user in applicant_users}

    recent_applicants = []
    for p in recent_applicants_qs:
        recent_applicants.append({
            'full_name': applicant_user_map.get(p.candidato.id_candidato_id, 'Candidato Desconocido'),
            'job_title': p.oferta.titulo_puesto,
            'date': p.fecha_postulacion,
            'offer_id': p.oferta.id_oferta
        })
    # --- End Dashboard Feeds ---

    context = {
        'company': company,
        'company_logo_url': logo_url,
        'company_banner_url': banner_url,
        'is_admin': is_admin,
        'members': members_for_template,
        'invitation_form': invitation_form,
        'company_data_form': company_data_form,
        'job_offer_form': job_offer_form,
        'all_categorias': categorias_for_filter,
        'all_offers': all_offers,
        'user_role': user_role,
        'all_regions': Region.objects.all(),
        'all_rubros_json': all_rubros_json,
        'active_jobs_count': active_jobs_count,
        'new_applicants_count': new_applicants_count,
        'total_users_count': total_users_count,
        'calendar_context': calendar_context,
        'upcoming_interviews': upcoming_interviews_list,
        'upcoming_interviews_count': upcoming_interviews_qs.count(),                                             
        'recent_activities': recent_activities,                                                                  
        'recent_applicants': recent_applicants,
        'filter_values': {
            'q': q_filter or '',
            'categoria': categoria_filter or '',
            'estado': estado_filter or '',
        }
    }
    return render(request, 'company/company_index.html', context)

from django.views.decorators.csrf import ensure_csrf_cookie
@login_required
@ensure_csrf_cookie
def view_offer_applicants(request, offer_id):
    try:
        empresa_usuario = EmpresaUsuario.objects.using('jflex_db').select_related('empresa').get(id_empresa_user=request.user)
        company = empresa_usuario.empresa
    except EmpresaUsuario.DoesNotExist:
        messages.error(request, "No estás asociado a ninguna empresa.")
        return redirect('index')

    offer = get_object_or_404(OfertaLaboral.objects.using('jflex_db'), id_oferta=offer_id, empresa=company)

    # Define Kanban columns and their display names
    STATUS_CHOICES = [
        ('enviada', 'Nuevos Postulantes'),
        ('en proceso', 'En Revisión'),
        ('entrevista', 'Entrevistas'),
        ('aceptada', 'Aceptados'),
        ('rechazada', 'Rechazados'),
    ]
    
    applicants_by_status = {status[0]: [] for status in STATUS_CHOICES}

    postulaciones = Postulacion.objects.using('jflex_db').filter(oferta=offer).select_related(
        'candidato', 'candidato__ciudad', 'cv_postulado'
    ).order_by('-fecha_postulacion')

    applicant_user_ids = [p.candidato.id_candidato_id for p in postulaciones]
    users_from_default = User.objects.using('default').filter(pk__in=applicant_user_ids)
    user_map = {user.pk: user for user in users_from_default}

    today = date.today()
    for p in postulaciones:
        candidato = p.candidato
        user = user_map.get(candidato.id_candidato_id)

        if not user:
            continue

        age = None
        if candidato.fecha_nacimiento:
            age = today.year - candidato.fecha_nacimiento.year - ((today.month, today.day) < (candidato.fecha_nacimiento.month, candidato.fecha_nacimiento.day))

        # Check if an interview is scheduled for this postulation
        has_interview = Entrevista.objects.using('jflex_db').filter(postulacion=p).exists()

        applicant_data = {
            'postulacion_id': p.id_postulacion,
            'full_name': user.get_full_name(),
            'age': age,
            'location': candidato.ciudad.nombre if candidato.ciudad else 'No especificada',
            'availability': 'Disponible' if candidato.disponible else 'No Disponible',
            'application_date': p.fecha_postulacion,
            'cv_id': p.cv_postulado.id_cv_user,
            'cv_type': p.cv_postulado.tipo_cv,
            'cv_url': None,  # Default value
            'has_interview': has_interview, # Add the flag here
        }
        
        if applicant_data['cv_type'] == 'subido':
            try:
                cv_subido = CVSubido.objects.using('jflex_db').get(pk=applicant_data['cv_id'])
                applicant_data['cv_url'] = cv_subido.ruta_archivo
            except CVSubido.DoesNotExist:
                pass  # Keep cv_url as None if not found
        
        # Add applicant to the correct status list
        status_key = p.estado_postulacion
        if status_key not in applicants_by_status:
            status_key = 'enviada' # Default to the first column if status is invalid or empty
        
        applicants_by_status[status_key].append(applicant_data)

    # Restructure data for easier template iteration
    kanban_data = []
    tooltips = {
        "enviada": "Postulantes que han aplicado a la oferta. Aún no se ha realizado ninguna acción.",
        "en proceso": "Postulantes cuyo CV está siendo revisado. Aquí puedes agendar una entrevista.",
        "entrevista": "Postulantes que ya tienen una entrevista agendada.",
        "aceptada": "Postulantes que han sido seleccionados para el puesto.",
        "rechazada": "Postulantes que no continúan en el proceso de selección."
    }
    for status_key, status_name in STATUS_CHOICES:
        kanban_data.append({
            'status_key': status_key,
            'status_name': status_name,
            'applicants': applicants_by_status.get(status_key, []),
            'tooltip': tooltips.get(status_key, "Sin descripción.")
        })

    context = {
        'offer': offer,
        'kanban_data': kanban_data,
        'company': company,
    }
    return render(request, 'company/offer_applicants.html', context)

@login_required
def update_postulacion_status(request, postulacion_id):
    if request.method == 'POST':
        try:
            # Security Check: Ensure user is associated with a company
            empresa_usuario = EmpresaUsuario.objects.using('jflex_db').get(id_empresa_user=request.user)
            
            # Get the application and verify it belongs to the user's company
            postulacion = get_object_or_404(
                Postulacion.objects.using('jflex_db').select_related('oferta__empresa'),
                pk=postulacion_id
            )

            if postulacion.oferta.empresa != empresa_usuario.empresa:
                return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

            data = json.loads(request.body)
            new_status = data.get('new_status')

            # Simplified and correct validation
            valid_kanban_statuses = ['enviada', 'en proceso', 'entrevista', 'aceptada', 'rechazada']
            if new_status not in valid_kanban_statuses:
                return JsonResponse({'status': 'error', 'message': f'Invalid status: {new_status}'}, status=400)

            postulacion.estado_postulacion = new_status
            postulacion.save(using='jflex_db')
            
            return JsonResponse({'status': 'success', 'message': 'Status updated successfully.'})

        except EmpresaUsuario.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not associated with any company.'}, status=403)
        except Postulacion.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Application not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_applicant_details(request, postulacion_id):
    try:
        # Set locale to Spanish for month names
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Fallback for Windows

        # Security Check: Ensure user is associated with a company
        empresa_usuario = EmpresaUsuario.objects.using('jflex_db').get(id_empresa_user=request.user)
        
        # Get the application and verify it belongs to the user's company
        postulacion = get_object_or_404(
            Postulacion.objects.using('jflex_db').select_related(
                'oferta__empresa', 
                'candidato__ciudad__region', 
                'cv_postulado'
            ),
            pk=postulacion_id
        )

        if postulacion.oferta.empresa != empresa_usuario.empresa:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        
        # Mark CV as viewed
        if not postulacion.cv_visto:
            postulacion.cv_visto = True
            postulacion.save(using='jflex_db')

        candidato = postulacion.candidato
        cv = postulacion.cv_postulado
        
        # Get User model data from the default database
        user_details = User.objects.using('default').get(pk=candidato.id_candidato_id)

        # 1. Serialize Personal Data
        today = date.today()
        age = None
        if candidato.fecha_nacimiento:
            age = today.year - candidato.fecha_nacimiento.year - ((today.month, today.day) < (candidato.fecha_nacimiento.month, candidato.fecha_nacimiento.day))

        location_str = 'No especificada'
        if candidato.ciudad:
            location_str = candidato.ciudad.nombre
            if candidato.ciudad.region:
                location_str = f"{candidato.ciudad.nombre}, {candidato.ciudad.region.nombre}"

        personal_data = {
            'full_name': user_details.get_full_name(),
            'email': user_details.email,
            'rut': candidato.rut_candidato,
            'phone': candidato.telefono,
            'age': age,
            'location': location_str,
            'linkedin_url': candidato.linkedin_url,
            'availability': 'Disponible' if candidato.disponible else 'No Disponible',
        }

        # 2. Serialize CV Data
        cv_data = {
            'cv_type': cv.tipo_cv,
            'cv_name': cv.nombre_cv,
            'cv_title': cv.cargo_asociado,
            'content': None
        }

        if cv.tipo_cv == 'subido':
            try:
                cv_subido = CVSubido.objects.using('jflex_db').get(pk=cv.id_cv_user)
                cv_data['content'] = cv_subido.ruta_archivo
            except CVSubido.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Uploaded CV file not found.'}, status=404)
        
        elif cv.tipo_cv == 'creado':
            try:
                cv_creado = CVCreado.objects.using('jflex_db').get(pk=cv.id_cv_user)
                
                def safe_get(obj, attr, default=''):
                    return getattr(obj, attr, default) if obj else default

                personal_data_obj = getattr(cv_creado, 'datospersonalescv', None)
                objective_obj = getattr(cv_creado, 'objetivoprofesionalcv', None)

                cv_data['content'] = {
                    'personalData': {
                        'firstName': safe_get(personal_data_obj, 'primer_nombre'),
                        'secondName': safe_get(personal_data_obj, 'segundo_nombre'),
                        'lastName': safe_get(personal_data_obj, 'apellido_paterno'),
                        'motherLastName': safe_get(personal_data_obj, 'apellido_materno'),
                        'title': safe_get(personal_data_obj, 'titulo_profesional'),
                        'email': safe_get(personal_data_obj, 'email'),
                        'phone': safe_get(personal_data_obj, 'telefono'),
                        'linkedin_link': safe_get(personal_data_obj, 'linkedin')
                    },
                    'objective': safe_get(objective_obj, 'texto_objetivo'),
                    'experience': [
                        {
                            'position': exp.cargo_puesto,
                            'company': exp.empresa,
                            'location': exp.ubicacion,
                            'start_date': exp.fecha_inicio.strftime('%B %Y') if exp.fecha_inicio else '',
                            'end_date': 'Presente' if exp.trabajo_actual else (exp.fecha_termino.strftime('%B %Y') if exp.fecha_termino else ''),
                            'description': exp.descripcion_cargo
                        } for exp in cv_creado.experiencia.all().order_by('-fecha_inicio')
                    ],
                    'education': [
                        {
                            'institution': edu.institucion,
                            'degree': edu.carrera_titulo_nivel,
                            'start_year': edu.fecha_inicio.year if edu.fecha_inicio else '',
                            'end_year': edu.fecha_termino.year if edu.fecha_termino and not edu.cursando else 'Presente',
                            'notes': edu.comentarios
                        } for edu in cv_creado.educacion.all().order_by('-fecha_inicio')
                    ],
                    'skills': {
                        'hard': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='hard')],
                        'soft': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='soft')]
                    },
                    'languages': [
                        {
                            'language': lang.nombre_idioma,
                            'level': lang.nivel_idioma
                        } for lang in cv_creado.idiomas.all()
                    ],
                    'certifications': [
                        {
                            'cert_name': cert.nombre_certificacion,
                            'issuer': cert.entidad_emisora,
                            'year': cert.fecha_obtencion.year if cert.fecha_obtencion else ''
                        } for cert in cv_creado.certificaciones.all()
                    ],
                    'projects': [
                        {
                            'project_name': proj.nombre_proyecto,
                            'period': proj.fecha_proyecto,
                            'role': proj.rol_participacion,
                            'description': proj.descripcion_proyecto,
                            'link': proj.url_proyecto
                        } for proj in cv_creado.proyectos.all()
                    ],
                    'volunteering': [
                        {
                            'organization': vol.nombre_organizacion,
                            'role': vol.puesto_rol,
                            'description': vol.descripcion_actividades,
                            'city': vol.ciudad,
                            'country': vol.pais,
                            'region': vol.region_estado_provincia,
                            'start_date': vol.fecha_inicio.isoformat() if vol.fecha_inicio else '',
                            'end_date': vol.fecha_termino.isoformat() if vol.fecha_termino and not vol.actualmente_activo else 'Presente',
                            'current': vol.actualmente_activo
                        } for vol in cv_creado.voluntariado.all()
                    ],
                    'references': [
                        {
                            'name': ref.nombre_referente,
                            'position': ref.cargo_referente,
                            'phone': ref.telefono,
                            'email': ref.email,
                            'linkedin_url': ref.url_linkedin
                        } for ref in cv_creado.referencias.all()
                    ]
                }

            except CVCreado.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Created CV data not found.'}, status=404)

        response_data = {
            'personal_data': personal_data,
            'cv_data': cv_data
        }

        return JsonResponse({'status': 'success', 'data': response_data})

    except EmpresaUsuario.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not associated with any company.'}, status=403)
    except Postulacion.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Application not found.'}, status=404)
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Candidate user account not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@transaction.atomic
def schedule_interview(request, postulacion_id):
    if request.method == 'POST':
        try:
            # Security Check
            empresa_usuario = EmpresaUsuario.objects.using('jflex_db').get(id_empresa_user=request.user)
            postulacion = get_object_or_404(
                Postulacion.objects.using('jflex_db').select_related('oferta__empresa', 'candidato'),
                pk=postulacion_id
            )
            if postulacion.oferta.empresa != empresa_usuario.empresa:
                return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

            data = json.loads(request.body)
            
            # --- Logic for Rescheduling ---
            # If an interview already exists, delete it before creating a new one.
            # This handles both new schedules and reschedules in one flow.
            existing_interview = Entrevista.objects.using('jflex_db').filter(postulacion=postulacion).first()
            if existing_interview:
                existing_interview.delete() # This will cascade and delete ModoOnline/Presencial as well

            # Explicitly convert string data to date and time objects
            fecha_obj = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
            hora_obj = datetime.strptime(data['hora'], '%H:%M').time()

            # Create Entrevista object
            entrevista = Entrevista.objects.using('jflex_db').create(
                postulacion=postulacion,
                fecha_entrevista=fecha_obj,
                hora_entrevista=hora_obj,
                nombre_reclutador=data['entrevistador'],
                modalidad=data['modalidad']
            )

            # CRITICAL FIX: Fetch user from the 'default' database before accessing its properties
            candidato_user = User.objects.using('default').get(pk=postulacion.candidato.id_candidato_id)

            # Create modality-specific object and gather email context
            email_context = {
                'candidato_name': candidato_user.get_full_name(),
                'company_name': postulacion.oferta.empresa.nombre_comercial,
                'job_title': postulacion.oferta.titulo_puesto,
                'interview_date': fecha_obj,
                'interview_time': hora_obj,
                'recruiter_name': entrevista.nombre_reclutador,
                'is_reschedule': bool(existing_interview) # Add a flag for the email template
            }
            
            if data['modalidad'] == 'Online':
                modo_online = ModoOnline.objects.using('jflex_db').create(
                    id_modo_online=entrevista,
                    plataforma=data['plataforma'],
                    url_reunion=data['url']
                )
                email_context['platform'] = modo_online.plataforma
                email_context['url'] = modo_online.url_reunion
                template_path = 'emails/interview_notification_online.html'
                subject_verb = "Reagendamiento de Entrevista" if existing_interview else "Invitación a Entrevista"
                subject = f"{subject_verb} Online para {postulacion.oferta.titulo_puesto}"

            elif data['modalidad'] == 'Presencial':
                modo_presencial = ModoPresencial.objects.using('jflex_db').create(
                    id_modo_presencial=entrevista,
                    direccion=data['direccion']
                )
                email_context['address'] = modo_presencial.direccion
                template_path = 'emails/interview_notification_presencial.html'
                subject_verb = "Reagendamiento de Entrevista" if existing_interview else "Invitación a Entrevista"
                subject = f"{subject_verb} Presencial para {postulacion.oferta.titulo_puesto}"

            # Send notification email
            message = render_to_string(template_path, email_context)
            to_email = candidato_user.email
            email_message = EmailMessage(subject, message, to=[to_email])
            email_message.content_subtype = "html"
            email_message.send()

            # Update application status
            postulacion.estado_postulacion = 'entrevista'
            postulacion.save(using='jflex_db')

            return JsonResponse({'status': 'success', 'message': 'Entrevista agendada y correo enviado exitosamente.'})

        except (EmpresaUsuario.DoesNotExist, Postulacion.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        except KeyError as e:
            return JsonResponse({'status': 'error', 'message': f'Falta el siguiente dato: {e}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_interview_details(request, postulacion_id):
    try:
        # Set locale for proper date formatting
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')

        # Security check
        empresa_usuario = EmpresaUsuario.objects.using('jflex_db').get(id_empresa_user=request.user)
        postulacion = get_object_or_404(Postulacion, pk=postulacion_id)
        if postulacion.oferta.empresa != empresa_usuario.empresa:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

        entrevista = get_object_or_404(Entrevista.objects.select_related('modoonline', 'modopresencial'), postulacion=postulacion)

        details = {
            'interview_id': entrevista.id_entrevista,
            'fecha': entrevista.fecha_entrevista.strftime('%Y-%m-%d'),
            'hora': entrevista.hora_entrevista.strftime('%H:%M'),
            'fecha_display': entrevista.fecha_entrevista.strftime('%A, %d de %B de %Y'),
            'hora_display': entrevista.hora_entrevista.strftime('%H:%M hrs'),
            'entrevistador': entrevista.nombre_reclutador,
            'modalidad': entrevista.modalidad,
            'plataforma': None,
            'url': None,
            'direccion': None,
        }

        if entrevista.modalidad == 'Online' and hasattr(entrevista, 'modoonline'):
            details['plataforma'] = entrevista.modoonline.plataforma
            details['url'] = entrevista.modoonline.url_reunion
        elif entrevista.modalidad == 'Presencial' and hasattr(entrevista, 'modopresencial'):
            details['direccion'] = entrevista.modopresencial.direccion
        
        return JsonResponse({'status': 'success', 'details': details})

    except (EmpresaUsuario.DoesNotExist, Postulacion.DoesNotExist, Entrevista.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@transaction.atomic
def delete_interview(request, interview_id):
    if request.method == 'POST':
        try:
            # Security check
            empresa_usuario = EmpresaUsuario.objects.using('jflex_db').get(id_empresa_user=request.user)
            entrevista = get_object_or_404(
                Entrevista.objects.using('jflex_db').select_related('postulacion__oferta__empresa', 'postulacion__candidato'), 
                pk=interview_id
            )
            if entrevista.postulacion.oferta.empresa != empresa_usuario.empresa:
                return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

            postulacion = entrevista.postulacion
            
            # CRITICAL FIX: Fetch user from the 'default' database
            candidato_user = User.objects.using('default').get(pk=postulacion.candidato.id_candidato_id)

            # Prepare email context BEFORE deleting
            email_context = {
                'candidato_name': candidato_user.get_full_name(),
                'company_name': postulacion.oferta.empresa.nombre_comercial,
                'job_title': postulacion.oferta.titulo_puesto,
                'interview_date': entrevista.fecha_entrevista,
                'interview_time': entrevista.hora_entrevista,
            }
            
            # Delete the interview
            entrevista.delete(using='jflex_db')

            # Change status to 'rechazada' as requested
            postulacion.estado_postulacion = 'rechazada'
            postulacion.save(using='jflex_db')
            
            # Send cancellation email
            message = render_to_string('emails/interview_cancellation.html', email_context)
            to_email = candidato_user.email
            email_message = EmailMessage(f"Cancelación de Entrevista para {postulacion.oferta.titulo_puesto}", message, to=[to_email])
            email_message.content_subtype = "html"
            email_message.send()

            return JsonResponse({'status': 'success', 'message': 'Entrevista eliminada, estado actualizado a "Rechazado" y correo de cancelación enviado.'})

        except (EmpresaUsuario.DoesNotExist, Entrevista.DoesNotExist, User.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found or permission denied.'}, status=404)
        except Exception as e:
            # Log the error for debugging
            print(f"Error in delete_interview: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


from django.db.models.functions import ExtractMonth
@login_required
def postulaciones(request: HttpRequest):
    #postulacion
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    def count_statuses(queryset):
      return queryset.aggregate(
          total=Count("id_postulacion"),
          sent=Count("id_postulacion", filter=Q(estado_postulacion="enviada")),
          in_progress=Count("id_postulacion", filter=Q(estado_postulacion="en proceso")),
          aproved=Count("id_postulacion", filter=Q(estado_postulacion="aceptada")|Q(estado_postulacion="entrevista")),
          rejected=Count("id_postulacion", filter=Q(estado_postulacion="rechazada")),
      )
    postu = Postulacion.objects.all().filter(candidato_id=request.user.pk)
    week_qs  = postu.filter(fecha_postulacion__date__gte=week_start)
    month_qs = postu.filter(fecha_postulacion__date__gte=month_start)

    week_stats = count_statuses(week_qs)
    month_stats = count_statuses(month_qs)

    year_qs  = (postu.filter(fecha_postulacion__date__gte=year_start).annotate(month=ExtractMonth("fecha_postulacion"))
      .values("month")
      .annotate(
          aproved=Count("id_postulacion", filter=Q(estado_postulacion="aceptada")|Q(estado_postulacion="entrevista")),
          rejected=Count("id_postulacion", filter=Q(estado_postulacion="rechazada")),
      )
      .order_by("month"))
    # Inicializar meses con 0
    stats_by_month = {
        m: {"aproved": 0, "rejected": 0}
        for m in range(1, 12 + 1)
    }
    # Rellenar con datos reales
    for row in year_qs:
        m = row["month"]
        stats_by_month[m]["aproved"] = row["aproved"]
        stats_by_month[m]["rejected"] = row["rejected"]
    apro_data = [stats_by_month[m]["aproved"] for m in range(1, 13)]
    recho_data = [stats_by_month[m]["rejected"] for m in range(1, 13)]
    apps = application_status(postu,'%d de %b, %Y')
    #entrevista
    inters = Entrevista.objects.filter(postulacion__in=postu).select_related("modoonline","modopresencial")
    ctx={
      'applied':apps,
      'interviews':inters,
      'tot_week':week_stats,
      'tot_month':month_stats,
      'tot_year':{
          'aproved':apro_data,
          'rejected':recho_data
      }
    }
    return render(request, 'user/postulaciones.html',ctx)

from django.core.serializers import serialize

@login_required
def perfiles_profesionales(request):
    candidato = Candidato.objects.get(id_candidato=request.user)
    
    if request.method == 'POST' and 'submit_cv' in request.POST:
        cv_subido_form = CVSubidoForm(request.POST, request.FILES)
        if cv_subido_form.is_valid():
            file = cv_subido_form.cleaned_data['cv_file']
            username = request.user.username
            filename = f"{uuid.uuid4().hex[:8]}_{file.name}"
            s3_key = f"CVs/{username}/{filename}"

            file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)

            cv_candidato = CVCandidato.objects.create(
                candidato=candidato,
                nombre_cv=cv_subido_form.cleaned_data['nombre_cv'],
                cargo_asociado=cv_subido_form.cleaned_data['cargo_asociado'],
                tipo_cv='subido'
            )
            
            CVSubido.objects.create(
                id_cv_subido=cv_candidato,
                ruta_archivo=file_url
            )
            
            messages.success(request, "Tu CV ha sido subido exitosamente.")
            return redirect('perfiles_profesionales')
    else:
        cv_subido_form = CVSubidoForm()

    cvs_qs = CVCandidato.objects.filter(candidato=candidato).select_related('cvcreado', 'cvsubido')

    cvs_list = []
    for cv in cvs_qs:
        cv_item = {
            'id_cv_user': cv.id_cv_user,
            'nombre_cv': cv.nombre_cv,
            'cargo_asociado': cv.cargo_asociado,
            'tipo_cv': cv.tipo_cv,
            'cv_data_json': '{}',
            'url': None,
            'ultima_actualizacion': None
        }
        cv_item['stats']=(
              CVCandidato.objects
              .filter(id_cv_user=cv.id_cv_user)
              .annotate(
                  total=Count('postulacion', distinct=True),
                  aceptado=Count('postulacion', filter=Q(postulacion__estado_postulacion='aprobado'), distinct=True),
                  rechazado=Count('postulacion', filter=Q(postulacion__estado_postulacion='rechazado'), distinct=True),
                  entrevistas=Count('postulacion__entrevista', distinct=True),
              )
              .values(
                  'total',
                  'aceptado',
                  'rechazado',
                  'entrevistas'
              )
              .first()
          )
        if cv.tipo_cv == 'creado' and hasattr(cv, 'cvcreado'):
            cv_creado = cv.cvcreado
            cv_item['ultima_actualizacion'] = cv_creado.ultima_actualizacion
            
            def safe_get(obj, attr, default=''):
                return getattr(obj, attr, default) if obj else default

            personal_data_obj = getattr(cv_creado, 'datospersonalescv', None)
            objective_obj = getattr(cv_creado, 'objetivoprofesionalcv', None)

            cv_data = {
                'personalData': {
                    'firstName': safe_get(personal_data_obj, 'primer_nombre'),
                    'secondName': safe_get(personal_data_obj, 'segundo_nombre'),
                    'lastName': safe_get(personal_data_obj, 'apellido_paterno'),
                    'motherLastName': safe_get(personal_data_obj, 'apellido_materno'),
                    'title': safe_get(personal_data_obj, 'titulo_profesional'),
                    'email': safe_get(personal_data_obj, 'email'),
                    'phone': safe_get(personal_data_obj, 'telefono'),
                    'linkedin_link': safe_get(personal_data_obj, 'linkedin')
                },
                'objective': safe_get(objective_obj, 'texto_objetivo'),
                'experience': [
                    {
                        'position': exp.cargo_puesto,
                        'company': exp.empresa,
                        'location': exp.ubicacion,
                        'start_month': exp.fecha_inicio.strftime('%B') if exp.fecha_inicio else '',
                        'start_year': exp.fecha_inicio.year if exp.fecha_inicio else '',
                        'end_month': exp.fecha_termino.strftime('%B') if exp.fecha_termino else '',
                        'end_year': exp.fecha_termino.year if exp.fecha_termino else '',
                        'current_job': exp.trabajo_actual,
                        'is_internship': exp.practica,
                        'total_hours': exp.horas_practica,
                        'description': exp.descripcion_cargo
                    } for exp in cv_creado.experiencia.all()
                ],
                'education': [
                    {
                        'institution': edu.institucion,
                        'degree': edu.carrera_titulo_nivel,
                        'start_year': edu.fecha_inicio.year if edu.fecha_inicio else '',
                        'end_year': edu.fecha_termino.year if edu.fecha_termino else '',
                        'currently_studying': edu.cursando,
                        'notes': edu.comentarios
                    } for edu in cv_creado.educacion.all()
                ],
                'skills': {
                    'hard': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='hard')],
                    'soft': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='soft')]
                },
                'languages': [
                    {
                        'language': lang.nombre_idioma,
                        'level': lang.nivel_idioma
                    } for lang in cv_creado.idiomas.all()
                ],
                'certifications': [
                    {
                        'cert_name': cert.nombre_certificacion,
                        'issuer': cert.entidad_emisora,
                        'year': cert.fecha_obtencion.year if cert.fecha_obtencion else ''
                    } for cert in cv_creado.certificaciones.all()
                ],
                'projects': [
                    {
                        'project_name': proj.nombre_proyecto,
                        'period': proj.fecha_proyecto,
                        'role': proj.rol_participacion,
                        'description': proj.descripcion_proyecto,
                        'link': proj.url_proyecto
                    } for proj in cv_creado.proyectos.all()
                ],
                'volunteering': [
                    {
                        'organization': vol.nombre_organizacion,
                        'role': vol.puesto_rol,
                        'description': vol.descripcion_actividades,
                        'city': vol.ciudad,
                        'country': vol.pais,
                        'region': vol.region_estado_provincia,
                        'start_date': vol.fecha_inicio.isoformat() if vol.fecha_inicio else '',
                        'end_date': vol.fecha_termino.isoformat() if vol.fecha_termino else '',
                        'current': vol.actualmente_activo
                    } for vol in cv_creado.voluntariado.all()
                ],
                'references': [
                    {
                        'name': ref.nombre_referente,
                        'position': ref.cargo_referente,
                        'phone': ref.telefono,
                        'email': ref.email,
                        'linkedin_url': ref.url_linkedin
                    } for ref in cv_creado.referencias.all()
                ]
            }
            cv_item['cv_data_json'] = json.dumps(cv_data, cls=DjangoJSONEncoder)
        
        elif cv.tipo_cv == 'subido' and hasattr(cv, 'cvsubido'):
            cv_subido = cv.cvsubido
            cv_item['url'] = cv_subido.ruta_archivo
            cv_item['ultima_actualizacion'] = cv_subido.fecha_subido

        cvs_list.append(cv_item)

    context = {
        'cvs': cvs_list,
        'cv_subido_form': cv_subido_form
    }
    return render(request, 'user/perfiles_profesionales.html', context)

@login_required
def create_cv(request):
    next_url = request.GET.get('next', None)
    context = {
        'next_url': next_url
    }
    return render(request, 'user/create_cv.html', context)

@login_required
def edit_cv(request, cv_id):
    try:
        cv = CVCandidato.objects.get(id_cv_user=cv_id, candidato__id_candidato=request.user)
        cv_creado = getattr(cv, 'cvcreado', None)
        if not cv_creado:
            raise CVCandidato.DoesNotExist

        # Helper to safely get attributes from related objects
        def safe_get(obj, attr, default=''):
            return getattr(obj, attr, default) if obj else default

        personal_data_obj = getattr(cv_creado, 'datospersonalescv', None)
        objective_obj = getattr(cv_creado, 'objetivoprofesionalcv', None)

        month_map = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
            7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }

        experience_data = [
            {
                'position': exp.cargo_puesto,
                'company': exp.empresa,
                'location': exp.ubicacion,
                'start_month': month_map[exp.fecha_inicio.month] if exp.fecha_inicio else '',
                'start_year': exp.fecha_inicio.year if exp.fecha_inicio else '',
                'end_month': month_map[exp.fecha_termino.month] if exp.fecha_termino else '',
                'end_year': exp.fecha_termino.year if exp.fecha_termino else '',
                'current_job': exp.trabajo_actual,
                'is_internship': exp.practica,
                'total_hours': exp.horas_practica,
                'description': exp.descripcion_cargo
            } for exp in cv_creado.experiencia.all()
        ]

        cv_data = {
            'personalData': {
                'firstName': safe_get(personal_data_obj, 'primer_nombre'),
                'secondName': safe_get(personal_data_obj, 'segundo_nombre'),
                'lastName': safe_get(personal_data_obj, 'apellido_paterno'),
                'motherLastName': safe_get(personal_data_obj, 'apellido_materno'),
                'title': safe_get(personal_data_obj, 'titulo_profesional'),
                'email': safe_get(personal_data_obj, 'email'),
                'phone': safe_get(personal_data_obj, 'telefono'),
                'linkedin_link': safe_get(personal_data_obj, 'linkedin')
            },
            'objective': safe_get(objective_obj, 'texto_objetivo'),
            'experience': experience_data,
            'education': [
                {
                    'institution': edu.institucion,
                    'degree': edu.carrera_titulo_nivel,
                    'start_year': edu.fecha_inicio.year if edu.fecha_inicio else '',
                    'end_year': edu.fecha_termino.year if edu.fecha_termino else '',
                    'currently_studying': edu.cursando,
                    'notes': edu.comentarios
                } for edu in cv_creado.educacion.all()
            ],
            'skills': {
                'hard': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='hard')],
                'soft': [h.texto_habilidad for h in cv_creado.habilidades.filter(tipo_habilidad='soft')]
            },
            'languages': [
                {
                    'language': lang.nombre_idioma,
                    'level': lang.nivel_idioma
                } for lang in cv_creado.idiomas.all()
            ],
            'certifications': [
                {
                    'cert_name': cert.nombre_certificacion,
                    'issuer': cert.entidad_emisora,
                    'year': cert.fecha_obtencion.year if cert.fecha_obtencion else ''
                } for cert in cv_creado.certificaciones.all()
            ],
            'projects': [
                {
                    'project_name': proj.nombre_proyecto,
                    'period': proj.fecha_proyecto,
                    'role': proj.rol_participacion,
                    'description': proj.descripcion_proyecto,
                    'link': proj.url_proyecto
                } for proj in cv_creado.proyectos.all()
            ],
            'volunteering': [
                {
                    'organization': vol.nombre_organizacion,
                    'role': vol.puesto_rol,
                    'description': vol.descripcion_actividades,
                    'city': vol.ciudad,
                    'country': vol.pais,
                    'region': vol.region_estado_provincia,
                    'start_date': vol.fecha_inicio.isoformat() if vol.fecha_inicio else '',
                    'end_date': vol.fecha_termino.isoformat() if vol.fecha_termino else '',
                    'current': vol.actualmente_activo
                } for vol in cv_creado.voluntariado.all()
            ],
            'references': [
                {
                    'name': ref.nombre_referente,
                    'position': ref.cargo_referente,
                    'phone': ref.telefono,
                    'email': ref.email,
                    'linkedin_url': ref.url_linkedin
                } for ref in cv_creado.referencias.all()
            ]
        }

        context = {
            'cv_data': cv_data,
            'cv_id': cv_id,
            'cv_name': cv.nombre_cv,
            'cargo_asociado': cv.cargo_asociado
        }
        return render(request, 'user/edit_cv.html', context)

    except CVCandidato.DoesNotExist:
        messages.error(request, "No se encontró el CV o no tienes permiso para editarlo.")
        return redirect('perfiles_profesionales')
    except Exception as e:
        messages.error(request, f"Ocurrió un error al cargar el CV para editar: {e}")
        return redirect('perfiles_profesionales')

from django.core.serializers.json import DjangoJSONEncoder

@login_required
def delete_cv(request, cv_id):
    if request.method == 'POST':
        try:
            cv = CVCandidato.objects.get(id_cv_user=cv_id, candidato__id_candidato=request.user)

            # Si el CV es de tipo 'subido', borrar el archivo de S3 primero
            if cv.tipo_cv == 'subido' and hasattr(cv, 'cvsubido'):
                try:
                    s3_url = cv.cvsubido.ruta_archivo
                    # Extraer la clave del objeto desde la URL de forma robusta
                    parsed_url = urlparse(s3_url)
                    object_key = parsed_url.path.lstrip('/')

                    s3 = boto3.client(
                        's3',
                        aws_access_key_id=django_settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=django_settings.AWS_SECRET_ACCESS_KEY,
                    )
                    s3.delete_object(
                        Bucket=django_settings.AWS_STORAGE_BUCKET_NAME,
                        Key=object_key
                    )
                except Exception as s3_error:
                    # Si falla la eliminación en S3, se informa pero se continúa para borrar el registro de la BD
                    messages.warning(request, f"No se pudo eliminar el archivo de S3, pero se eliminará el registro. Error: {s3_error}")

            # Eliminar el registro de la base de datos (y sus relaciones en cascada)
            cv.delete()
            messages.success(request, "El CV ha sido eliminado exitosamente.")
        except CVCandidato.DoesNotExist:
            messages.error(request, "No se encontró el CV o no tienes permiso para eliminarlo.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error al eliminar el CV: {e}")
    
    # Redirigir a la página anterior o a una por defecto
    return redirect(request.META.get('HTTP_REFERER', 'perfiles_profesionales'))

def is_valid_email(email):
    """Valida el formato del correo electrónico."""
    if not email:
        return False
    # Expresión regular robusta para validar email
    pattern = r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)'
    return re.match(pattern, email) is not None

def _validate_cv_data(cv_name, cargo_asociado, cv_data):
    errors = {}

    # Validate CVCandidato fields
    if not cv_name or not cv_name.strip():
        errors['cv_name'] = 'El nombre del CV es obligatorio.'
    elif len(cv_name) > 100:
        errors['cv_name'] = 'El nombre del CV no puede exceder los 100 caracteres.'

    if not cargo_asociado or not cargo_asociado.strip():
        errors['cargo_asociado'] = 'El cargo asociado es obligatorio.'
    elif len(cargo_asociado) > 100:
        errors['cargo_asociado'] = 'El cargo asociado no puede exceder los 100 caracteres.'

    # Validate DatosPersonalesCV fields
    personal_data = cv_data.get('personalData', {})
    if not personal_data.get('firstName') or not personal_data.get('firstName').strip():
        errors['personalData.firstName'] = 'El primer nombre es obligatorio.'
    elif len(personal_data.get('firstName', '')) > 50:
        errors['personalData.firstName'] = 'El primer nombre no puede exceder los 50 caracteres.'

    if not personal_data.get('lastName') or not personal_data.get('lastName').strip():
        errors['personalData.lastName'] = 'El apellido paterno es obligatorio.'
    elif len(personal_data.get('lastName', '')) > 50:
        errors['personalData.lastName'] = 'El apellido paterno no puede exceder los 50 caracteres.'

    if not personal_data.get('email') or not personal_data.get('email').strip():
        errors['personalData.email'] = 'El correo electrónico es obligatorio.'
    elif len(personal_data.get('email', '')) > 150:
        errors['personalData.email'] = 'El correo electrónico no puede exceder los 150 caracteres.'
    elif not is_valid_email(personal_data.get('email', '')):
        errors['personalData.email'] = 'Formato de correo electrónico inválido.'

    if not personal_data.get('phone') or not personal_data.get('phone').strip():
        errors['personalData.phone'] = 'El teléfono es obligatorio.'
    elif len(personal_data.get('phone', '')) > 20:
        errors['personalData.phone'] = 'El teléfono no puede exceder los 20 caracteres.'
    
    if personal_data.get('secondName') and len(personal_data.get('secondName', '')) > 50:
        errors['personalData.secondName'] = 'El segundo nombre no puede exceder los 50 caracteres.'
    if personal_data.get('motherLastName') and len(personal_data.get('motherLastName', '')) > 50:
        errors['personalData.motherLastName'] = 'El apellido materno no puede exceder los 50 caracteres.'
    if personal_data.get('title') and len(personal_data.get('title', '')) > 100:
        errors['personalData.title'] = 'El título profesional no puede exceder los 100 caracteres.'
    if personal_data.get('linkedin_link') and len(personal_data.get('linkedin_link', '')) > 255:
        errors['personalData.linkedin_link'] = 'El link de LinkedIn no puede exceder los 255 caracteres.'
    # Basic URL validation for linkedin_link
    if personal_data.get('linkedin_link') and not (personal_data.get('linkedin_link').startswith('http://') or personal_data.get('linkedin_link').startswith('https://')):
        errors['personalData.linkedin_link'] = 'El link de LinkedIn debe ser una URL válida (empezar con http:// o https://).'


    # Validate ObjetivoProfesionalCV fields
    objective_text = cv_data.get('objective')
    if not objective_text or not objective_text.strip():
        errors['objective'] = 'El objetivo profesional es obligatorio.'
    elif len(objective_text) > 1000:
        errors['objective'] = 'El objetivo profesional no puede exceder los 1000 caracteres.'

    # Helper for date validation
    def is_valid_year_month(year, month_name=None):
        try:
            if month_name:
                month_num = month_to_number.get(month_name)
                if not month_num:
                    return False
                date(int(year), int(month_num), 1)
            else:
                date(int(year), 1, 1)
            return True
        except (ValueError, TypeError):
            return False

    month_to_number = {
        'Enero': '01', 'Febrero': '02', 'Marzo': '03', 'Abril': '04',
        'Mayo': '05', 'Junio': '06', 'Julio': '07', 'Agosto': '08',
        'Septiembre': '09', 'Octubre': '10', 'Noviembre': '11', 'Diciembre': '12'
    }

    # Validate ExperienciaLaboralCV fields
    for i, exp_data in enumerate(cv_data.get('experience', [])):
        prefix = f'experience[{i}].'
        if not exp_data.get('position') or not exp_data.get('position').strip():
            errors[prefix + 'position'] = 'El cargo o puesto es obligatorio.'
        elif len(exp_data.get('position', '')) > 100:
            errors[prefix + 'position'] = 'El cargo o puesto no puede exceder los 100 caracteres.'

        if not exp_data.get('company') or not exp_data.get('company').strip():
            errors[prefix + 'company'] = 'La empresa es obligatoria.'
        elif len(exp_data.get('company', '')) > 100:
            errors[prefix + 'company'] = 'La empresa no puede exceder los 100 caracteres.'

        if not exp_data.get('location') or not exp_data.get('location').strip():
            errors[prefix + 'location'] = 'La ubicación es obligatoria.'
        elif len(exp_data.get('location', '')) > 100:
            errors[prefix + 'location'] = 'La ubicación no puede exceder los 100 caracteres.'

        if not exp_data.get('start_year') or not exp_data.get('start_month'):
            errors[prefix + 'start_date'] = 'La fecha de inicio es obligatoria.'
        elif not is_valid_year_month(exp_data.get('start_year'), exp_data.get('start_month')):
            errors[prefix + 'start_date'] = 'Formato de fecha de inicio inválido.'

        if not (exp_data.get('current_job') == 'on' or exp_data.get('current_job') is True): # If not current job, end date is required
            if not exp_data.get('end_year') or not exp_data.get('end_month'):
                errors[prefix + 'end_date'] = 'La fecha de término es obligatoria si no es el trabajo actual.'
            elif not is_valid_year_month(exp_data.get('end_year'), exp_data.get('end_month')):
                errors[prefix + 'end_date'] = 'Formato de fecha de término inválido.'
            else:
                try:
                    start_date_obj = date(int(exp_data['start_year']), int(month_to_number[exp_data['start_month']]), 1)
                    end_date_obj = date(int(exp_data['end_year']), int(month_to_number[exp_data['end_month']]), 1)
                    if start_date_obj > end_date_obj:
                        errors[prefix + 'date_order'] = 'La fecha de inicio no puede ser posterior a la fecha de término.'
                except (ValueError, KeyError):
                    # Should be caught by is_valid_year_month, but as a fallback
                    errors[prefix + 'date_order'] = 'Error al comparar fechas.'

        if exp_data.get('description') and len(exp_data.get('description', '')) > 1000:
            errors[prefix + 'description'] = 'La descripción del cargo no puede exceder los 1000 caracteres.'
        
        if (exp_data.get('is_internship') == 'on' or exp_data.get('is_internship') is True):
            total_hours_val = exp_data.get('total_hours')
            if not total_hours_val:
                errors[prefix + 'total_hours'] = 'Las horas totales son obligatorias para prácticas.'
            else:
                try:
                    int(total_hours_val)
                except ValueError:
                    errors[prefix + 'total_hours'] = 'Las horas totales deben ser un número entero.'

    # Validate EducacionCV fields
    for i, edu_data in enumerate(cv_data.get('education', [])):
        prefix = f'education[{i}].'
        if not edu_data.get('institution') or not edu_data.get('institution').strip():
            errors[prefix + 'institution'] = 'La institución educativa es obligatoria.'
        elif len(edu_data.get('institution', '')) > 100:
            errors[prefix + 'institution'] = 'La institución educativa no puede exceder los 100 caracteres.'

        if not edu_data.get('degree') or not edu_data.get('degree').strip():
            errors[prefix + 'degree'] = 'La carrera/título/nivel es obligatoria.'
        elif len(edu_data.get('degree', '')) > 100:
            errors[prefix + 'degree'] = 'La carrera/título/nivel no puede exceder los 100 caracteres.'

        if not edu_data.get('start_year'):
            errors[prefix + 'start_year'] = 'El año de inicio es obligatorio.'
        elif not is_valid_year_month(edu_data.get('start_year')):
            errors[prefix + 'start_year'] = 'Formato de año de inicio inválido.'

        if not (edu_data.get('currently_studying') == 'on' or edu_data.get('currently_studying') is True): # If not currently studying, end year is required
            if not edu_data.get('end_year'):
                errors[prefix + 'end_year'] = 'El año de término es obligatorio si no está cursando actualmente.'
            elif not is_valid_year_month(edu_data.get('end_year')):
                errors[prefix + 'end_year'] = 'Formato de año de término inválido.'
            else:
                try:
                    start_year_obj = date(int(edu_data['start_year']), 1, 1)
                    end_year_obj = date(int(edu_data['end_year']), 1, 1)
                    if start_year_obj > end_year_obj:
                        errors[prefix + 'date_order'] = 'El año de inicio no puede ser posterior al año de término.'
                except (ValueError, KeyError):
                    errors[prefix + 'date_order'] = 'Error al comparar años.'
        
        if edu_data.get('notes') and len(edu_data.get('notes', '')) > 500:
            errors[prefix + 'notes'] = 'Los comentarios no pueden exceder los 500 caracteres.'

    # Validate HabilidadCV fields
    hard_skills = cv_data.get('skills', {}).get('hard', [])
    soft_skills = cv_data.get('skills', {}).get('soft', [])

    if len(hard_skills) > 10:
        errors['skills.hard'] = 'No se pueden tener más de 10 habilidades técnicas.'
    for i, skill_text in enumerate(hard_skills):
        if not skill_text or not skill_text.strip():
            errors[f'skills.hard[{i}]'] = 'La habilidad técnica no puede estar vacía.'
        elif len(skill_text) > 150:
            errors[f'skills.hard[{i}]'] = 'La habilidad técnica no puede exceder los 150 caracteres.'
    
    if len(soft_skills) > 10:
        errors['skills.soft'] = 'No se pueden tener más de 10 habilidades blandas.'
    for i, skill_text in enumerate(soft_skills):
        if not skill_text or not skill_text.strip():
            errors[f'skills.soft[{i}]'] = 'La habilidad blanda no puede estar vacía.'
        elif len(skill_text) > 150:
            errors[f'skills.soft[{i}]'] = 'La habilidad blanda no puede exceder los 150 caracteres.'

    # Validate IdiomaCV fields
    for i, lang_data in enumerate(cv_data.get('languages', [])):
        prefix = f'languages[{i}].'
        if not lang_data.get('language') or not lang_data.get('language').strip():
            errors[prefix + 'language'] = 'El nombre del idioma es obligatorio.'
        elif len(lang_data.get('language', '')) > 50:
            errors[prefix + 'language'] = 'El nombre del idioma no puede exceder los 50 caracteres.'

        if not lang_data.get('level') or not lang_data.get('level').strip():
            errors[prefix + 'level'] = 'El nivel del idioma es obligatorio.'
        elif lang_data.get('level') not in ['Básico', 'Intermedio', 'Avanzado', 'Nativo']:
            errors[prefix + 'level'] = 'Nivel de idioma inválido.'
        elif len(lang_data.get('level', '')) > 30:
            errors[prefix + 'level'] = 'El nivel del idioma no puede exceder los 30 caracteres.'

    # Validate CertificacionesCV fields
    for i, cert_data in enumerate(cv_data.get('certifications', [])):
        prefix = f'certifications[{i}].'
        if not cert_data.get('cert_name') or not cert_data.get('cert_name').strip():
            errors[prefix + 'cert_name'] = 'El nombre de la certificación es obligatorio.'
        elif len(cert_data.get('cert_name', '')) > 150:
            errors[prefix + 'cert_name'] = 'El nombre de la certificación no puede exceder los 150 caracteres.'

        if not cert_data.get('issuer') or not cert_data.get('issuer').strip():
            errors[prefix + 'issuer'] = 'La entidad emisora es obligatoria.'
        elif len(cert_data.get('issuer', '')) > 150:
            errors[prefix + 'issuer'] = 'La entidad emisora no puede exceder los 150 caracteres.'

        if not cert_data.get('year'):
            errors[prefix + 'year'] = 'El año de obtención es obligatorio.'
        elif not is_valid_year_month(cert_data.get('year')):
            errors[prefix + 'year'] = 'Formato de año de obtención inválido.'

    # Validate ProyectosCV fields
    for i, proj_data in enumerate(cv_data.get('projects', [])):
        prefix = f'projects[{i}].'
        if not proj_data.get('project_name') or not proj_data.get('project_name').strip():
            errors[prefix + 'project_name'] = 'El nombre del proyecto es obligatorio.'
        elif len(proj_data.get('project_name', '')) > 100:
            errors[prefix + 'project_name'] = 'El nombre del proyecto no puede exceder los 100 caracteres.'

        if not proj_data.get('period'):
            errors[prefix + 'period'] = 'El año o periodo de ejecución es obligatorio.'
        elif len(str(proj_data.get('period', ''))) > 100: # Max length for CharField in model is 100
            errors[prefix + 'period'] = 'El año o periodo de ejecución no puede exceder los 100 caracteres.'

        if proj_data.get('role') and len(proj_data.get('role', '')) > 100:
            errors[prefix + 'role'] = 'El rol de participación no puede exceder los 100 caracteres.'

        if not proj_data.get('description') or not proj_data.get('description').strip():
            errors[prefix + 'description'] = 'La descripción del proyecto es obligatoria.'
        elif len(proj_data.get('description', '')) > 1000:
            errors[prefix + 'description'] = 'La descripción del proyecto no puede exceder los 1000 caracteres.'

        if proj_data.get('link') and len(proj_data.get('link', '')) > 255:
            errors[prefix + 'link'] = 'El enlace no puede exceder los 255 caracteres.'
        elif proj_data.get('link') and not (proj_data.get('link').startswith('http://') or proj_data.get('link').startswith('https://')):
            errors[prefix + 'link'] = 'El enlace debe ser una URL válida (empezar con http:// o https://).'

    # Validate VoluntariadoCV fields
    for i, vol_data in enumerate(cv_data.get('volunteering', [])):
        prefix = f'volunteering[{i}].'
        if not vol_data.get('organization') or not vol_data.get('organization').strip():
            errors[prefix + 'organization'] = 'El nombre de la organización es obligatorio.'
        elif len(vol_data.get('organization', '')) > 100:
            errors[prefix + 'organization'] = 'El nombre de la organización no puede exceder los 100 caracteres.'

        if not vol_data.get('role') or not vol_data.get('role').strip():
            errors[prefix + 'role'] = 'El puesto/rol desempeñado es obligatorio.'
        elif len(vol_data.get('role', '')) > 100:
            errors[prefix + 'role'] = 'El puesto/rol desempeñado no puede exceder los 100 caracteres.'

        if vol_data.get('description') and len(vol_data.get('description', '')) > 1000:
            errors[prefix + 'description'] = 'La descripción de actividades no puede exceder los 1000 caracteres.'

        if not vol_data.get('city') or not vol_data.get('city').strip():
            errors[prefix + 'city'] = 'La ciudad es obligatoria.'
        elif len(vol_data.get('city', '')) > 50:
            errors[prefix + 'city'] = 'La ciudad no puede exceder los 50 caracteres.'
        
        if not vol_data.get('country') or not vol_data.get('country').strip():
            errors[prefix + 'country'] = 'El país es obligatorio.'
        elif len(vol_data.get('country', '')) > 50:
            errors[prefix + 'country'] = 'El país no puede exceder los 50 caracteres.'

        if not vol_data.get('start_date'):
            errors[prefix + 'start_date'] = 'La fecha de inicio es obligatoria.'
        else:
            try:
                datetime.strptime(vol_data['start_date'], '%Y-%m-%d').date()
            except ValueError:
                errors[prefix + 'start_date'] = 'Formato de fecha de inicio inválido (YYYY-MM-DD).'

        if not (vol_data.get('current') == 'on' or vol_data.get('current') == True):
            if not vol_data.get('end_date'):
                errors[prefix + 'end_date'] = 'La fecha de término es obligatoria si no está actualmente activo.'
            else:
                try:
                    datetime.strptime(vol_data['end_date'], '%Y-%m-%d').date()
                except ValueError:
                    errors[prefix + 'end_date'] = 'Formato de fecha de término inválido (YYYY-MM-DD).'
                
                if 'start_date' not in errors and 'end_date' not in errors:
                    try:
                        start_date_obj = datetime.strptime(vol_data['start_date'], '%Y-%m-%d').date()
                        end_date_obj = datetime.strptime(vol_data['end_date'], '%Y-%m-%d').date()
                        if start_date_obj > end_date_obj:
                            errors[prefix + 'date_order'] = 'La fecha de inicio no puede ser posterior a la fecha de término.'
                    except ValueError:
                        errors[prefix + 'date_order'] = 'Error al comparar fechas.'

    # Validate ReferenciasCV fields
    for i, ref_data in enumerate(cv_data.get('references', [])):
        prefix = f'references[{i}].'
        if not ref_data.get('name') or not ref_data.get('name').strip():
            errors[prefix + 'name'] = 'El nombre del referente es obligatorio.'
        elif len(ref_data.get('name', '')) > 100:
            errors[prefix + 'name'] = 'El nombre del referente no puede exceder los 100 caracteres.'

        if not ref_data.get('position') or not ref_data.get('position').strip():
            errors[prefix + 'position'] = 'El cargo del referente es obligatorio.'
        elif len(ref_data.get('position', '')) > 100:
            errors[prefix + 'position'] = 'El cargo del referente no puede exceder los 100 caracteres.'

        if not ref_data.get('phone') or not ref_data.get('phone').strip():
            errors[prefix + 'phone'] = 'El teléfono del referente es obligatorio.'
        elif len(ref_data.get('phone', '')) > 20:
            errors[prefix + 'phone'] = 'El teléfono del referente no puede exceder los 20 caracteres.'

        if not ref_data.get('email') or not ref_data.get('email').strip():
            errors[prefix + 'email'] = 'El correo electrónico del referente es obligatorio.'
        elif len(ref_data.get('email', '')) > 150:
            errors[prefix + 'email'] = 'El correo electrónico del referente no puede exceder los 150 caracteres.'
        elif not is_valid_email(ref_data.get('email', '')):
            errors[prefix + 'email'] = 'Formato de correo electrónico del referente inválido.'

        if ref_data.get('linkedin_url') and len(ref_data.get('linkedin_url', '')) > 255:
            errors[prefix + 'linkedin_url'] = 'El link de LinkedIn del referente no puede exceder los 255 caracteres.'
        elif ref_data.get('linkedin_url') and not (ref_data.get('linkedin_url').startswith('http://') or ref_data.get('linkedin_url').startswith('https://')):
            errors[prefix + 'linkedin_url'] = 'El link de LinkedIn del referente debe ser una URL válida (empezar con http:// o https://).'

    return errors

@login_required
@transaction.atomic
def save_cv(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cv_id = data.get('cv_id')
            cv_name = data.get('cv_name')
            cargo_asociado = data.get('cargo_asociado')
            cv_data = data.get('cvData')

            if not cv_name or not cargo_asociado or not cv_data:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos esenciales para guardar el CV.'}, status=400)

            # Perform server-side validation
            validation_errors = _validate_cv_data(cv_name, cargo_asociado, cv_data)
            if validation_errors:
                return JsonResponse({'status': 'error', 'message': 'Errores de validación.', 'errors': validation_errors}, status=400)

            candidato = Candidato.objects.get(id_candidato=request.user)
            
            cv_candidato = None
            if cv_id:
                # Update existing CV
                cv_candidato = CVCandidato.objects.get(id_cv_user=cv_id, candidato=candidato)
                cv_candidato.nombre_cv = cv_name
                cv_candidato.cargo_asociado = cargo_asociado
                cv_candidato.save()

                # Delete old data associated with the CV
                if hasattr(cv_candidato, 'cvcreado'):
                    cv_candidato.cvcreado.delete()
            else:
                # Create new CV
                cv_candidato = CVCandidato.objects.create(
                    candidato=candidato,
                    nombre_cv=cv_name,
                    cargo_asociado=cargo_asociado,
                    tipo_cv='creado'
                )
            
            # Create new CVCreado instance and associated data
            cv_creado = CVCreado.objects.create(id_cv_creado=cv_candidato)

            month_to_number = {
                'Enero': '01', 'Febrero': '02', 'Marzo': '03', 'Abril': '04',
                'Mayo': '05', 'Junio': '06', 'Julio': '07', 'Agosto': '08',
                'Septiembre': '09', 'Octubre': '10', 'Noviembre': '11', 'Diciembre': '12'
            }

            # Personal Data
            personal_data = cv_data.get('personalData', {})
            DatosPersonalesCV.objects.create(
                id_cv_creado=cv_creado,
                primer_nombre=personal_data.get('firstName'),
                segundo_nombre=personal_data.get('secondName'),
                apellido_paterno=personal_data.get('lastName'),
                apellido_materno=personal_data.get('motherLastName'),
                titulo_profesional=personal_data.get('title'),
                email=personal_data.get('email'),
                telefono=personal_data.get('phone'),
                linkedin=personal_data.get('linkedin_link')
            )

            # Objective
            objective_text = cv_data.get('objective')
            if objective_text:
                ObjetivoProfesionalCV.objects.create(
                    id_cv_creado=cv_creado,
                    texto_objetivo=objective_text
                )

            # Experience
            for exp_data in cv_data.get('experience', []):
                # ... (existing code for month_to_number, etc.)

                fecha_inicio = None
                try:
                    start_year = exp_data.get('start_year')
                    start_month = exp_data.get('start_month')
                    if start_year and start_month:
                        start_month_num = month_to_number.get(start_month)
                        if start_month_num:
                            fecha_inicio = date(int(start_year), int(start_month_num), 1)
                except (ValueError, TypeError):
                    pass # Let validation handle the error, but prevent crash here

                fecha_termino = None
                if not (exp_data.get('current_job') == 'on' or exp_data.get('current_job') is True):
                    try:
                        end_year = exp_data.get('end_year')
                        end_month = exp_data.get('end_month')
                        if end_year and end_month:
                            end_month_num = month_to_number.get(end_month)
                            if end_month_num:
                                fecha_termino = date(int(end_year), int(end_month_num), 1)
                    except (ValueError, TypeError):
                        pass # Let validation handle the error, but prevent crash here

                horas_practica_value = None
                is_internship_bool = exp_data.get('is_internship') == 'on' or exp_data.get('is_internship') is True
                if is_internship_bool and exp_data.get('total_hours'):
                    try:
                        horas_practica_value = int(exp_data.get('total_hours'))
                    except ValueError:
                        horas_practica_value = None

                ExperienciaLaboralCV.objects.create(
                    cv_creado=cv_creado,
                    cargo_puesto=exp_data.get('position'),
                    empresa=exp_data.get('company'),
                    ubicacion=exp_data.get('location'),
                    fecha_inicio=fecha_inicio, # Use date object or None
                    fecha_termino=fecha_termino, # Use date object or None
                    trabajo_actual=exp_data.get('current_job') == 'on' or exp_data.get('current_job') is True,
                    practica=is_internship_bool,
                    horas_practica=horas_practica_value,
                    descripcion_cargo=exp_data.get('description')
                )

            # Education
            for edu_data in cv_data.get('education', []):
                EducacionCV.objects.create(
                    cv_creado=cv_creado,
                    institucion=edu_data.get('institution'),
                    carrera_titulo_nivel=edu_data.get('degree'),
                    fecha_inicio=f"{edu_data.get('start_year')}-01-01",
                    fecha_termino=f"{edu_data.get('end_year')}-01-01" if not edu_data.get('currently_studying') else None,
                    cursando=edu_data.get('currently_studying') == 'on' or edu_data.get('currently_studying') is True,
                    comentarios=edu_data.get('notes')
                )
                                # Skills
            for skill_type, skills in cv_data.get('skills', {}).items():
                for skill_text in skills:
                    HabilidadCV.objects.create(
                        cv_creado=cv_creado,
                        tipo_habilidad=skill_type,
                        texto_habilidad=skill_text
                    )

            # Languages
            for lang_data in cv_data.get('languages', []):
                IdiomaCV.objects.create(
                    cv_creado=cv_creado,
                    nombre_idioma=lang_data.get('language'),
                    nivel_idioma=lang_data.get('level')
                )

            # Certifications
            for cert_data in cv_data.get('certifications', []):
                CertificacionesCV.objects.create(
                    cv_creado=cv_creado,
                    nombre_certificacion=cert_data.get('cert_name'),
                    entidad_emisora=cert_data.get('issuer'),
                    fecha_obtencion=f"{cert_data.get('year')}-01-01"
                )

            # Projects
            for proj_data in cv_data.get('projects', []):
                ProyectosCV.objects.create(
                    cv_creado=cv_creado,
                    nombre_proyecto=proj_data.get('project_name'),
                    fecha_proyecto=proj_data.get('period'), # This might need adjustment if 'period' is not a date
                    rol_participacion=proj_data.get('role'),
                    descripcion_proyecto=proj_data.get('description'),
                    url_proyecto=proj_data.get('link')
                )

            # Volunteering
            for vol_data in cv_data.get('volunteering', []):
                VoluntariadoCV.objects.create(
                    cv_creado=cv_creado,
                    nombre_organizacion=vol_data.get('organization'),
                    puesto_rol=vol_data.get('role'),
                    descripcion_actividades=vol_data.get('description'),
                    ciudad=vol_data.get('city'),
                    pais=vol_data.get('country'),
                    region_estado_provincia=vol_data.get('region'),
                    fecha_inicio=vol_data.get('start_date'),
                    fecha_termino=vol_data.get('end_date'),
                    actualmente_activo=vol_data.get('current') == 'on' or vol_data.get('current') == True
                )

            # References
            for ref_data in cv_data.get('references', []):
                ReferenciasCV.objects.create(
                    cv_creado=cv_creado,
                    nombre_referente=ref_data.get('name'),
                    cargo_referente=ref_data.get('position'),
                    telefono=ref_data.get('phone'),
                    email=ref_data.get('email'),
                    url_linkedin=ref_data.get('linkedin_url')
                )

            next_url = data.get('next_url')
            redirect_to = next_url or reverse('perfiles_profesionales')
            return JsonResponse({'status': 'success', 'message': 'CV guardado exitosamente.', 'redirect_url': redirect_to})

        except CVCandidato.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Candidato no encontrado.'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Formato JSON inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

@login_required
def download_cv_pdf(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        html_content = data.get('html_content', '')

        # Path to the CSS file
        css_file_path = os.path.join(django_settings.BASE_DIR, 'JFlex', 'static', 'CSS', 'style.css')
        
        css_content = ''
        try:
            with open(css_file_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        except FileNotFoundError:
            # Handle case where CSS file is not found, maybe log this
            pass

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                {css_content}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(full_html)
            pdf_bytes = page.pdf(
                format="A4",
                margin={
                    "top": "50px",
                    "bottom": "50px",
                    "left": "50px",
                    "right": "50px"
                }
            )
            browser.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="cv_jobflex.pdf"'
        return response

    return HttpResponse("Invalid request method.", status=405)

@login_required
def download_s3_cv(request, cv_id):
    from django.shortcuts import get_object_or_404
    import boto3
    from django.conf import settings as django_settings
    from urllib.parse import urlparse

    cv_subido = get_object_or_404(CVSubido, id_cv_subido=cv_id, id_cv_subido__candidato__id_candidato=request.user)
    s3_url = cv_subido.ruta_archivo

    # Extract object key from S3 URL
    parsed_url = urlparse(s3_url)
    object_key = parsed_url.path.lstrip('/')
    file_name = os.path.basename(object_key) # Get original filename from S3 key

    s3 = boto3.client(
        's3',
        aws_access_key_id=django_settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=django_settings.AWS_SECRET_ACCESS_KEY,
        region_name=django_settings.AWS_S3_REGION_NAME # Ensure region is set
    )

    try:
        s3_object = s3.get_object(Bucket=django_settings.AWS_STORAGE_BUCKET_NAME, Key=object_key)
        file_content = s3_object['Body'].read()
        content_type = s3_object['ContentType'] # Get content type from S3

        response = HttpResponse(file_content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    except s3.exceptions.NoSuchKey:
        messages.error(request, "El archivo no se encontró en el almacenamiento.")
        return redirect('perfiles_profesionales')
    except Exception as e:
        messages.error(request, f"Error al descargar el archivo: {e}")
        return redirect('perfiles_profesionales')

@login_required
def settings(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('settings')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'user/settings.html', {
        'form': form
    })

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        if not user.check_password(request.POST.get('password')):
            messages.error(request, 'Contraseña incorrecta.')
            return redirect('settings')

        try:
            # Primero, eliminar todos los objetos relacionados en la base de datos 'jflex_db'
            with transaction.atomic(using='jflex_db'):
                # Usamos .filter().delete() que es más seguro si el objeto no existe
                RegistroUsuarios.objects.using('jflex_db').filter(id_registro=user).delete()
                Candidato.objects.using('jflex_db').filter(id_candidato=user).delete()
                EmpresaUsuario.objects.using('jflex_db').filter(id_empresa_user=user).delete()

            # Segundo, realizar un "soft delete" en la base de datos 'default'
            with transaction.atomic(using='default'):
                user.is_active = False
                # Anonimizar datos para permitir que se vuelvan a usar en el futuro
                user.email = f"deleted_{user.id}_{user.email}"
                user.username = f"deleted_{user.id}_{user.username}"
                user.save()

            logout(request)
            messages.success(request, 'Tu cuenta ha sido desactivada y eliminada permanentemente.')
            return redirect('index')

        except Exception as e:
            messages.error(request, f'Ocurrió un error al eliminar tu cuenta: {e}')
            return redirect('settings')

    return redirect('settings')

class CustomLoginView(auth_views.LoginView):
    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        
        try:
            trusted_user = self.request.get_signed_cookie('trusted_device', default=None, salt='jobflex-2fa-salt')
            if trusted_user == user.username:
                login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
                return super().form_valid(form)
        except (KeyError, BadSignature):
            pass

        try:
            registro_usuario = RegistroUsuarios.objects.using('jflex_db').get(id_registro=user)
            if registro_usuario.autenticacion_dos_factores_activa:
                self.request.session['2fa_user_pk'] = user.pk
                
                code = str(random.randint(100000, 999999))
                self.request.session['2fa_code'] = code
                self.request.session['2fa_code_expiry'] = (timezone.now() + timedelta(minutes=5)).isoformat()

                send_verification_email(
                    user.email,
                    code,
                    f'Tu código de inicio de sesión para JobFlex es {code}',
                    'registration/2fa_login_code_email.html'
                )
                
                return redirect('verify_2fa')
        except RegistroUsuarios.DoesNotExist:
            pass

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return super().form_valid(form)
@login_required
def edit_cv_meta(request, cv_id):
    try:
        cv_instance = CVCandidato.objects.get(id_cv_user=cv_id, candidato__id_candidato=request.user)
    except CVCandidato.DoesNotExist:
        messages.error(request, "No se encontró el CV o no tienes permiso para editarlo.")
        return redirect('profile')

    if request.method == 'POST':
        form = CVCandidatoForm(request.POST, instance=cv_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "La información principal del CV ha sido actualizada.")
            return redirect('profile')
        else:
            # Si hay errores, es difícil mostrarlos en el modal directamente.
            # Por ahora, solo mostraremos un error genérico.
            messages.error(request, "Hubo un error al actualizar la información. Por favor, inténtalo de nuevo.")
    
    return redirect('profile') # Redirigir si no es POST

from django.contrib.auth import login as auth_login # Import auth_login

@transaction.atomic
def accept_company_invitation(request, token):
    try:
        invitation_token_obj = CompanyInvitationToken.objects.using('jflex_db').get(token=token)
    except CompanyInvitationToken.DoesNotExist:
        messages.error(request, "El enlace de invitación es inválido o ha expirado.")
        return redirect('index') # Or a dedicated error page

    user = invitation_token_obj.user # This user is from default DB
    company = invitation_token_obj.company # This company is from jflex_db

    if not invitation_token_obj.is_valid() or user.is_active:
        messages.error(request, "El enlace de invitación es inválido o ya ha sido utilizado.")
        invitation_token_obj.delete() # Invalidate token
        return redirect('index')

    if request.method == 'POST':
        form = SetInvitationPasswordForm(user, request.POST)
        if form.is_valid():
            form.save() # Saves password and first/last name to the User object in default DB
            user.is_active = True
            user.save() # Activates user in default DB

            # Create RegistroUsuarios entry for the newly activated user
            # Get or create the 'empresa' TipoUsuario
            print(f"Attempting to get or create TipoUsuario 'empresa' for user {user.email}...")
            tipo_usuario_empresa, created_tipo = TipoUsuario.objects.using('jflex_db').get_or_create(nombre_user='empresa')
            print(f"TipoUsuario 'empresa' retrieved/created: {tipo_usuario_empresa.nombre_user}, created: {created_tipo}")

            try:
                print(f"Attempting to create RegistroUsuarios for user {user.email} (ID: {user.id})...")
                RegistroUsuarios.objects.using('jflex_db').create(
                    id_registro=user,
                    nombres=user.first_name,
                    apellidos=user.last_name,
                    email=user.email,
                    tipo_usuario=tipo_usuario_empresa
                )
                print(f"RegistroUsuarios created successfully for user {user.email}.")
            except Exception as e:
                print(f"ERROR: Failed to create RegistroUsuarios for user {user.email}: {e}")
                # Re-raise the exception to ensure the transaction rolls back if this fails
                raise

            invitation_token_obj.delete() # Delete token from jflex_db

            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"¡Bienvenido a {company.nombre_comercial}! Tu cuenta ha sido activada.")
            return redirect('company_index') # Redirect to company dashboard
        else:
            messages.error(request, "Por favor, corrige los errores en el formulario.")
    else:
        form = SetInvitationPasswordForm(user)

    context = {
        'form': form,
        'company_name': company.nombre_comercial,
        'invited_email': user.email,
    }
    return render(request, 'company/accept_invitation.html', context)

def job_offers(request: HttpRequest):
    q = request.GET.get('q', '').lower()
    region_id = request.GET.get('region', '')
    ciudad_id = request.GET.get('ciudad', '')
    mode = request.GET.get('mode', '')
    time_str = request.GET.get('time', '')

    ofertas_query = OfertaLaboral.objects.select_related("empresa", "jornada", "modalidad", "ciudad__region")

    # Apply keyword search
    if q:
        search_terms = q.split()
        keyword_query = Q()
        for term in search_terms:
            keyword_query |= (
                Q(titulo_puesto__icontains=term) |
                Q(descripcion_puesto__icontains=term) |
                Q(empresa__nombre_comercial__icontains=term) |
                Q(habilidades_clave__icontains=term)
            )
        ofertas_query = ofertas_query.filter(keyword_query)

    # Apply modality filter
    if mode:
        try:
            mode_int = int(mode)
            if mode_int > 0:
                ofertas_query = ofertas_query.filter(modalidad_id=mode_int)
        except ValueError:
            pass

    # Apply time (jornada) filter for multiple values
    if time_str:
        try:
            time_values = [int(t) for t in time_str.split(',') if t.isdigit()]
            if time_values:
                ofertas_query = ofertas_query.filter(jornada_id__in=time_values)
        except (ValueError, TypeError):
            pass

    # Apply location filters
    if region_id:
        try:
            region_obj = Region.objects.get(pk=region_id)
            if region_obj.nombre != 'Cualquier Región':
                ofertas_query = ofertas_query.filter(ciudad__region=region_obj)
                
                if ciudad_id:
                    try:
                        ciudad_obj = Ciudad.objects.get(pk=ciudad_id)
                        if ciudad_obj.nombre != 'Cualquier comuna':
                            ofertas_query = ofertas_query.filter(ciudad=ciudad_obj)
                    except Ciudad.DoesNotExist:
                        pass
        except Region.DoesNotExist:
            pass

    ofertas = ofertas_query.order_by('-fecha_publicacion')
    
    paginator = Paginator(ofertas, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_regions = Region.objects.all().order_by('nombre')
    selected_region_obj = None
    selected_ciudad_obj = None

    if region_id:
        try:
            selected_region_obj = Region.objects.get(pk=region_id)
        except Region.DoesNotExist:
            pass
    
    if ciudad_id:
        try:
            selected_ciudad_obj = Ciudad.objects.get(pk=ciudad_id)
        except Ciudad.DoesNotExist:
            pass

    ctx = {
      'page_obj': page_obj,
      'search_params': {
        'q': q,
        'region_id': region_id,
        'ciudad_id': ciudad_id,
        'mode': mode,
        'time': time_str
      },
      'all_regions': all_regions,
      'selected_region': selected_region_obj,
      'selected_ciudad': selected_ciudad_obj,
      'ofertas': ofertas
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render(request, 'offers/partials/_job_paginator.html', ctx).content.decode('utf-8')
        return JsonResponse({'html': html})
    return render(request, 'offers/job_offers.html', ctx)

def job_details(request: HttpRequest,id_oferta:int):
    oferta=get_object_or_404(OfertaLaboral,pk=int(id_oferta))

    # --- Track view count ---
    viewed_offers = request.session.get('viewed_offers', [])
    if id_oferta not in viewed_offers:
        oferta.vistas = F('vistas') + 1
        oferta.save(update_fields=['vistas'])
        oferta.refresh_from_db()
        viewed_offers.append(id_oferta)
        request.session['viewed_offers'] = viewed_offers
    # --- End Track view count ---

    skills = json.loads(oferta.habilidades_clave)
    skills = [s["value"] for s in skills]
    boons= json.loads(oferta.beneficios)
    boons = [s["value"] for s in boons]

    has_applied = False
    if request.user.is_authenticated:
        # Check if the user is a candidate before querying for profile
        if hasattr(request.user, 'candidato_profile'):
            try:
                candidato = request.user.candidato_profile
                if Postulacion.objects.filter(oferta=oferta, candidato=candidato).exists():
                    has_applied = True
            except Candidato.DoesNotExist:
                # This case should ideally not be reached if hasattr check is robust
                pass
    
    ctx={
      'oferta':oferta,
      'habilidad':skills,
      'beneficios':boons,
      'has_applied': has_applied
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'offers/partials/_job_details.html', ctx)
        
    return render(request ,'offers/job_details_page.html',ctx)

def company_profile(request, company_id):
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    company = get_object_or_404(Empresa, pk=company_id)
    
    # Get active job offers for this company
    ofertas_list = OfertaLaboral.objects.filter(
        empresa=company,
        estado='activa'
    ).select_related('jornada', 'modalidad', 'ciudad').order_by('-fecha_publicacion')
    
    paginator = Paginator(ofertas_list, 5) # Show 5 offers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Check for incomplete profile
    profile_incomplete = False
    required_fields = [
        'resumen_empresa', 'mision', 'vision', 'telefono', 
        'sitio_web', 'imagen_portada', 'imagen_perfil', 'rubro', 'ciudad'
    ]
    if any(not getattr(company, field) for field in required_fields):
        profile_incomplete = True

    # Pass the form for the modal
    company_data_form = EmpresaDataForm(instance=company, prefix="modal")
    
    # Manually serialize rubros to ensure it's a JSON array string
    all_rubros_qs = RubroIndustria.objects.all()
    rubros_list = list(all_rubros_qs.values('pk', 'nombre_rubro'))
    all_rubros_json = json.dumps(rubros_list)

    # Determine if the logged-in user can edit this profile
    can_edit = False
    if request.user.is_authenticated:
        try:
            # Check if the logged-in user is associated with THIS company and has an admin role
            empresa_usuario = EmpresaUsuario.objects.select_related('rol').get(id_empresa_user=request.user)
            if empresa_usuario.empresa == company:
                user_role = empresa_usuario.rol.nombre_rol
                if user_role in ['Representante', 'Administrador']:
                    can_edit = True
        except EmpresaUsuario.DoesNotExist:
            pass # User is not a company user, so can_edit remains False

    context = {
        'empresa': company,
        'page_obj': page_obj, # Pass the page object instead of the full list
        'total_ofertas': ofertas_list.count(),
        'profile_incomplete': profile_incomplete,
        'company_data_form': company_data_form, # Add form to context
        'all_rubros_json': all_rubros_json,
        'can_edit': can_edit,
    }
    return render(request, 'company/company_profile.html', context)

def terms_and_conditions(request):
    """Renderiza la página de Términos y Condiciones."""
    return render(request, 'static_pages/terms.html')

def privacy_policy(request):
    """Renderiza la página de Política de Privacidad."""
    return render(request, 'static_pages/privacy.html')

def about_us(request):
    """Renderiza la página 'Sobre Nosotros'."""
    return render(request, 'static_pages/about.html')

def contact_us(request):
    """Renderiza la página de Contacto."""
    return render(request, 'static_pages/contact.html')

@login_required
def apply_to_offer(request, offer_id):
    offer = get_object_or_404(OfertaLaboral, pk=offer_id)
    candidato = get_object_or_404(Candidato, pk=request.user.pk)

    # Check for profile completeness
    profile_is_complete = all([
        candidato.rut_candidato, 
        candidato.fecha_nacimiento, 
        candidato.telefono, 
        candidato.ciudad_id
    ])

    if not profile_is_complete:
        return JsonResponse({
            'error': 'incomplete_profile',
            'message': 'Por favor, completa tu perfil antes de postular.',
            'redirect_url': reverse('profile')
        }, status=400)

    # Check if already applied
    if Postulacion.objects.filter(oferta=offer, candidato=candidato).exists():
        return JsonResponse({
            'error': 'already_applied',
            'message': 'Ya has postulado a esta oferta.'
        }, status=400)

    if request.method == 'POST':
        selected_cv_id = request.POST.get('selected_cv')
        if not selected_cv_id:
            return JsonResponse({'error': 'cv_not_selected', 'message': 'Debes seleccionar un CV.'}, status=400)

        try:
            selected_cv = CVCandidato.objects.get(pk=selected_cv_id, candidato=candidato)
            
            Postulacion.objects.create(
                oferta=offer,
                candidato=candidato,
                cv_postulado=selected_cv,
                estado_postulacion='enviada'
            )
            
            return JsonResponse({'success': True, 'message': '¡Postulación enviada con éxito!'})

        except CVCandidato.DoesNotExist:
            return JsonResponse({'error': 'cv_not_found', 'message': 'El CV seleccionado no es válido.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'unknown_error', 'message': str(e)}, status=500)

    # GET request
    user_cvs = CVCandidato.objects.filter(candidato=candidato).order_by('-id_cv_user')
    
    # If user has no CVs, redirect them to create one, passing the offer URL
    if not user_cvs.exists():
        create_cv_url = reverse('create_cv')
        # Construct the full URL to the current job offer page to be used as 'next'
        offer_url = request.build_absolute_uri(reverse('job_offers')) + f'?oferta={offer.id_oferta}'
        return JsonResponse({
            'error': 'no_cv',
            'message': 'No tienes CVs. Debes crear uno para poder postular.',
            'redirect_url': f'{create_cv_url}?next={offer_url}'
        }, status=400)

    context = {
        'offer': offer,
        'cvs': user_cvs,
        'candidato': candidato,
    }
    
    modal_html = render_to_string('offers/partials/_apply_modal.html', context, request=request)
    
    return JsonResponse({'html': modal_html})

@login_required
def update_profile_from_modal(request):
    if request.method != 'POST' or not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'bad_request', 'message': 'Método no permitido.'}, status=405)

    candidato = get_object_or_404(Candidato, pk=request.user.pk)
    form = CompletarPerfilForm(request.POST, instance=candidato)

    if form.is_valid():
        form.save()
        # Return the updated data to refresh the modal view
        updated_data = {
            'full_name': request.user.get_full_name(),
            'rut': candidato.rut_candidato,
            'telefono': candidato.telefono,
            'ubicacion': str(candidato.ciudad) if candidato.ciudad else "No ingresada"
        }
        return JsonResponse({'success': True, 'message': 'Perfil actualizado.', 'updated_data': updated_data})
    else:
        return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

@login_required
def get_profile_edit_form_html(request):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponse("Bad Request", status=400)
        
    candidato = get_object_or_404(Candidato, pk=request.user.pk)
    form = CompletarPerfilForm(instance=candidato)
    
    form_html = render_to_string('offers/partials/_edit_profile_form_modal.html', {'form': form}, request=request)
    
    return JsonResponse({'html': form_html})

@login_required
def upload_cv_from_modal(request):
    if request.method != 'POST' or not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'bad_request', 'message': 'Método no permitido.'}, status=405)

    candidato = get_object_or_404(Candidato, pk=request.user.pk)
    form = CVSubidoForm(request.POST, request.FILES)

    if form.is_valid():
        file = form.cleaned_data['cv_file']
        nombre_cv = form.cleaned_data['nombre_cv']
        cargo_asociado = form.cleaned_data['cargo_asociado']

        username = request.user.username
        filename = f"{uuid.uuid4().hex[:8]}_{file.name}"
        s3_key = f"CVs/{username}/{filename}"

        try:
            file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)

            cv_candidato = CVCandidato.objects.create(
                candidato=candidato,
                nombre_cv=nombre_cv,
                cargo_asociado=cargo_asociado,
                tipo_cv='subido'
            )
            
            CVSubido.objects.create(
                id_cv_subido=cv_candidato,
                ruta_archivo=file_url
            )
            
            return JsonResponse({
                'success': True,
                'message': 'CV subido exitosamente.',
                'cv': {
                    'id_cv_user': cv_candidato.id_cv_user,
                    'nombre_cv': cv_candidato.nombre_cv,
                    'cargo_asociado': cv_candidato.cargo_asociado,
                    'tipo_cv': cv_candidato.tipo_cv
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al subir el CV a S3: {str(e)}'}, status=500)
    else:
        return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
# Helper function to create notifications
def crear_notificacion(usuario_destino_obj, tipo_notificacion_nombre, mensaje_str, link_relacionado_str=None, motivo_str=None):
    # Get or create TipoNotificacion
    tipo_notificacion_obj, created = TipoNotificacion.objects.get_or_create(
        nombre_tipo=tipo_notificacion_nombre,
        defaults={'descripcion': tipo_notificacion_nombre} # Default description
    )

    # Create Notificaciones object
    notificacion_base = Notificaciones.objects.create(
        usuario_destino=usuario_destino_obj,
        tipo_notificacion=tipo_notificacion_obj,
        mensaje=mensaje_str,
        link_relacionado=link_relacionado_str,
    )

    # Create specialized notification based on user type
    # Assuming usuario_destino_obj is a User instance
    try:
        # Check if the user is a Candidate
        candidato_profile = Candidato.objects.filter(id_candidato=usuario_destino_obj).first()
        if candidato_profile:
            NotificacionCandidato.objects.create(
                id_notificacion_candidato=notificacion_base,
                motivo=motivo_str if motivo_str else tipo_notificacion_nombre
            )
            return
    except Candidato.DoesNotExist:
        pass # Not a candidate, check for employer

    try:
        # Check if the user is an Employer (EmpresaUsuario)
        empresa_profile = EmpresaUsuario.objects.filter(id_empresa_user=usuario_destino_obj).first()
        if empresa_profile:
            NotificacionEmpresa.objects.create(
                id_notificacion_empresa=notificacion_base,
                motivo=motivo_str if motivo_str else tipo_notificacion_nombre
            )
            return
    except EmpresaUsuario.DoesNotExist:
        pass # Not an employer
    
    # If no specialized notification is created, log a warning or handle as needed
    print(f"WARNING: No specialized notification created for user {usuario_destino_obj.username}")
@login_required
@require_POST
def mark_all_as_read(request):
    try:
        registro_usuario = RegistroUsuarios.objects.get(id_registro=request.user)

        all_notifications_qs = Notificaciones.objects.filter(
            usuario_destino=request.user,
            leida=False
        )

        # Filter by specialized notification types based on user's role
        if registro_usuario.tipo_usuario and registro_usuario.tipo_usuario.nombre_user == 'candidato':
            notifications_to_mark = all_notifications_qs.filter(
                notificacioncandidato__isnull=False
            )
        elif registro_usuario.tipo_usuario and registro_usuario.tipo_usuario.nombre_user == 'empresa':
            notifications_to_mark = all_notifications_qs.filter(
                notificacionempresa__isnull=False
            )
        else:
            notifications_to_mark = all_notifications_qs.none()
        
        count = notifications_to_mark.update(leida=True)
        messages.success(request, f"{count} notificaciones han sido marcadas como leídas.")
    except RegistroUsuarios.DoesNotExist:
        messages.error(request, "No se encontró tu perfil de registro.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error al marcar las notificaciones: {e}")
    
    # Redirect to the previous page or a fallback
    return redirect(request.META.get('HTTP_REFERER', '/'))
@login_required
@require_POST
def delete_all_notifications(request):
    try:
        Notificaciones.objects.filter(usuario_destino=request.user).delete()
        messages.success(request, "Todas tus notificaciones han sido eliminadas.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error al eliminar las notificaciones: {e}")
    
    return redirect(request.META.get('HTTP_REFERER', '/'))
import re
import os
import json
from urllib.parse import urlparse
import uuid
import boto3
from django.conf import settings as django_settings
 # Added here

from datetime import datetime, date, timedelta # Added here
import random

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash, logout
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model # Use get_user_model
User = get_user_model() # Define User globally
from django.db import transaction # Add this line
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse # Import reverse here
from playwright.sync_api import sync_playwright

# ... (rest of the imports)

# 1. Importar los formularios y modelos necesarios y limpios
from .forms import SignUpForm, VerificationForm, CandidatoForm, CVCandidatoForm, CompletarPerfilForm, InvitationForm, SetInvitationPasswordForm, CVSubidoForm
from .models import CompanyInvitationToken, TipoUsuario, RegistroUsuarios, Candidato, EmpresaUsuario, Empresa, RolesEmpresa, CVCandidato, CVCreado, CVSubido, DatosPersonalesCV, ObjetivoProfesionalCV, EducacionCV, ExperienciaLaboralCV, CertificacionesCV, HabilidadCV, IdiomaCV, ProyectosCV, ReferenciasCV, VoluntariadoCV, Postulacion, Entrevista, ModoOnline, ModoPresencial, TipoNotificacion, Notificaciones, NotificacionCandidato, NotificacionEmpresa, Ubicacion # Explicitly import models
from django.http import JsonResponse, HttpResponse

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

            mail_subject = f'Tu código de activación para JobFlex es {code}'
            message = render_to_string('registration/code_email.html', {'code': code})
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()
            
            return redirect('verify_code')
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

def index(req):
    if req.user.is_authenticated:
        return redirect('user_index')
    return render(req, 'index.html')

def upload_to_s3(file, bucket_name, object_key):
    s3 = boto3.client(
        's3',
        aws_access_key_id=django_settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=django_settings.AWS_SECRET_ACCESS_KEY,
    )
    s3.upload_fileobj(file, bucket_name, object_key, ExtraArgs={
        'ContentType': file.content_type
    })
    # La URL del objeto no cambia en su formato base
    file_url = f"https://{bucket_name}.s3.{django_settings.AWS_S3_REGION_NAME}.amazonaws.com/{object_key}"
    return file_url

@login_required
def user_index(request):
    try:
        registro = RegistroUsuarios.objects.get(id_registro=request.user)
        
        if registro.tipo_usuario and registro.tipo_usuario.nombre_user == 'candidato':
            candidato = request.user.candidato_profile
            show_modal = not all([candidato.rut_candidato, candidato.fecha_nacimiento, candidato.telefono, candidato.ubicacion_id])
            
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
                        
                        # Construir la nueva ruta del objeto para S3
                        username = request.user.username
                        filename = f"{uuid.uuid4().hex[:8]}_{file.name}"
                        s3_key = f"CVs/{username}/{filename}"

                        # Subida manual a S3 con la nueva ruta
                        file_url = upload_to_s3(file, django_settings.AWS_STORAGE_BUCKET_NAME, s3_key)

                        # Crear CVCandidato
                        cv_candidato = CVCandidato.objects.create(
                            candidato=candidato,
                            nombre_cv=cv_subido_form.cleaned_data['nombre_cv'],
                            cargo_asociado=cv_subido_form.cleaned_data['cargo_asociado'],
                            tipo_cv='subido'
                        )
                        
                        # Crear CVSubido con la URL de S3
                        CVSubido.objects.create(
                            id_cv_subido=cv_candidato,
                            ruta_archivo=file_url
                        )
                        
                        messages.success(request, "Tu CV ha sido subido y organizado exitosamente en S3.")
                        return redirect('user_index')

            context = {
                'show_modal': show_modal, 
                'form': completar_perfil_form,
                'cv_subido_form': cv_subido_form
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


from django.core.serializers.json import DjangoJSONEncoder

@login_required
def Profile(request):
    try:
        candidato = Candidato.objects.get(id_candidato=request.user)
    except Candidato.DoesNotExist:
        messages.error(request, "Perfil de candidato no encontrado.")
        return redirect('user_index')

    if request.method == 'POST':
        # Diferenciar entre los formularios
        if 'submit_profile' in request.POST:
            form = CandidatoForm(request.POST, instance=candidato)
            if form.is_valid():
                form.save()
                messages.success(request, "¡Tu perfil ha sido actualizado con éxito!")
                return redirect('profile')
        
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
                
                messages.success(request, "Tu CV ha sido subido exitosamente.")
                return redirect('profile')
    else:
        form = CandidatoForm(instance=candidato)
        cv_subido_form = CVSubidoForm()

    # --- Lógica de serialización de CVs para la vista previa ---
    cvs_qs = CVCandidato.objects.filter(candidato=candidato).select_related('cvcreado', 'cvsubido')
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

        cv_list.append(cv_item)

    # Calcular edad
    today = date.today()
    age = today.year - candidato.fecha_nacimiento.year - ((today.month, today.day) < (candidato.fecha_nacimiento.month, candidato.fecha_nacimiento.day))

    # Lógica para determinar si se muestra el modal
    show_profile_modal = not candidato.rut_candidato or not candidato.telefono

    context = {
        'form': form,
        'candidato': candidato,
        'age': age,
        'show_profile_modal': show_profile_modal,
        'cv_list': cv_list,
        'cv_subido_form': cv_subido_form
    }
    return render(request, 'user/profile.html', context)

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

def get_ciudades(request, region_nombre):
    ciudades = list(Ubicacion.objects.using('jflex_db').filter(region=region_nombre).values_list('ciudad', flat=True).distinct().order_by('ciudad'))
    return JsonResponse(ciudades, safe=False)

import uuid # Add this import at the top

# ... (rest of the imports)

from .forms import SignUpForm, VerificationForm, CandidatoForm, CVCandidatoForm, CompletarPerfilForm, InvitationForm, EmpresaDataForm
from .models import *
from django.http import JsonResponse

# ... (rest of the views)

@login_required
def company_index(request):
    # 1. Get the current user's company and role
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

        if action == 'update_company_data' and is_admin:
            company_data_form = EmpresaDataForm(request.POST, request.FILES, instance=company)
            if company_data_form.is_valid():
                company_data_form.save()
                messages.success(request, "Los datos de la empresa han sido actualizados.")
                return redirect('company_index')
            else:
                messages.error(request, "Error al actualizar los datos. Por favor, revisa el formulario.")
                # The form with errors will be passed in the context, but we need to handle it in the template

        elif action == 'invite_user' and is_admin: # Only admins can invite
            form = InvitationForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                role = form.cleaned_data['role'] # This is a RolesEmpresa object

                # Check if user already exists in Django's User model
                try:
                    invited_user = User.objects.get(email=email)
                    # Check if the user is already part of this company
                    if EmpresaUsuario.objects.filter(empresa=company, id_empresa_user=invited_user).exists():
                        messages.warning(request, f"El usuario {email} ya es parte de esta empresa.")
                    else:
                        # Link existing user to the company
                        EmpresaUsuario.objects.create(
                            id_empresa_user=invited_user,
                            empresa=company,
                            rol=role
                        )
                        messages.success(request, f"El usuario existente {email} ha sido añadido a la empresa como {role.nombre_rol}.")
                except User.DoesNotExist:
                    # User does not exist, create an inactive user and send invitation
                    # This part needs a proper invitation flow (e.g., email with a link to set password)
                    # For now, let's create an inactive user and link them.
                    # A more robust solution would involve a temporary token and a dedicated registration view.
                    
                    # Create a dummy username for the inactive user
                    username = f"temp_{uuid.uuid4().hex[:10]}"
                    new_user = User.objects.create_user(username=username, email=email, password="temporarypassword123")
                    new_user.is_active = False
                    new_user.first_name = "Invitado" # Placeholder
                    new_user.last_name = "Pendiente" # Placeholder
                    new_user.save()

                    EmpresaUsuario.objects.create(
                        id_empresa_user=new_user,
                        empresa=company,
                        rol=role
                    )
                    
                    # Generate invitation token
                    invitation_token = uuid.uuid4().hex
                    expires_at = timezone.now() + timedelta(days=1) # Token valid for 24 hours

                    CompanyInvitationToken.objects.using('jflex_db').create(
                        user_id=new_user.id, # Assign the user's ID, not the user object
                        company=company,
                        token=invitation_token,
                        expires_at=expires_at
                    )

                    # Construct invitation URL
                    invitation_link = request.build_absolute_uri(
                        reverse('accept_company_invitation', kwargs={'token': invitation_token})
                    )

                    # Send invitation email
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
                
                return redirect('company_index') # Redirect to refresh the page and show messages
            else:
                # Form is invalid, re-render with errors
                messages.error(request, "Error al invitar usuario. Por favor, revisa los datos.")
                # The form with errors will be passed to the context below
        
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
                # Prevent deleting the last admin/representative
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
    empresa_usuarios_qs = EmpresaUsuario.objects.using('jflex_db').filter(empresa=company).select_related('rol') # Removed .order_by('id_empresa_user__email')
    
    user_ids = [eu.id_empresa_user_id for eu in empresa_usuarios_qs]
    users_from_default = User.objects.using('default').filter(pk__in=user_ids)
    user_map = {user.pk: user for user in users_from_default}

    members_for_template = []
    for eu in empresa_usuarios_qs:
        user_obj = user_map.get(eu.id_empresa_user_id)
        if user_obj: # Ensure user exists
            members_for_template.append({
                'pk': eu.pk,
                'user_full_name': user_obj.get_full_name(),
                'user_email': user_obj.email,
                'role': eu.rol,
                'role_display': eu.rol.nombre_rol,
            })
    
    # Sort the list of dictionaries by user_email in Python
    members_for_template.sort(key=lambda x: x['user_email'])

    # Initialize forms for modals
    invitation_form = InvitationForm()
    company_data_form = EmpresaDataForm(instance=company)

    # If a specific form had an error on POST, we might need to replace the empty one
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'invite_user' and 'form' in locals() and not form.is_valid():
            invitation_form = form # Pass the form with errors back to the template
        elif action == 'update_company_data' and 'company_data_form' in locals() and not company_data_form.is_valid():
            # This form is already the one with errors, so no need to reassign
            pass


    context = {
        'company': company,
        'is_admin': is_admin,
        'members': members_for_template, # Use the list of dictionaries
        'invitation_form': invitation_form,
        'company_data_form': company_data_form,
        'user_role': user_role, # For displaying current user's role
    }
    return render(request, 'company/company_index.html', context)

@login_required
def postulaciones(request):
    return render(request, 'user/postulaciones.html')

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
    return render(request, 'user/create_cv.html')

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
    elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', personal_data.get('email', '')):
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
    def is_valid_date(year, month_name=None):
        try:
            if month_name:
                month_num = month_to_number.get(month_name)
                if not month_num:
                    return False
                date(int(year), int(month_num), 1)
            else:
                date(int(year), 1, 1)
            return True
        except ValueError:
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
        elif not is_valid_date(exp_data.get('start_year'), exp_data.get('start_month')):
            errors[prefix + 'start_date'] = 'Formato de fecha de inicio inválido.'

        if not (exp_data.get('current_job') == 'on' or exp_data.get('current_job') is True): # If not current job, end date is required
            if not exp_data.get('end_year') or not exp_data.get('end_month'):
                errors[prefix + 'end_date'] = 'La fecha de término es obligatoria si no es el trabajo actual.'
            elif not is_valid_date(exp_data.get('end_year'), exp_data.get('end_month')):
                errors[prefix + 'end_date'] = 'Formato de fecha de término inválido.'
            else:
                try:
                    start_date_obj = date(int(exp_data['start_year']), int(month_to_number[exp_data['start_month']]), 1)
                    end_date_obj = date(int(exp_data['end_year']), int(month_to_number[exp_data['end_month']]), 1)
                    if start_date_obj > end_date_obj:
                        errors[prefix + 'date_order'] = 'La fecha de inicio no puede ser posterior a la fecha de término.'
                except (ValueError, KeyError):
                    # Should be caught by is_valid_date, but as a fallback
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
        elif not is_valid_date(edu_data.get('start_year')):
            errors[prefix + 'start_year'] = 'Formato de año de inicio inválido.'

        if not (edu_data.get('currently_studying') == 'on' or edu_data.get('currently_studying') is True): # If not currently studying, end year is required
            if not edu_data.get('end_year'):
                errors[prefix + 'end_year'] = 'El año de término es obligatorio si no está cursando actualmente.'
            elif not is_valid_date(edu_data.get('end_year')):
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
        elif not is_valid_date(cert_data.get('year')):
            errors[prefix + 'year'] = 'Formato de año de obtención inválido.'

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
        elif not is_valid_date(cert_data.get('year')):
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
        # Assuming 'period' can be a year string or a more complex period string.
        # If it's strictly a year, validate as such. If it's a string, just check length.
        elif not is_valid_date(proj_data.get('period')) and not isinstance(proj_data.get('period'), str):
             errors[prefix + 'period'] = 'Formato de año o periodo de ejecución inválido.'
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

        if vol_data.get('region') and len(vol_data.get('region', '')) > 50:
            errors[prefix + 'region'] = 'La región/estado/provincia no puede exceder los 50 caracteres.'

        if not vol_data.get('start_date'):
            errors[prefix + 'start_date'] = 'La fecha de inicio es obligatoria.'
        else:
            try:
                datetime.strptime(vol_data['start_date'], '%Y-%m-%d').date()
            except ValueError:
                errors[prefix + 'start_date'] = 'Formato de fecha de inicio inválido (YYYY-MM-DD).'

        if not (vol_data.get('current') == 'on' or vol_data.get('current') is True):
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
        elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', ref_data.get('email', '')):
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

            return JsonResponse({'status': 'success', 'message': 'CV guardado exitosamente.', 'redirect_url': '/perfiles-profesionales/'})

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


def job_offers(request):
    return render(request, 'offers/job_offers.html')


def company_profile(request, company_id):
    from django.shortcuts import get_object_or_404
    company = get_object_or_404(Empresa, pk=company_id)
    context = {
        'empresa': company
    }
    return render(request, 'company/company_profile.html', context)


# --- El resto de las vistas se mantienen comentadas para ser implementadas después ---

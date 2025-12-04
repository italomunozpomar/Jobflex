from django.db import transaction
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import pre_social_login
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from JFlex.models import TipoUsuario, RegistroUsuarios, Candidato
from django.contrib.auth import get_user_model
import random
from JFlex.views import send_verification_email # Importar la función para enviar correos

User = get_user_model()

@receiver(user_signed_up)
@transaction.atomic
def social_login_profile_creation(sender, request, user, **kwargs):
    """
    Crea los perfiles de RegistroUsuarios y Candidato para un nuevo
    registro social, manteniendo la cuenta activa.
    """
    
    # Asegurarse de que el usuario no tenga ya un perfil en jflex_db
    if RegistroUsuarios.objects.using('jflex_db').filter(id_registro=user).exists():
        return

    try:
        # Usar una transacción para la base de datos jflex_db
        with transaction.atomic(using='jflex_db'):
            # 1. Obtener o crear el TipoUsuario 'candidato' por defecto
            tipo_usuario_candidato, _ = TipoUsuario.objects.get_or_create(nombre_user='candidato')

            # 2. Crear el RegistroUsuarios
            RegistroUsuarios.objects.create(
                id_registro=user,
                nombres=user.first_name or '',
                apellidos=user.last_name or '',
                email=user.email,
                tipo_usuario=tipo_usuario_candidato
            )

            # 3. Crear el perfil de Candidato
            Candidato.objects.create(
                id_candidato=user,
                rut_candidato='',
                fecha_nacimiento='1900-01-01',
                telefono='',
                ciudad=None
            )
        
        # El usuario permanece activo por defecto, según el flujo de allauth.
        print(f"DEBUG: Perfil de candidato creado para {user.email} (Social Login)")

    except Exception as e:
        print(f"ERROR: Fallo al crear perfil para el usuario {user.email} después del social login: {e}")

@receiver(pre_social_login)
def handle_social_login_2fa(sender, request, sociallogin, **kwargs):
    """
    Intercepta un social login para comprobar si el usuario tiene 2FA activado.
    Si es así, lo redirige a la página de verificación de 2FA en lugar de iniciar sesión.
    """
    user = sociallogin.user
    if not user.pk:
        # Es un usuario nuevo, la 2FA no puede estar activada todavía.
        return

    try:
        registro_usuario = RegistroUsuarios.objects.using('jflex_db').get(id_registro=user)
        if registro_usuario.autenticacion_dos_factores_activa:
            # Guardar los datos necesarios para la verificación 2FA en la sesión
            request.session['2fa_user_pk'] = user.pk
            
            code = str(random.randint(100000, 999999))
            request.session['2fa_code'] = code
            request.session['2fa_code_expiry'] = (timezone.now() + timedelta(minutes=5)).isoformat()

            # Enviar el código 2FA por correo
            send_verification_email(
                user.email,
                code,
                f'Tu código de inicio de sesión para JobFlex es {code}',
                'registration/2fa_login_code_email.html'
            )

            # Impedir que allauth complete el inicio de sesión y redirigir a nuestra página 2FA
            raise ImmediateHttpResponse(redirect(reverse('verify_2fa')))

    except RegistroUsuarios.DoesNotExist:
        # Este usuario no tiene un perfil en jflex_db, por lo que la 2FA no es aplicable.
        # Esto puede ocurrir en casos excepcionales o para superusuarios.
        pass

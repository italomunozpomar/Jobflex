from django.db import transaction
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
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
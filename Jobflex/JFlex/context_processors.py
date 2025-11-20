from .models import Notificaciones, NotificacionCandidato, NotificacionEmpresa, TipoUsuario
from django.db.models import Q

def notifications_processor(request):
    notifications_data = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }

    if request.user.is_authenticated:
        try:
            # Check user type
            registro_usuario = request.user.registrousuarios
            
            # Fetch generic notifications
            all_notifications_qs = Notificaciones.objects.filter(
                usuario_destino=request.user
            ).select_related('tipo_notificacion').order_by('-fecha_envio')

            # Filter by specialized notification types
            if registro_usuario.tipo_usuario and registro_usuario.tipo_usuario.nombre_user == 'candidato':
                # Only show notifications that have a corresponding NotificacionCandidato entry
                notifications_for_user = all_notifications_qs.filter(
                    notificacioncandidato__isnull=False
                )
            elif registro_usuario.tipo_usuario and registro_usuario.tipo_usuario.nombre_user == 'empresa':
                # Only show notifications that have a corresponding NotificacionEmpresa entry
                notifications_for_user = all_notifications_qs.filter(
                    notificacionempresa__isnull=False
                )
            else:
                notifications_for_user = all_notifications_qs.none() # No specialized notifications

            notifications_data['unread_notifications_count'] = notifications_for_user.filter(leida=False).count()
            
            # Fetch a few recent notifications for display
            for notif in notifications_for_user[:5]: # Limit to 5 recent notifications
                notifications_data['recent_notifications'].append({
                    'id': notif.id_notificacion,
                    'message': notif.mensaje,
                    'is_read': notif.leida,
                    'timestamp': notif.fecha_envio,
                    'link': notif.link_relacionado,
                    'type': notif.tipo_notificacion.nombre_tipo if notif.tipo_notificacion else 'General'
                })

        except RegistroUsuarios.DoesNotExist:
            # User might be authenticated but not have a RegistroUsuarios profile yet
            pass
        except Exception as e:
            # Log any other errors
            print(f"Error in notifications_processor: {e}")

    return notifications_data
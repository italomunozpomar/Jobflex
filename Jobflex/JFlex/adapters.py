from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
import random
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from .models import RegistroUsuarios

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).
        """
        # Ignore existing social accounts, just do this for new ones
        if sociallogin.is_existing:
            return

        # 'email' is a mandatory field for Google, so we can rely on it
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return

        User = get_user_model()
        try:
            # Check if a user with this email already exists
            user = User.objects.get(email=email)
            
            # If the user exists, connect this new social account to the existing user
            sociallogin.connect(request, user)
            
        except User.DoesNotExist:
            pass # If user does not exist, let the normal signup flow proceed

    def login(self, request, user):
        """
        Intercepts the login to check for 2FA requirements.
        """
        try:
            registro = RegistroUsuarios.objects.get(id_registro=user)
            if registro.autenticacion_dos_factores_activa:
                # Check trusted device cookie
                try:
                    trusted_user = request.get_signed_cookie('trusted_device', default=None, salt='jobflex-2fa-salt')
                    if trusted_user == user.username:
                        # Trusted device, allow login
                        super().login(request, user)
                        return
                except:
                    pass # If cookie check fails, proceed to 2FA

                # 2FA Required Logic
                request.session['2fa_user_pk'] = user.pk
                
                code = str(random.randint(100000, 999999))
                request.session['2fa_code'] = code
                request.session['2fa_code_expiry'] = (timezone.now() + timedelta(minutes=5)).isoformat()

                # Send Verification Email
                mail_subject = f'Tu código de inicio de sesión para JobFlex es {code}'
                message = render_to_string('registration/2fa_login_code_email.html', {'code': code})
                email = EmailMessage(mail_subject, message, to=[user.email])
                email.content_subtype = "html"
                email.send()

                # Interrupt login flow and redirect to verification page
                raise ImmediateHttpResponse(redirect('verify_2fa'))

        except RegistroUsuarios.DoesNotExist:
            pass # No profile found, proceed with normal login

        # Standard Login if no 2FA required
        super().login(request, user)

    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly signed up social login. Ensures the user is set to active.
        """
        user = sociallogin.user
        user.is_active = True  # Ensure the user is always active
        sociallogin.save(request)
        return user

    def populate_user(self, request, sociallogin, data):
        """
        Populates the user instance with data from the social provider.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Use email as username if available
        if sociallogin.account.extra_data.get('email'):
            user.username = sociallogin.account.extra_data['email']
        
        return user

    def populate_user(self, request, sociallogin, data):
        """
        Populates the user instance with data from the social provider.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Use email as username if available
        if sociallogin.account.extra_data.get('email'):
            user.username = sociallogin.account.extra_data['email']
        
        return user

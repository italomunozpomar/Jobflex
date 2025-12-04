from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

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

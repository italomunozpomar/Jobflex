from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly signed up social login. Ensures the user is set to active.
        """
        user = sociallogin.user
        user.is_active = True  # Ensure the user is always active
        sociallogin.save(request)
        return user

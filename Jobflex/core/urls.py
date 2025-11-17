"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from JFlex import views as jflex_views  # Importamos las vistas de la app JFlex
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap, OfertaLaboralSitemap, CompanyProfileSitemap
from django.contrib.staticfiles.urls import staticfiles_urlpatterns # Import this

sitemaps = {
    'static': StaticViewSitemap,
    'ofertas': OfertaLaboralSitemap,
    'empresas': CompanyProfileSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('JFlex.urls')),

    # Ruta para manejar la cancelación del login social
    path('accounts/social/login/cancelled/', jflex_views.social_login_cancelled, name='social_login_cancelled'),

    # Incluir las URLs de allauth
    path('accounts/', include('allauth.urls')),

    path("__reload__/", include("django_browser_reload.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve static files in development even when DEBUG is False
urlpatterns += staticfiles_urlpatterns()
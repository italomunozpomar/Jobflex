# core/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from JFlex.models import OfertaLaboral, Empresa

class StaticViewSitemap(Sitemap):
    """
    Sitemap for static pages.
    """
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        # These are the 'name' values from urls.py
        return [
            'index', 
            'job_offers',
            'about_us', 
            'contact_us', 
            'privacy_policy', 
            'terms_and_conditions',
            'validate'
        ]

    def location(self, item):
        return reverse(item)

class OfertaLaboralSitemap(Sitemap):
    """
    Sitemap for dynamic job offer pages.
    """
    changefreq = 'daily'
    priority = 1.0

    def items(self):
        # Index all offers that are currently active
        return OfertaLaboral.objects.filter(estado='activa') 

    def lastmod(self, obj):
        # Use the publication date
        return obj.fecha_publicacion 

    def location(self, obj):
        # The URL is named 'job_details' and takes 'id_oferta'
        return reverse('job_details', kwargs={'id_oferta': obj.pk})

class CompanyProfileSitemap(Sitemap):
    """
    Sitemap for public company profile pages.
    """
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        # Index all companies that have a profile image (as a proxy for being "public")
        return Empresa.objects.exclude(imagen_perfil__isnull=True).exclude(imagen_perfil='')

    def lastmod(self, obj):
        # Use the last modification date of the company profile
        return obj.ultima_modificacion

    def location(self, obj):
        # The URL is named 'company_profile' and takes 'company_id'
        return reverse('company_profile', kwargs={'company_id': obj.pk})
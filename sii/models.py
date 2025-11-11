from django.db import models

class EmpresaSII(models.Model):
    rut = models.IntegerField(
        help_text='RUT de la empresa sin el dígito verificador.'
    )
    dv = models.CharField(
        max_length=1, 
        help_text='Dígito verificador del RUT.'
    )
    razon_social = models.CharField(
        max_length=255, 
        help_text='Nombre o razón social de la empresa.'
    )
    rut_completo = models.CharField(
        max_length=12, 
        unique=True, 
        primary_key=True, 
        help_text='RUT completo con guión, ej: 12345678-9.'
    )

    class Meta:
        db_table = 'sii_empresas'
        verbose_name = 'Empresa SII'
        verbose_name_plural = 'Empresas SII'
        ordering = ['razon_social']

    def __str__(self):
        return f'{self.razon_social} ({self.rut_completo})'

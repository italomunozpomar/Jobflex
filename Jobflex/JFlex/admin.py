from django.contrib import admin
from .models import (
    RegistroUsuarios, Empresa, EmpresaUsuario, RolesEmpresa, Candidato, TipoUsuario,
    Jornada, Modalidad, Categoria, Postulacion
)
@admin.register(RegistroUsuarios)
class RegistroUsuariosAdmin(admin.ModelAdmin):
    list_display = ('id_registro_id', 'tipo_usuario', 'fecha_creacion', 'activo')
    list_filter = ('tipo_usuario', 'activo')
    search_fields = ('email', 'nombres', 'apellidos')
    raw_id_fields = ('id_registro',)

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre_comercial', 'rut_empresa', 'razon_social', 'rubro')
    search_fields = ('nombre_comercial', 'rut_empresa', 'razon_social')

@admin.register(EmpresaUsuario)
class EmpresaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_empresa_user_id', 'empresa', 'rol')
    search_fields = ('id_empresa_user__email', 'empresa__nombre_comercial')
    raw_id_fields = ('id_empresa_user', 'empresa', 'rol')

@admin.register(RolesEmpresa)
class RolesEmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre_rol', 'descripcion_rol')

@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ('id_candidato_id', 'rut_candidato', 'telefono', 'disponible')
    search_fields = ('id_candidato__email', 'rut_candidato')
    raw_id_fields = ('id_candidato',)

admin.site.register(TipoUsuario)
admin.site.register(Jornada)
admin.site.register(Modalidad)
admin.site.register(Categoria)
admin.site.register(Postulacion)
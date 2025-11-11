from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone # Import timezone

# ==============================================================================
# Modelos de Usuarios y Perfiles
# ==============================================================================

class TipoUsuario(models.Model):
    id_tipo_user = models.AutoField(primary_key=True)
    nombre_user = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre_user

class RegistroUsuarios(models.Model):
    # Este modelo parece un intento de un User model custom.
    # Lo ideal es usar el User de Django y extenderlo con perfiles.
    # Por ahora, lo mapeo directamente, pero recomiendo unificarlo con el User de Django.
    id_registro = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, db_constraint=False)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    contrasena = models.CharField(max_length=255) # Django maneja esto de forma segura, no almacenar aquí.
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    ultimo_ingreso = models.DateTimeField(null=True, blank=True)
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.SET_NULL, null=True, blank=True) # Relación inferida

class Candidato(models.Model):
    id_candidato = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='candidato_profile', db_constraint=False) # Relación inferida
    rut_candidato = models.CharField(max_length=15)
    fecha_nacimiento = models.DateField()
    telefono = models.CharField(max_length=20)
    disponible = models.BooleanField(default=True)
    linkedin_url = models.URLField(max_length=255, null=True, blank=True)
    ubicacion = models.ForeignKey('Ubicacion', on_delete=models.SET_NULL, null=True, blank=True) # Relación inferida

    def __str__(self):
        return f"Candidato: {self.id_candidato.get_full_name()}"

class EmpresaUsuario(models.Model):
    id_empresa_user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='empresa_profile', db_constraint=False) # Relación inferida
    empresa = models.ForeignKey('Empresa', on_delete=models.CASCADE) # Relación inferida
    rol = models.ForeignKey('RolesEmpresa', on_delete=models.SET_NULL, null=True) # Relación inferida

    def __str__(self):
        return f"{self.id_empresa_user.username} en {self.empresa.nombre_comercial}"

# ==============================================================================
# Modelos de Empresa y Ofertas
# ==============================================================================

class RubroIndustria(models.Model):
    id_rubro = models.AutoField(primary_key=True)
    nombre_rubro = models.CharField(max_length=50)
    descripcion_rubro = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre_rubro

class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    rut_empresa = models.CharField(max_length=20, unique=True)
    razon_social = models.CharField(max_length=150)
    nombre_comercial = models.CharField(max_length=150)
    resumen_empresa = models.TextField(max_length=1000)
    mision = models.TextField(max_length=500, null=True, blank=True)
    vision = models.TextField(max_length=500, null=True, blank=True)
    telefono = models.CharField(max_length=20)
    sitio_web = models.URLField(max_length=255, null=True, blank=True)
    imagen_portada = models.ImageField(upload_to='company_banners/', null=True, blank=True)
    imagen_perfil = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    ultima_modificacion = models.DateTimeField(auto_now=True)
    rubro = models.ForeignKey(RubroIndustria, on_delete=models.SET_NULL, null=True, blank=True) # Relación inferida
    ubicacion = models.ForeignKey('Ubicacion', on_delete=models.SET_NULL, null=True, blank=True) # Relación inferida

    def __str__(self):
        return self.nombre_comercial

class RolesEmpresa(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50)
    descripcion_rol = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre_rol

class CompanyInvitationToken(models.Model):
    user_id = models.BigIntegerField(unique=True) # Store user ID as a simple field
    company = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    @property
    def user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.using('default').get(pk=self.user_id)

    def __str__(self):
        # Access user via the property
        try:
            user_email = self.user.email
        except User.DoesNotExist:
            user_email = f"User ID {self.user_id} (not found)"
        return f"Invitation for {user_email} to {self.company.nombre_comercial}"

    class Meta:
        db_table = 'CompanyInvitationToken'
        app_label = 'JFlex' # Ensure it's managed by jflex_db
        managed = True

class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    tipo_categoria = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo_categoria

class Jornada(models.Model):
    id_jornada = models.AutoField(primary_key=True)
    tipo_jornada = models.CharField(max_length=50)

    def __str__(self):
        return self.tipo_jornada

class Modalidad(models.Model):
    id_modalidad = models.AutoField(primary_key=True)
    tipo_modalidad = models.CharField(max_length=50)

    def __str__(self):
        return self.tipo_modalidad

class OfertaLaboral(models.Model):
    id_oferta = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE) # Relación inferida
    titulo_puesto = models.CharField(max_length=150)
    descripcion_puesto = models.TextField(max_length=2000)
    requisitos_puesto = models.TextField(max_length=1000)
    habilidades_clave = models.CharField(max_length=500, null=True, blank=True)
    beneficios = models.CharField(max_length=500, null=True, blank=True)
    nivel_experiencia = models.CharField(max_length=50)
    salario_min = models.IntegerField()
    salario_max = models.IntegerField()
    fecha_publicacion = models.DateField(auto_now_add=True)
    fecha_cierre = models.DateField()
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True) # Relación inferida
    jornada = models.ForeignKey(Jornada, on_delete=models.SET_NULL, null=True) # Relación inferida
    modalidad = models.ForeignKey(Modalidad, on_delete=models.SET_NULL, null=True) # Relación inferida

    def __str__(self):
        return self.titulo_puesto

# ==============================================================================
# Modelos de CV (Curriculum Vitae)
# ==============================================================================

class CVCandidato(models.Model):
    # Tabla central que representa un CV
    id_cv_user = models.AutoField(primary_key=True)
    candidato = models.ForeignKey(Candidato, on_delete=models.CASCADE) # Relación inferida
    nombre_cv = models.CharField(max_length=100)
    cargo_asociado = models.CharField(max_length=100)
    tipo_cv = models.CharField(max_length=20) # 'creado' o 'subido'

    def __str__(self):
        return f"{self.nombre_cv} ({self.candidato})"

class CVCreado(models.Model):
    # CV creado con el wizard del sitio
    id_cv_creado = models.OneToOneField(CVCandidato, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

class CVSubido(models.Model):
    # CV subido como archivo
    id_cv_subido = models.OneToOneField(CVCandidato, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    fecha_subido = models.DateTimeField(auto_now_add=True)
    ruta_archivo = models.URLField(max_length=500)

# --- Secciones del CV Creado ---

class DatosPersonalesCV(models.Model):
    id_cv_creado = models.OneToOneField(CVCreado, on_delete=models.CASCADE, primary_key=True)
    primer_nombre = models.CharField(max_length=50)
    segundo_nombre = models.CharField(max_length=50, null=True, blank=True)
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50, null=True, blank=True)
    titulo_profesional = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=20)
    linkedin = models.URLField(max_length=255, null=True, blank=True)

class ObjetivoProfesionalCV(models.Model):
    id_cv_creado = models.OneToOneField(CVCreado, on_delete=models.CASCADE, primary_key=True)
    texto_objetivo = models.TextField(max_length=1000)

class EducacionCV(models.Model):
    id_educacion = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='educacion') # Relación inferida
    institucion = models.CharField(max_length=100)
    carrera_titulo_nivel = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    cursando = models.BooleanField(default=False)
    comentarios = models.CharField(max_length=500, null=True, blank=True)

class ExperienciaLaboralCV(models.Model):
    id_experiencia = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='experiencia') # Relación inferida
    cargo_puesto = models.CharField(max_length=100)
    empresa = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    trabajo_actual = models.BooleanField(default=False)
    practica = models.BooleanField(default=False)
    horas_practica = models.IntegerField(null=True, blank=True)
    descripcion_cargo = models.TextField(max_length=1000)

class CertificacionesCV(models.Model):
    id_certificacion = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='certificaciones') # Relación inferida
    nombre_certificacion = models.CharField(max_length=150)
    entidad_emisora = models.CharField(max_length=150)
    fecha_obtencion = models.DateField()

class HabilidadCV(models.Model):
    id_habilidad = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='habilidades') # Relación inferida
    tipo_habilidad = models.CharField(max_length=50)
    texto_habilidad = models.CharField(max_length=150)

class IdiomaCV(models.Model):
    id_idioma = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='idiomas') # Relación inferida
    nombre_idioma = models.CharField(max_length=50)
    nivel_idioma = models.CharField(max_length=30)

class ProyectosCV(models.Model):
    id_proyecto = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='proyectos') # Relación inferida
    nombre_proyecto = models.CharField(max_length=100)
    fecha_proyecto = models.DateField()
    rol_participacion = models.CharField(max_length=100, null=True, blank=True)
    descripcion_proyecto = models.TextField(max_length=1000)
    url_proyecto = models.URLField(max_length=255, null=True, blank=True)

class ReferenciasCV(models.Model):
    id_referencia = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='referencias') # Relación inferida
    nombre_referente = models.CharField(max_length=100)
    cargo_referente = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(max_length=150)
    url_linkedin = models.URLField(max_length=255, null=True, blank=True)

class VoluntariadoCV(models.Model):
    id_voluntariado = models.AutoField(primary_key=True)
    cv_creado = models.ForeignKey(CVCreado, on_delete=models.CASCADE, related_name='voluntariado') # Relación inferida
    nombre_organizacion = models.CharField(max_length=100)
    puesto_rol = models.CharField(max_length=100)
    descripcion_actividades = models.TextField(max_length=1000)
    ciudad = models.CharField(max_length=50)
    region_estado_provincia = models.CharField(max_length=50, null=True, blank=True)
    pais = models.CharField(max_length=50)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    actualmente_activo = models.BooleanField(default=False)

# ==============================================================================
# Modelos de Postulación y Entrevistas
# ==============================================================================

class Postulacion(models.Model):
    id_postulacion = models.AutoField(primary_key=True)
    oferta = models.ForeignKey(OfertaLaboral, on_delete=models.CASCADE) # Relación inferida
    candidato = models.ForeignKey(Candidato, on_delete=models.CASCADE) # Relación inferida
    cv_postulado = models.ForeignKey(CVCandidato, on_delete=models.CASCADE) # Relación inferida
    fecha_postulacion = models.DateTimeField(auto_now_add=True)
    estado_postulacion = models.CharField(max_length=50)

class Entrevista(models.Model):
    id_entrevista = models.AutoField(primary_key=True)
    postulacion = models.ForeignKey(Postulacion, on_delete=models.CASCADE) # Relación inferida
    fecha_entrevista = models.DateField()
    hora_entrevista = models.TimeField() # DDL usaba DATE, asumo que era para la hora
    nombre_reclutador = models.CharField(max_length=150)
    modalidad = models.CharField(max_length=20) # 'online' o 'presencial'
    asistencia_confirmada = models.BooleanField(null=True, blank=True)

class ModoOnline(models.Model):
    id_modo_online = models.OneToOneField(Entrevista, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    plataforma = models.CharField(max_length=100)
    url_reunion = models.URLField(max_length=255)

class ModoPresencial(models.Model):
    id_modo_presencial = models.OneToOneField(Entrevista, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    direccion = models.CharField(max_length=150)

# ==============================================================================
# Modelos de Notificaciones y Ubicación
# ==============================================================================

class TipoNotificacion(models.Model):
    id_tipo_notificacion = models.AutoField(primary_key=True)
    nombre_tipo = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255)

class Notificaciones(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    usuario_destino = models.ForeignKey(User, on_delete=models.CASCADE, db_constraint=False) # Relación inferida
    tipo_notificacion = models.ForeignKey(TipoNotificacion, on_delete=models.CASCADE) # Relación inferida
    mensaje = models.CharField(max_length=255)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    link_relacionado = models.URLField(max_length=255, null=True, blank=True)

class NotificacionCandidato(models.Model):
    # Esta tabla y la siguiente parecen innecesarias si se usa el modelo Notificaciones
    id_notificacion_candidato = models.OneToOneField(Notificaciones, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    motivo = models.CharField(max_length=100)

class NotificacionEmpresa(models.Model):
    id_notificacion_empresa = models.OneToOneField(Notificaciones, on_delete=models.CASCADE, primary_key=True) # Relación inferida
    motivo = models.CharField(max_length=100)

class Ubicacion(models.Model):
    id_ubicacion = models.AutoField(primary_key=True)
    region = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.ciudad}, {self.region}"


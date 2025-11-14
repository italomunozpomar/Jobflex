from django import forms
from django.utils.translation import gettext_lazy as _
from allauth.account.forms import LoginForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
import uuid
# Se importan los nuevos modelos necesarios
from .models import Candidato, Region, Ciudad, RolesEmpresa

User = get_user_model()

class CustomLoginForm(LoginForm):
    def clean(self):
        cleaned_data = super().clean()
        email = self.cleaned_data.get('login')
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                user = User.objects.get(email=email)
                if user.socialaccount_set.exists():
                    raise forms.ValidationError(
                        _("Esta cuenta se registró usando un proveedor externo (como Google). Por favor, inicia sesión usando ese método.")
                    )
            except User.DoesNotExist:
                pass
        
        return cleaned_data

class SignUpForm(UserCreationForm):
    nombres = forms.CharField(max_length=150, required=True, label='Nombres')
    apellidos = forms.CharField(max_length=150, required=True, label='Apellidos')
    email = forms.EmailField(max_length=254, required=True, label='Correo Electrónico')

    class Meta:
        model = User
        fields = ('nombres', 'apellidos', 'email')

    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields['password1'].label = "Contraseña"
        self.fields['password1'].help_text = 'Tu contraseña debe contener al menos 8 caracteres y no puede ser demasiado común.'
        self.fields['password2'].label = "Confirmar Contraseña"
        self.fields['password2'].help_text = None # Opcional: limpiar el help_text del segundo campo
        
        if 'username' in self.fields:
            self.fields['username'].widget = forms.HiddenInput()
            self.fields['username'].required = False

        for field_name in self.fields:
            field = self.fields.get(field_name)
            if field and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                })


    def save(self, commit=True):
        user = super(SignUpForm, self).save(commit=False)
        user.username = self.cleaned_data['email']
        user.first_name = self.cleaned_data['nombres']
        user.last_name = self.cleaned_data['apellidos']
        if commit:
            user.save()
        return user

class VerificationForm(forms.Form):
    code = forms.CharField(max_length=6, required=True, label="Código de Verificación")

class CandidatoForm(forms.ModelForm):
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=False,
        label="Región",
        empty_label="Selecciona una región"
    )

    class Meta:
        model = Candidato
        fields = ['rut_candidato', 'fecha_nacimiento', 'telefono', 'linkedin_url', 'region', 'ciudad']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'rut_candidato': forms.TextInput(attrs={'placeholder': '12345678-9'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 XXXX XXXX'}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/tu-usuario'}),
            'ciudad': forms.Select(attrs={'class': 'form-control'}), # Será poblado por JS
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['ciudad'].queryset = Ciudad.objects.none()

        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].ciudad:
            instance = kwargs['instance']
            self.fields['region'].initial = instance.ciudad.region
            self.fields['ciudad'].queryset = Ciudad.objects.filter(region=instance.ciudad.region).order_by('nombre')
            self.fields['ciudad'].initial = instance.ciudad
        elif 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['ciudad'].queryset = Ciudad.objects.filter(region_id=region_id).order_by('nombre')
            except (ValueError, TypeError):
                pass  # invalid input from browser; ignore and fallback to empty City queryset
        
        self.fields['rut_candidato'].label = "RUT"
        self.fields['fecha_nacimiento'].label = "Fecha de Nacimiento"
        self.fields['telefono'].label = "Teléfono de Contacto"
        self.fields['linkedin_url'].label = "URL de tu perfil de LinkedIn"

        for field_name in self.fields:
            field = self.fields.get(field_name)
            if field and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                })

    # El método save ya no necesita lógica especial para la ubicación,
    # el ModelForm se encarga de guardar la FK 'ciudad' directamente.

class EmpresaSignUpForm(SignUpForm):
    terms = forms.BooleanField(required=True, label='Acepto los Términos y Condiciones')
    rut = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super(EmpresaSignUpForm, self).__init__(*args, **kwargs)
        self.fields['nombres'].label = "Nombres del Representante"
        self.fields['apellidos'].label = "Apellidos del Representante"


from .models import CVCandidato

class CVCandidatoForm(forms.ModelForm):
    class Meta:
        model = CVCandidato
        fields = ['nombre_cv', 'cargo_asociado']
        labels = {
            'nombre_cv': 'Nombre del Perfil de CV',
            'cargo_asociado': 'Cargo Asociado',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            field = self.fields.get(field_name)
            if field:
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                })

class CompletarPerfilForm(forms.ModelForm):
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=True,
        label="Región",
        empty_label="Selecciona una región"
    )

    class Meta:
        model = Candidato
        fields = ['rut_candidato', 'fecha_nacimiento', 'telefono', 'linkedin_url', 'region', 'ciudad']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'rut_candidato': forms.TextInput(attrs={'placeholder': '12345678-9'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 XXXX XXXX'}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/tu-usuario'}),
            'ciudad': forms.Select(attrs={'class': 'form-control'}), # Será poblado por JS
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['ciudad'].queryset = Ciudad.objects.none()

        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].ciudad:
            instance = kwargs['instance']
            self.fields['region'].initial = instance.ciudad.region
            self.fields['ciudad'].queryset = Ciudad.objects.filter(region=instance.ciudad.region).order_by('nombre')
            self.fields['ciudad'].initial = instance.ciudad
        elif 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['ciudad'].queryset = Ciudad.objects.filter(region_id=region_id).order_by('nombre')
            except (ValueError, TypeError):
                pass
        
        self.fields['rut_candidato'].label = "RUT"
        self.fields['fecha_nacimiento'].label = "Fecha de Nacimiento"
        self.fields['telefono'].label = "Teléfono de Contacto"
        self.fields['linkedin_url'].label = "URL de tu perfil de LinkedIn"

        for field_name in self.fields:
            field = self.fields.get(field_name)
            if field and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                })

from django.contrib.auth.forms import SetPasswordForm # Import SetPasswordForm

class SetInvitationPasswordForm(SetPasswordForm):
    nombres = forms.CharField(max_length=150, required=True, label='Nombres')
    apellidos = forms.CharField(max_length=150, required=True, label='Apellidos')

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        # Initialize first_name and last_name from the user object if available
        if user.first_name and user.first_name != "Invitado": # Check for placeholder
            self.fields['nombres'].initial = user.first_name
        if user.last_name and user.last_name != "Pendiente": # Check for placeholder
            self.fields['apellidos'].initial = user.last_name

        for field_name in self.fields:
            field = self.fields.get(field_name)
            if field and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                })
        
        # Make password fields required
        self.fields['new_password1'].required = True
        self.fields['new_password2'].required = True

    def save(self, commit=True):
        user = super().save(commit=False) # Save password
        user.first_name = self.cleaned_data['nombres']
        user.last_name = self.cleaned_data['apellidos']
        if commit:
            user.save()
        return user

# --- Formularios de Empresa (Mantenidos comentados por ahora para evitar errores) ---
# ...

class InvitationForm(forms.Form):
    email = forms.EmailField(
        label='Correo Electrónico',
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': 'tu@email.com'
        })
    )
    role = forms.ModelChoiceField(
        queryset=RolesEmpresa.objects.all(),
        label='Rol del Usuario',
        empty_label='Selecciona un rol',
        widget=forms.Select(attrs={
            'class': 'block w-full pl-3 pr-10 py-2 border border-gray-300 rounded-md leading-5 bg-white text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm'
        })
    )

from .models import Empresa, CVSubido



class EmpresaDataForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['nombre_comercial', 'resumen_empresa', 'sitio_web', 'mision', 'vision']
        labels = {
            'nombre_comercial': 'Nombre Comercial',
            'resumen_empresa': 'Resumen de la Empresa',
            'sitio_web': 'Sitio Web',
            'mision': 'Misión',
            'vision': 'Visión',
        }
        widgets = {
            'resumen_empresa': forms.Textarea(attrs={'rows': 4}),
            'mision': forms.Textarea(attrs={'rows': 3}),
            'vision': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_sitio_web(self):
        sitio_web = self.cleaned_data.get('sitio_web')
        if sitio_web and not sitio_web.startswith(('http://', 'https://')):
            sitio_web = 'https://' + sitio_web
        return sitio_web

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field and not isinstance(field.widget, forms.CheckboxInput):
                existing_classes = field.widget.attrs.get('class', '')
                base_class = 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
                field.widget.attrs['class'] = f"{existing_classes} {base_class}".strip()



class CVSubidoForm(forms.Form):
    nombre_cv = forms.CharField(max_length=100, required=True, label='Nombre del Perfil de CV')
    cargo_asociado = forms.CharField(max_length=100, required=True, label='Cargo Asociado')
    cv_file = forms.FileField(label='Archivo CV (PDF)', widget=forms.FileInput(attrs={
        'class': 'absolute inset-0 opacity-0 z-50 pointer-events-none'
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre_cv'].widget.attrs.update({
            'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary',
            'placeholder': 'Ej: Mi CV para startups'
        })
        self.fields['cargo_asociado'].widget.attrs.update({
            'class': 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary',
            'placeholder': 'Ej: Desarrollador Full-Stack'
        })
from .models import OfertaLaboral, Categoria, Jornada, Modalidad
from django.utils import timezone
from datetime import timedelta

class OfertaLaboralForm(forms.ModelForm):
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        label="Categoría",
        required=False,
        empty_label="Selecciona una categoría"
    )
    nueva_categoria = forms.CharField(
        label="Nueva Categoría",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Escribe un nombre para la nueva categoría'})
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=False,
        label="Región",
        empty_label="Selecciona una región"
    )
    duracion_oferta = forms.ChoiceField(
        choices=[
            ('7', '1 semana'),
            ('14', '2 semanas'),
            ('21', '3 semanas'),
            ('30', '1 mes'),
            ('custom', 'Personalizada'),
        ],
        label='Duración de la Oferta'
    )
    fecha_cierre_personalizada = forms.DateField(
        label='Fecha de Cierre Personalizada',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = OfertaLaboral
        fields = [
            'titulo_puesto', 'categoria', 'nueva_categoria', 'region', 'ciudad', 'jornada', 'modalidad', 
            'salario_min', 'salario_max', 'nivel_experiencia', 
            'descripcion_puesto', 'requisitos_puesto', 
            'habilidades_clave', 'beneficios'
        ]
        widgets = {
            'descripcion_puesto': forms.Textarea(attrs={'rows': 5, 'class': 'form-textarea'}),
            'requisitos_puesto': forms.Textarea(attrs={'rows': 5, 'class': 'form-textarea'}),
            'habilidades_clave': forms.TextInput(attrs={'placeholder': 'Python, SQL, etc.'}),
            'beneficios': forms.TextInput(attrs={'placeholder': 'Seguro médico, etc.'}),
            'ciudad': forms.Select(), # Será poblado por JS
        }
        labels = {
            'titulo_puesto': 'Título del Puesto',
            'jornada': 'Jornada Laboral',
            'modalidad': 'Modalidad de Trabajo',
            'ciudad': 'Ciudad',
            'salario_min': 'Salario Mínimo (CLP)',
            'salario_max': 'Salario Máximo (CLP)',
            'nivel_experiencia': 'Nivel de Experiencia Requerido',
            'descripcion_puesto': 'Descripción del Puesto',
            'requisitos_puesto': 'Requisitos del Puesto',
            'habilidades_clave': 'Habilidades Clave',
            'beneficios': 'Beneficios Ofrecidos',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['jornada'].queryset = Jornada.objects.all()
        self.fields['modalidad'].queryset = Modalidad.objects.all()
        self.fields['ciudad'].queryset = Ciudad.objects.none()

        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].ciudad:
            instance = kwargs['instance']
            self.fields['region'].initial = instance.ciudad.region
            self.fields['ciudad'].queryset = Ciudad.objects.filter(region=instance.ciudad.region).order_by('nombre')
            self.fields['ciudad'].initial = instance.ciudad
        elif 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['ciudad'].queryset = Ciudad.objects.filter(region_id=region_id).order_by('nombre')
            except (ValueError, TypeError):
                pass

        base_css_class = 'mt-1 block w-full p-3 border border-light-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary'
        
        for field_name, field in self.fields.items():
            if field_name not in self.Meta.widgets:
                field.widget.attrs.update({'class': base_css_class})
            elif field_name in self.Meta.widgets:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = base_css_class

            if field_name == 'salario_min':
                field.widget.attrs['placeholder'] = 'Ej: 800000'
            if field_name == 'salario_max':
                field.widget.attrs['placeholder'] = 'Ej: 1200000'
            if field_name == 'nivel_experiencia':
                field.widget.attrs['placeholder'] = 'Ej: Semi-Senior, Junior, Senior...'

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        nueva_categoria = cleaned_data.get('nueva_categoria')
        duracion = cleaned_data.get('duracion_oferta')
        fecha_personalizada = cleaned_data.get('fecha_cierre_personalizada')

        if not categoria and not nueva_categoria:
            raise forms.ValidationError('Debe seleccionar una categoría o crear una nueva.', code='categoria_required')
        
        if categoria and nueva_categoria:
            raise forms.ValidationError('No puede seleccionar una categoría y crear una nueva al mismo tiempo.', code='categoria_ambiguous')

        if duracion == 'custom':
            if not fecha_personalizada:
                self.add_error('fecha_cierre_personalizada', 'Debe seleccionar una fecha si elige la opción personalizada.')
            else:
                today = timezone.now().date()
                # This validation is now handled in JS, but we keep a server-side check
                # max_date = today + timedelta(days=31) 
                # if not (today <= fecha_personalizada <= max_date):
                #     self.add_error('fecha_cierre_personalizada', f'La fecha debe estar entre hoy y 31 días en el futuro.')
        
        return cleaned_data
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from JFlex.models import (Ciudad, Empresa, OfertaLaboral, Categoria, Jornada,
                           Modalidad)

# More comprehensive and realistic job data
JOB_DATA = {
    'Tecnología': [
        {'titulo': 'Ingeniero de Software Senior (Backend)', 'descripcion': '<p>Únete a nuestro equipo para diseñar, desarrollar y mantener las API REST que potencian nuestros servicios en la nube. Trabajarás con un stack moderno y un equipo de alto rendimiento.</p>', 'requisitos': '<ul><li>+5 años con Python, Django o Flask.</li><li>Experiencia en diseño de microservicios.</li><li>Conocimiento de AWS o Azure.</li><li>Manejo de Docker y Kubernetes.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2800000, 4000000)},
        {'titulo': 'Arquitecto de Soluciones Cloud', 'descripcion': '<p>Define la visión técnica y la arquitectura de nuestras soluciones en la nube, asegurando escalabilidad, seguridad y rendimiento. Serás el referente técnico para los equipos de desarrollo.</p>', 'requisitos': '<ul><li>+8 años de experiencia en roles de arquitectura.</li><li>Certificación como Arquitecto de Soluciones en AWS, Azure o GCP.</li><li>Profundo conocimiento de patrones de diseño de software.</li></ul>', 'nivel_experiencia': 'Experto', 'salario_range': (3500000, 5000000)},
        {'titulo': 'Científico de Datos (Machine Learning)', 'descripcion': '<p>Desarrolla modelos de machine learning para resolver problemas complejos de negocio, desde la experimentación hasta la puesta en producción. Trabajarás con grandes volúmenes de datos.</p>', 'requisitos': '<ul><li>Magíster o Doctorado en Computación, Estadística o similar.</li><li>+4 años de experiencia en roles de Data Science.</li><li>Dominio de Python, Scikit-learn, TensorFlow o PyTorch.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2600000, 3800000)},
        {'titulo': 'Product Manager Técnico', 'descripcion': '<p>Lidera la estrategia y el roadmap de uno de nuestros productos de software. Traducirás las necesidades del negocio en requerimientos técnicos claros para el equipo de desarrollo.</p>', 'requisitos': '<ul><li>Experiencia previa como Product Manager en empresas de tecnología.</li><li>Sólida comprensión del ciclo de vida de desarrollo de software.</li><li>Excelentes habilidades de comunicación.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2400000, 3500000)},
        {'titulo': 'Ingeniero DevOps', 'descripcion': '<p>Automatiza y optimiza nuestros procesos de CI/CD, infraestructura como código y monitoreo. Tu objetivo es mejorar la velocidad y la fiabilidad de nuestros despliegues.</p>', 'requisitos': '<ul><li>Experiencia con Jenkins, GitLab CI o similar.</li><li>Dominio de Terraform y Ansible.</li><li>Conocimientos de monitoreo con Prometheus y Grafana.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1800000, 2600000)},
        {'titulo': 'Desarrollador Frontend (React)', 'descripcion': '<p>Construye interfaces de usuario interactivas y de alto rendimiento utilizando React y las últimas tecnologías del ecosistema frontend.</p>', 'requisitos': '<ul><li>+3 años de experiencia con React y TypeScript.</li><li>Manejo de Redux o similares para la gestión de estado.</li><li>Experiencia con pruebas unitarias (Jest/React Testing Library).</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1700000, 2500000)},
        {'titulo': 'Especialista en Ciberseguridad', 'descripcion': '<p>Protege nuestra infraestructura y aplicaciones de amenazas internas y externas. Realizarás análisis de vulnerabilidades, pentesting y gestión de incidentes.</p>', 'requisitos': '<ul><li>Certificaciones como CISSP, OSCP o similar.</li><li>Experiencia en análisis de malware y forense digital.</li><li>Conocimiento de normativas de seguridad.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2500000, 3700000)},
        {'titulo': 'Analista de Business Intelligence', 'descripcion': '<p>Transforma datos crudos en insights accionables para el negocio. Crearás dashboards y reportes que faciliten la toma de decisiones estratégicas.</p>', 'requisitos': '<ul><li>Experiencia con herramientas de BI como Power BI o Tableau.</li><li>Sólidos conocimientos de SQL.</li><li>Capacidad para comunicar resultados a audiencias no técnicas.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1400000, 2200000)},
        {'titulo': 'Soporte Técnico Nivel 2', 'descripcion': '<p>Resolver problemas técnicos complejos de nuestros clientes corporativos, escalando casos a los equipos de ingeniería cuando sea necesario.</p>', 'requisitos': '<ul><li>+2 años de experiencia en roles de soporte técnico.</li><li>Conocimientos de redes y sistemas operativos.</li><li>Excelentes habilidades de resolución de problemas.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (900000, 1300000)},
        {'titulo': 'Scrum Master', 'descripcion': '<p>Facilita las ceremonias de Scrum, elimina impedimentos y fomenta una cultura de mejora continua dentro de los equipos de desarrollo.</p>', 'requisitos': '<ul><li>Certificación Scrum Master (CSM, PSM I).</li><li>+3 años de experiencia en el rol.</li><li>Experiencia con herramientas como Jira.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1600000, 2400000)},
    ],
    'Retail': [
        {'titulo': 'Gerente de Tienda', 'descripcion': '<p>Responsable de la gestión integral de la tienda, incluyendo equipo, inventario y metas de venta.</p>', 'requisitos': '<ul><li>+5 años de experiencia en retail.</li><li>Liderazgo y gestión de equipos.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1500000, 2200000)},
        {'titulo': 'Category Manager', 'descripcion': '<p>Define la estrategia comercial para una categoría de productos, gestionando la relación con proveedores y optimizando el surtido.</p>', 'requisitos': '<ul><li>Ingeniería Comercial o similar.</li><li>Experiencia en compras o gestión de categorías en retail.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1800000, 2600000)},
        {'titulo': 'Analista de Logística y Cadena de Suministro', 'descripcion': '<p>Optimiza los procesos de recepción, almacenamiento y despacho de mercadería para garantizar la disponibilidad de productos en tienda.</p>', 'requisitos': '<ul><li>Ingeniero en Logística o Industrial.</li><li>Manejo de SAP o algún ERP similar.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1100000, 1600000)},
        {'titulo': 'Visual Merchandiser', 'descripcion': '<p>Diseña y ejecuta la presentación visual de los productos en la tienda para maximizar las ventas y mejorar la experiencia del cliente.</p>', 'requisitos': '<ul><li>Estudios en Diseño de Ambientes o similar.</li><li>Experiencia en visual merchandising en retail.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (800000, 1200000)},
        {'titulo': 'Especialista en Prevención de Pérdidas', 'descripcion': '<p>Implementa estrategias y procedimientos para minimizar las mermas y pérdidas de inventario en la tienda.</p>', 'requisitos': '<ul><li>Experiencia en seguridad o prevención de pérdidas en retail.</li><li>Conocimiento de sistemas de CCTV.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (900000, 1400000)},
        {'titulo': 'Analista de Marketing y Fidelización', 'descripcion': '<p>Desarrolla y ejecuta campañas para atraer y retener clientes, gestionando el programa de lealtad de la tienda.</p>', 'requisitos': '<ul><li>Publicista o Ingeniero en Marketing.</li><li>Experiencia en marketing para retail.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1000000, 1500000)},
        {'titulo': 'Jefe de Cajas', 'descripcion': '<p>Supervisa el correcto funcionamiento de la línea de cajas, gestionando al personal y los procesos de pago.</p>', 'requisitos': '<ul><li>Experiencia previa como supervisor de cajas.</li><li>Manejo de sistemas de punto de venta (POS).</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (850000, 1250000)},
        {'titulo': 'Comprador Junior', 'descripcion': '<p>Asiste al Category Manager en la selección de productos, negociación con proveedores y análisis de ventas.</p>', 'requisitos': '<ul><li>Recién egresado de Ingeniería Comercial.</li><li>Excel avanzado.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (700000, 1100000)},
        {'titulo': 'Coordinador de E-commerce', 'descripcion': '<p>Responsable de la operación diaria del canal online, incluyendo la carga de productos y la gestión de pedidos.</p>', 'requisitos': '<ul><li>Experiencia en la operación de plataformas de e-commerce.</li><li>Atención al detalle.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (950000, 1450000)},
        {'titulo': 'Asistente de Recursos Humanos en Tienda', 'descripcion': '<p>Apoya en los procesos de reclutamiento, contratación y gestión de personal para la tienda.</p>', 'requisitos': '<ul><li>Técnico o Ingeniero en RRHH.</li><li>Conocimiento de legislación laboral básica.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (750000, 1150000)},
    ],
    'Minería': [
        {'titulo': 'Supervisor de Mantenimiento Eléctrico', 'descripcion': '<p>Planifica y supervisa los trabajos de mantenimiento eléctrico en equipos de la planta para asegurar la continuidad operacional.</p>', 'requisitos': '<ul><li>Ingeniero Eléctrico o similar.</li><li>+5 años en mantenimiento industrial, idealmente en minería.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2600000, 3600000)},
        {'titulo': 'Ingeniero de Planificación Minera', 'descripcion': '<p>Desarrolla planes de producción a corto y largo plazo, optimizando la extracción de mineral.</p>', 'requisitos': '<ul><li>Ingeniero de Minas.</li><li>Experiencia con software de planificación como Deswik o MineSight.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (2000000, 2800000)},
        {'titulo': 'Jefe de Turno de Operaciones', 'descripcion': '<p>Lidera al equipo de operadores durante el turno, velando por el cumplimiento de las metas de producción y seguridad.</p>', 'requisitos': '<ul><li>Experiencia liderando equipos en operaciones mineras.</li><li>Fuerte enfoque en seguridad.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (3000000, 4200000)},
        {'titulo': 'Especialista en Medio Ambiente', 'descripcion': '<p>Asegura el cumplimiento de la normativa ambiental y gestiona los permisos y monitoreos requeridos para la operación.</p>', 'requisitos': '<ul><li>Ingeniero Ambiental o carrera afín.</li><li>Conocimiento de la legislación ambiental chilena.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1700000, 2400000)},
        {'titulo': 'Ingeniero en Automatización y Control', 'descripcion': '<p>Desarrolla y mantiene los sistemas de control automático de la planta para optimizar los procesos.</p>', 'requisitos': '<ul><li>Ingeniero en Automatización, Electrónico o similar.</li><li>Experiencia con PLC y sistemas SCADA.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1900000, 2700000)},
        {'titulo': 'Analista de Contratos Mineros', 'descripcion': '<p>Gestiona la administración de contratos con empresas colaboradoras, asegurando el cumplimiento de los términos y condiciones.</p>', 'requisitos': '<ul><li>Ingeniero Comercial o Abogado.</li><li>Experiencia en gestión de contratos, preferentemente en minería.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1600000, 2300000)},
        {'titulo': 'Prevencionista de Riesgos para Faena', 'descripcion': '<p>Implementa y supervisa el programa de prevención de riesgos en terreno para garantizar un ambiente de trabajo seguro.</p>', 'requisitos': '<ul><li>Ingeniero en Prevención de Riesgos.</li><li>Calificación SERNAGEOMIN.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1800000, 2500000)},
        {'titulo': 'Operador de Camión de Extracción (CAEX)', 'descripcion': '<p>Opera camiones de alto tonelaje para el transporte de material dentro de la mina.</p>', 'requisitos': '<ul><li>Licencia de conducir A-5.</li><li>Certificación para operar CAEX.</li><li>Experiencia en minería a cielo abierto.</li></ul>', 'nivel_experiencia': 'Operativo', 'salario_range': (1400000, 2000000)},
        {'titulo': 'Ingeniero Metalurgista de Procesos', 'descripcion': '<p>Monitorea y optimiza los procesos de la planta concentradora para maximizar la recuperación de cobre.</p>', 'requisitos': '<ul><li>Ingeniero Civil Metalúrgico o Químico.</li><li>Conocimiento en procesos de flotación y lixiviación.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (2100000, 2900000)},
        {'titulo': 'Asistente de Bodega en Faena', 'descripcion': '<p>Gestiona la recepción, almacenamiento y despacho de materiales y repuestos en la bodega de la faena minera.</p>', 'requisitos': '<ul><li>Experiencia en logística de bodega.</li><li>Licencia de conducir clase D (manejo de grúa horquilla).</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (900000, 1300000)},
    ],
    'Telecomunicaciones': [
        {'titulo': 'Técnico de Fibra Óptica (FTTH)', 'descripcion': '<p>Realiza instalaciones y reparaciones de servicios de internet y televisión por fibra óptica en domicilios de clientes.</p>', 'requisitos': '<ul><li>Conocimiento en tendido y fusión de fibra óptica.</li><li>Licencia de conducir clase B.</li></ul>', 'nivel_experiencia': 'Técnico', 'salario_range': (700000, 1100000)},
        {'titulo': 'Key Account Manager (KAM) Empresas', 'descripcion': '<p>Gestiona y desarrolla la cartera de clientes corporativos, ofreciendo soluciones de telecomunicaciones a la medida de sus necesidades.</p>', 'requisitos': '<ul><li>+3 años de experiencia en ventas a empresas.</li><li>Conocimiento del mercado de las telecomunicaciones.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1800000, 2800000)},
        {'titulo': 'Analista de Calidad de Red', 'descripcion': '<p>Monitorea los indicadores de rendimiento de la red móvil y fija para identificar y resolver problemas de calidad de servicio.</p>', 'requisitos': '<ul><li>Ingeniero en Telecomunicaciones o similar.</li><li>Conocimiento de protocolos de red y herramientas de monitoreo.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1300000, 1900000)},
        {'titulo': 'Especialista en Marketing de Producto', 'descripcion': '<p>Lidera el lanzamiento de nuevos productos y servicios, desde la conceptualización hasta la estrategia de go-to-market.</p>', 'requisitos': '<ul><li>Ingeniero Comercial o Publicista.</li><li>Experiencia en marketing de productos, idealmente en Telco.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1600000, 2400000)},
        {'titulo': 'Ingeniero de Proyectos TI', 'descripcion': '<p>Lidera proyectos de implementación de nuevas plataformas y sistemas de TI para soportar la operación del negocio.</p>', 'requisitos': '<ul><li>Ingeniero Informático o Industrial.</li><li>Certificación PMP o similar (deseable).</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1900000, 2700000)},
        {'titulo': 'Soporte Técnico en Terreno', 'descripcion': '<p>Proporciona asistencia técnica a clientes empresariales en sus instalaciones, resolviendo problemas de conectividad y configuración.</p>', 'requisitos': '<ul><li>Técnico en Conectividad y Redes.</li><li>Licencia de conducir.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (800000, 1200000)},
        {'titulo': 'Desarrollador de Aplicaciones Móviles (Android/iOS)', 'descripcion': '<p>Crea y mantiene las aplicaciones móviles de la compañía, enfocándose en la experiencia de usuario y el rendimiento.</p>', 'requisitos': '<ul><li>Experiencia en desarrollo nativo (Kotlin/Swift) o híbrido (Flutter/React Native).</li><li>Publicación de apps en App Store o Google Play.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1800000, 2600000)},
        {'titulo': 'Analista de Fraude y Seguridad', 'descripcion': '<p>Monitorea transacciones y patrones de uso para detectar y prevenir actividades fraudulentas en la red.</p>', 'requisitos': '<ul><li>Experiencia en análisis de datos con SQL.</li><li>Conocimiento en prevención de fraude.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1200000, 1700000)},
        {'titulo': 'Planificador de Red de Acceso', 'descripcion': '<p>Diseña y planifica la expansión de la red de acceso (móvil y fija) para cubrir nuevas áreas y aumentar la capacidad.</p>', 'requisitos': '<ul><li>Ingeniero en Telecomunicaciones.</li><li>Conocimiento de herramientas de planificación de radiofrecuencia (RF).</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (2000000, 2800000)},
        {'titulo': 'Ejecutivo de Atención al Cliente (Redes Sociales)', 'descripcion': '<p>Responde y soluciona las consultas y problemas de los clientes a través de las plataformas de redes sociales de la empresa.</p>', 'requisitos': '<ul><li>Excelente redacción y ortografía.</li><li>Experiencia en atención al cliente.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (600000, 900000)},
    ],
    'Educación': [
        {'titulo': 'Director de Carrera (Ingeniería)', 'descripcion': '<p>Lidera la gestión académica y administrativa de las carreras del área de Ingeniería, asegurando la calidad y pertinencia del programa.</p>', 'requisitos': '<ul><li>Título de Ingeniero y postgrado (Magíster o Doctorado).</li><li>Experiencia en gestión académica.</li></ul>', 'nivel_experiencia': 'Directivo', 'salario_range': (2500000, 3500000)},
        {'titulo': 'Coordinador de Prácticas Profesionales', 'descripcion': '<p>Gestiona la relación con empresas para generar nuevas oportunidades de práctica y apoya a los estudiantes en su proceso de inserción laboral.</p>', 'requisitos': '<ul><li>Experiencia en vinculación con el medio o RRHH.</li><li>Red de contactos en el mundo empresarial.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1100000, 1600000)},
        {'titulo': 'Diseñador Instruccional', 'descripcion': '<p>Diseña experiencias de aprendizaje online, creando material didáctico y estructurando cursos en plataformas LMS.</p>', 'requisitos': '<ul><li>Pedagogo o diseñador con experiencia en e-learning.</li><li>Manejo de herramientas de autoría como Articulate o Captivate.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1200000, 1800000)},
        {'titulo': 'Analista de Datos Educacionales', 'descripcion': '<p>Analiza datos de rendimiento académico y deserción estudiantil para generar insights que permitan mejorar los programas educativos.</p>', 'requisitos': '<ul><li>Sociólogo, Estadístico o similar.</li><li>Manejo de SPSS, R o Python para análisis de datos.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1300000, 1900000)},
        {'titulo': 'Asistente de Admisión', 'descripcion': '<p>Orienta a los futuros estudiantes sobre la oferta académica y los guía durante el proceso de postulación y matrícula.</p>', 'requisitos': '<ul><li>Experiencia en ventas o atención al público.</li><li>Excelentes habilidades de comunicación.</li></ul>', 'nivel_experiencia': 'Junior', 'salario_range': (650000, 950000)},
        {'titulo': 'Docente de Inglés para Educación Superior', 'descripcion': '<p>Imparte clases de inglés a estudiantes de diversas carreras, enfocándose en habilidades comunicativas para el mundo profesional.</p>', 'requisitos': '<ul><li>Pedagogo en Inglés o traductor.</li><li>Certificación TEFL/TESOL (deseable).</li></ul>', 'nivel_experiencia': 'Docente', 'salario_range': (800000, 1400000)},
        {'titulo': 'Especialista en Asuntos Estudiantiles', 'descripcion': '<p>Organiza y gestiona actividades y programas de apoyo para los estudiantes, fomentando su bienestar y desarrollo integral.</p>', 'requisitos': '<ul><li>Psicólogo, Trabajador Social o carrera afín.</li><li>Experiencia trabajando con jóvenes.</li></ul>', 'nivel_experiencia': 'Semi-Senior', 'salario_range': (1000000, 1500000)},
        {'titulo': 'Jefe de Biblioteca', 'descripcion': '<p>Administra los recursos físicos y digitales de la biblioteca, gestionando al personal y promoviendo el uso de los servicios.</p>', 'requisitos': '<ul><li>Bibliotecólogo titulado.</li><li>Experiencia en gestión de bibliotecas académicas.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1400000, 2000000)},
        {'titulo': 'Técnico de Laboratorio (Área Salud)', 'descripcion': '<p>Prepara y mantiene los laboratorios y equipos para las clases prácticas de las carreras del área de la salud.</p>', 'requisitos': '<ul><li>Técnico de Nivel Superior en Enfermería o Laboratorio.</li><li>Experiencia en manejo de equipos de simulación.</li></ul>', 'nivel_experiencia': 'Técnico', 'salario_range': (750000, 1100000)},
        {'titulo': 'Coordinador de Educación Continua', 'descripcion': '<p>Desarrolla y comercializa diplomados y cursos de capacitación para profesionales, gestionando la relación con docentes y empresas.</p>', 'requisitos': '<ul><li>Profesional con experiencia en ventas y gestión de programas educativos.</li><li>Buenas habilidades de negociación.</li></ul>', 'nivel_experiencia': 'Senior', 'salario_range': (1700000, 2500000)},
    ]
}

COMPANY_INDUSTRIES = {
    2: 'Minería',          # Codelco
    3: 'Retail',           # líder
    4: 'Tecnología',       # Microsoft
    5: 'Tecnología',       # Copec (Asignado a Tecnología por enfoque en apps y servicios)
    6: 'Telecomunicaciones', # Entel
    7: 'Educación',        # Duoc
    8: 'Retail'            # Jumbo
}

class Command(BaseCommand):
    help = 'Populates the database with 10 realistic job offers for each specified company.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting to populate realistic job offers...')

        company_ids = [2, 3, 4, 5, 6, 7, 8]
        offers_created_count = 0

        # Get all related objects once to avoid querying in a loop
        categorias = list(Categoria.objects.all())
        jornadas = list(Jornada.objects.all())
        modalidades = list(Modalidad.objects.all())
        ciudades = list(Ciudad.objects.all())
        
        if not all([categorias, jornadas, modalidades, ciudades]):
            self.stdout.write(self.style.ERROR('Error: Could not retrieve necessary related data (Categories, etc.). Please populate them first.'))
            return

        for company_id in company_ids:
            try:
                company = Empresa.objects.get(id_empresa=company_id)
                self.stdout.write(f'--- Populating 10 offers for {company.nombre_comercial} ---')
                
                industry = COMPANY_INDUSTRIES.get(company_id, 'Retail')
                job_samples = JOB_DATA.get(industry, JOB_DATA['Retail'])
                random.shuffle(job_samples) # Shuffle to get unique jobs each time

                for i in range(10):
                    if i >= len(job_samples):
                        self.stdout.write(self.style.WARNING(f'Not enough unique job samples for {industry}. Re-using samples.'))
                        job_template = random.choice(job_samples)
                        title_suffix = f" (Ref. {random.randint(100, 999)})"
                    else:
                        job_template = job_samples[i]
                        title_suffix = ""

                    
                    salario_min, salario_max = job_template['salario_range']
                    
                    OfertaLaboral.objects.create(
                        empresa=company,
                        titulo_puesto=f"{job_template['titulo']}{title_suffix}",
                        descripcion_puesto=job_template['descripcion'],
                        requisitos_puesto=job_template['requisitos'],
                        habilidades_clave='[{"value":"Trabajo en Equipo"}, {"value":"Proactividad"}, {"value":"Comunicación"}]',
                        beneficios='[{"value":"Seguro Complementario"}, {"value":"Día libre de cumpleaños"}]',
                        nivel_experiencia=job_template['nivel_experiencia'],
                        salario_min=salario_min,
                        salario_max=salario_max,
                        fecha_publicacion=timezone.now(),
                        fecha_cierre=timezone.now() + timedelta(days=random.randint(15, 30)),
                        categoria=random.choice(categorias),
                        jornada=random.choice(jornadas),
                        modalidad=random.choice(modalidades),
                        estado='activa',
                        ciudad=random.choice(ciudades),
                        vistas=0
                    )
                    offers_created_count += 1
                    self.stdout.write(f"  - Created: {job_template['titulo']}{title_suffix}")

            except Empresa.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Error: Company with id={company_id} not found.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'An error occurred for company ID {company_id}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully created {offers_created_count} job offers in total.'))

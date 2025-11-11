import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from JFlex.models import EmpValidation

class Command(BaseCommand):
    help = 'Carga las primeras 100 empresas desde PUB_NOMBRES_PJ.txt para la demostración.'

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.BASE_DIR, 'JFlex', 'static', 'PUB_NOMBRES_PJ.txt')
        num_records_to_load = 100

        self.stdout.write(self.style.SUCCESS('--- Iniciando Carga de Demo para Validación de Empresas ---'))

        try:
            with transaction.atomic():
                # Paso 1: Limpiar la tabla para asegurar un estado limpio para la demo
                self.stdout.write('Paso 1: Limpiando la tabla EmpValidation...')
                count, _ = EmpValidation.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Se eliminaron {count} registros existentes.'))

                # Paso 2: Leer el archivo y cargar 100 registros
                self.stdout.write(f'Paso 2: Leyendo el archivo y preparando {num_records_to_load} registros...')
                records_to_create = []
                with open(file_path, 'r', encoding='latin-1') as f:
                    next(f)  # Omitir la línea de encabezado

                    for line in f:
                        if len(records_to_create) >= num_records_to_load:
                            break
                        
                        try:
                            parts = line.strip().split('\t')
                            if len(parts) < 4:
                                continue

                            rut = int(parts[0])
                            dv = parts[1]
                            razon_social = parts[3]
                            rut_completo = f'{rut}-{dv}'

                            records_to_create.append(EmpValidation(
                                rut=rut,
                                dv=dv,
                                razon_social=razon_social,
                                rut_completo=rut_completo
                            ))
                        except (ValueError, IndexError):
                            # Si una línea está mal formada, la saltamos y continuamos con la siguiente
                            continue
                
                # Paso 3: Cargar los registros en la base de datos
                if records_to_create:
                    self.stdout.write(f'Paso 3: Cargando {len(records_to_create)} registros en la base de datos...')
                    EmpValidation.objects.bulk_create(records_to_create)
                    self.stdout.write(self.style.SUCCESS('¡Carga masiva completada!'))

            self.stdout.write(self.style.SUCCESS('--- Proceso de Carga de Demo Finalizado ---'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Error: No se encontró el archivo en {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error inesperado: {e}'))

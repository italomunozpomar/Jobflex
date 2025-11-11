import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from JFlex.models import EmpValidation

class Command(BaseCommand):
    help = 'Carga y actualiza la base de datos de empresas desde el archivo PUB_NOMBRES_PJ.txt de forma masiva (bulk).'

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.BASE_DIR, 'JFlex', 'static', 'PUB_NOMBRES_PJ.txt')
        batch_size = 10000  # Se puede ajustar, pero 10,000 es un buen punto de partida

        self.stdout.write(self.style.SUCCESS('--- Proceso de Carga Masiva Optimizado Iniciado ---'))
        start_time = time.time()

        try:
            # PASO 1: Cargar todos los RUTs existentes en memoria para una búsqueda rápida.
            self.stdout.write('Paso 1: Cargando RUTs existentes en memoria...')
            existing_ruts = set(EmpValidation.objects.values_list('rut_completo', flat=True))
            self.stdout.write(self.style.SUCCESS(f'Se encontraron {len(existing_ruts)} registros existentes en la base de datos.'))

            records_to_create = []
            records_to_update = []
            
            self.stdout.write(f'Paso 2: Procesando el archivo de texto en lotes de {batch_size}...')
            
            with open(file_path, 'r', encoding='latin-1') as f:
                next(f)  # Omitir la línea de encabezado

                for i, line in enumerate(f, 1):
                    try:
                        parts = line.strip().split('\t')
                        if len(parts) < 4:
                            continue

                        rut = int(parts[0])
                        dv = parts[1]
                        razon_social = parts[3]
                        rut_completo = f'{rut}-{dv}'

                        # PASO 2.1: Separar en listas de creación o actualización
                        if rut_completo in existing_ruts:
                            # Para la actualización, guardamos tuplas con los datos necesarios
                            records_to_update.append((rut_completo, rut, dv, razon_social))
                        else:
                            # Para la creación, creamos el objeto en memoria
                            records_to_create.append(EmpValidation(
                                rut=rut,
                                dv=dv,
                                razon_social=razon_social,
                                rut_completo=rut_completo
                            ))
                            # Agregamos el nuevo rut al set para no intentar crearlo de nuevo en este ciclo
                            existing_ruts.add(rut_completo)
                        
                        # PASO 2.2: Si alcanzamos el tamaño del lote, lo procesamos
                        if i % batch_size == 0:
                            self.process_batches(records_to_create, records_to_update)
                            self.stdout.write(self.style.SUCCESS(f'Procesadas {i} líneas...'))
                            records_to_create.clear()
                            records_to_update.clear()

                    except (ValueError, IndexError):
                        continue
                
                # PASO 3: Procesar los registros restantes al final del archivo
                if records_to_create or records_to_update:
                    self.stdout.write('Procesando lote final...')
                    self.process_batches(records_to_create, records_to_update)

            total_time = time.time() - start_time
            self.stdout.write(self.style.SUCCESS('--- Proceso de Carga Finalizado ---'))
            self.stdout.write(self.style.SUCCESS(f'Tiempo total: {total_time:.2f} segundos.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Error: No se encontró el archivo en {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error inesperado: {e}'))

    def process_batches(self, to_create, to_update):
        """
        Función auxiliar para ejecutar las operaciones bulk en una transacción.
        """
        try:
            with transaction.atomic():
                # Lote de creación
                if to_create:
                    EmpValidation.objects.bulk_create(to_create)
                    self.stdout.write(self.style.NOTICE(f'  Creados {len(to_create)} nuevos registros.'))

                # Lote de actualización
                if to_update:
                    # Para actualizar en lote, primero obtenemos los objetos de la BD
                    update_ruts = [item[0] for item in to_update]
                    existing_objs_map = {obj.rut_completo: obj for obj in EmpValidation.objects.filter(rut_completo__in=update_ruts)}
                    
                    objs_to_update_in_db = []
                    for rut_completo, rut, dv, razon_social in to_update:
                        obj = existing_objs_map.get(rut_completo)
                        if obj:
                            obj.rut = rut
                            obj.dv = dv
                            obj.razon_social = razon_social
                            objs_to_update_in_db.append(obj)
                    
                    if objs_to_update_in_db:
                        EmpValidation.objects.bulk_update(objs_to_update_in_db, ['rut', 'dv', 'razon_social'])
                        self.stdout.write(self.style.NOTICE(f'  Actualizados {len(objs_to_update_in_db)} registros existentes.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error procesando un lote: {e}'))
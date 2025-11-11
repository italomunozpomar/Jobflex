import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from sii.models import EmpresaSII

class Command(BaseCommand):
    help = 'Loads company data from PUB_NOMBRES_PJ.txt into the sii database.'

    def handle(self, *args, **kwargs):
        # Correctly locate the data file in the /static/ directory of the JFlex app
        file_path = os.path.join(settings.BASE_DIR, 'JFlex', 'static', 'PUB_NOMBRES_PJ.txt')
        batch_size = 10000

        self.stdout.write(self.style.SUCCESS('--- Starting Bulk Load Process for SII Data ---'))
        start_time = time.time()

        try:
            self.stdout.write('Deleting existing data from sii_empresas table...')
            # Ensure the delete operation uses the 'sii' database connection
            with transaction.atomic(using='sii'):
                EmpresaSII.objects.using('sii').all().delete()
            self.stdout.write(self.style.SUCCESS('Existing data deleted.'))

            records_to_create = []
            processed_lines = 0
            
            self.stdout.write(f'Processing text file in batches of {batch_size}...')
            
            with open(file_path, 'r', encoding='latin-1') as f:
                next(f)  # Skip header line

                for line in f:
                    try:
                        parts = line.strip().split('\t')
                        if len(parts) < 4:
                            continue

                        rut = int(parts[0])
                        dv = parts[1]
                        razon_social = parts[3].strip()
                        rut_completo = f'{rut}-{dv}'

                        records_to_create.append(EmpresaSII(
                            rut=rut,
                            dv=dv,
                            razon_social=razon_social,
                            rut_completo=rut_completo
                        ))
                        
                        if len(records_to_create) >= batch_size:
                            # Perform bulk create on the 'sii' database
                            with transaction.atomic(using='sii'):
                                EmpresaSII.objects.using('sii').bulk_create(records_to_create)
                            processed_lines += len(records_to_create)
                            self.stdout.write(self.style.SUCCESS(f'Processed {processed_lines} lines...'))
                            records_to_create.clear()

                    except (ValueError, IndexError):
                        self.stdout.write(self.style.WARNING(f'Skipping malformed line: {line.strip()}'))
                        continue
                
                if records_to_create:
                    with transaction.atomic(using='sii'):
                        EmpresaSII.objects.using('sii').bulk_create(records_to_create)
                    processed_lines += len(records_to_create)
                    self.stdout.write(self.style.SUCCESS(f'Processed final batch of {len(records_to_create)} records.'))

            total_time = time.time() - start_time
            self.stdout.write(self.style.SUCCESS('--- Load Process Finished ---'))
            self.stdout.write(self.style.SUCCESS(f'Total records loaded: {processed_lines}'))
            self.stdout.write(self.style.SUCCESS(f'Total time: {total_time:.2f} seconds.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Error: File not found at {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {e}'))

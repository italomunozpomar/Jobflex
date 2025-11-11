# Jobflex/JFlex/management/commands/populate_locations.py

from django.core.management.base import BaseCommand
from JFlex.models import Ubicacion
import requests

class Command(BaseCommand):
    help = 'Populates the Ubicacion table with regions and communes from a static JSON file.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting population of Ubicacion table...'))

        url = 'https://gist.githubusercontent.com/juanbrujo/0fd2f4d126b3ce5a95a7dd1f28b3d8dd/raw/b8575eb82dce974fd2647f46819a7568278396bd/comunas-regiones.json'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            
            regiones_data = data.get('regiones', [])
            if not regiones_data:
                self.stdout.write(self.style.WARNING('No regions found in the JSON data.'))
                return

            created_count = 0
            for region_item in regiones_data:
                region_name = region_item.get('region')
                comunas = region_item.get('comunas', [])

                if region_name and comunas:
                    for comuna_name in comunas:
                        ubicacion, created = Ubicacion.objects.using('jflex_db').get_or_create(
                            region=region_name,
                            ciudad=comuna_name
                        )
                        if created:
                            created_count += 1
                            # self.stdout.write(f'Created: {region_name} - {comuna_name}')

            self.stdout.write(self.style.SUCCESS(f'Successfully populated Ubicacion table. Created {created_count} new entries.'))

        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f'Error fetching data from Gist: {e}'))
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f'Error parsing JSON data: {e}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An unexpected error occurred: {e}'))

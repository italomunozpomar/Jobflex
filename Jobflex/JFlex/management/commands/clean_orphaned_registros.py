# Jobflex/JFlex/management/commands/clean_orphaned_registros.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from JFlex.models import RegistroUsuarios

class Command(BaseCommand):
    help = 'Finds and deletes orphaned RegistroUsuarios records that do not have a corresponding User.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting cleanup of orphaned RegistroUsuarios...'))

        # Get all User IDs from the 'default' database
        try:
            user_ids = set(User.objects.using('default').values_list('id', flat=True))
            self.stdout.write(self.style.SUCCESS(f'Found {len(user_ids)} users in the auth database.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fetching users from default database: {e}'))
            return

        # Get all RegistroUsuarios from the 'jflex_db' database
        try:
            registros = RegistroUsuarios.objects.using('jflex_db').all()
            self.stdout.write(f'Found {len(registros)} RegistroUsuarios records to check.')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fetching RegistroUsuarios from jflex_db: {e}'))
            return

        orphaned_count = 0
        for registro in registros:
            if registro.id_registro_id not in user_ids:
                self.stdout.write(self.style.WARNING(
                    f'Found orphaned RegistroUsuarios with id_registro_id: {registro.id_registro_id}. Deleting...'
                ))
                try:
                    registro.delete(using='jflex_db')
                    orphaned_count += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'Could not delete registro {registro.id_registro_id}: {e}'
                    ))

        if orphaned_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {orphaned_count} orphaned records.'))
        else:
            self.stdout.write(self.style.SUCCESS('No orphaned records found. Your database is clean!'))

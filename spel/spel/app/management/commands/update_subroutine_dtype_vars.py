import csv

from app.models import (
    Modules,
    SubroutineActiveGlobalVars,
    Subroutines,
    TypeDefinitions,
    UserTypeInstances,
    UserTypes,
)
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update SubroutineActiveGlobalVars from CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file.")

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                subroutine_name = row["subroutine_name"].strip()
                instance_name = row["instance_name"].strip()
                module_name = row["module_name"].strip()
                user_type_name = row["user_type_name"].strip()
                member_type = row["member_type"].strip()
                member_name = row["member_name"].strip()
                status = row["status"].strip()

                # Lookup the Subroutine record.
                try:
                    subroutine_obj = Subroutines.objects.get(
                        subroutine_name=subroutine_name
                    )
                except Subroutines.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"Subroutine {subroutine_name} not found.")
                    )
                    continue

                # Lookup the UserTypeInstances record.
                try:
                    instance_obj = UserTypeInstances.objects.get(
                        instance_name=instance_name
                    )
                except UserTypeInstances.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"Instance {instance_name} not found.")
                    )
                    instance_obj = None  # or skip, based on your logic

                # Lookup the Module record.
                try:
                    module_obj = Modules.objects.get(module_name=module_name)
                except Modules.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"Module {module_name} not found.")
                    )
                    continue

                # Lookup the UserTypes record.
                try:
                    user_type_obj = UserTypes.objects.get(
                        user_type_name=user_type_name, module=module_obj
                    )
                except UserTypes.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"UserType {user_type_name} not found in module {module_name}."
                        )
                    )
                    continue

                # Lookup the TypeDefinitions record.
                try:
                    type_def_obj = TypeDefinitions.objects.get(
                        module=module_obj,
                        user_type=user_type_obj,
                        member_type=member_type,
                        member_name=member_name,
                    )
                except TypeDefinitions.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"TypeDefinition not found for module {module_name}, user_type {user_type_name}, member_type {member_type}, member_name {member_name}."
                        )
                    )
                    continue

                # Update or create the SubroutineActiveGlobalVars record.
                obj, created = SubroutineActiveGlobalVars.objects.update_or_create(
                    subroutine=subroutine_obj,
                    instance=instance_obj,  # this can be None if blank is allowed
                    member=type_def_obj,
                    defaults={"status": status},
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created active global var for subroutine {subroutine_name}."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Updated active global var for subroutine {subroutine_name}."
                        )
                    )
        self.stdout.write(self.style.SUCCESS("Update complete."))

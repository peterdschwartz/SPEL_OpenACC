# myapp/management/commands/update_all_data.py

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update Modules, ModuleDependency, and SubroutineActiveGlobalVars from CSV files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--modules-csv",
            type=str,
            required=True,
            help="Path to the CSV file for Modules and ModuleDependency updates.",
        )
        parser.add_argument(
            "--typedef-csv",
            type=str,
            required=False,
            help="Path to CSV file for TypeDefinitions",
        )
        parser.add_argument(
            "--instances-csv",
            type=str,
            required=False,
            help="Path to CSV file for UserTypeInstances",
        )
        parser.add_argument(
            "--active-globals-csv",
            type=str,
            required=False,
            help="Path to the CSV file for SubroutineActiveGlobalVars updates.",
        )

    def handle(self, *args, **options):
        modules_csv = options.get("modules_csv")
        typedef_csv = options.get("typedef_csv", None)
        instances_csv = options.get("instances_csv", None)
        active_globals_csv = options.get("active_globals_csv", None)

        self.stdout.write("Updating Modules and ModuleDependency...")
        call_command("update_modules_deps", modules_csv)

        if typedef_csv:
            self.stdout.write("Updating TypeDefinitions...")
            call_command("update_typedefs", csv_file=typedef_csv)
        if instances_csv:
            self.stdout.write("Updating UserTypeInstances...")
            call_command("update_instances", csv_file=instances_csv)
        if active_globals_csv:
            self.stdout.write("Updating SubroutineActiveGlobalVars...")
            call_command("update_active_globals", csv_file=active_globals_csv)

        self.stdout.write(self.style.SUCCESS("All updates complete."))

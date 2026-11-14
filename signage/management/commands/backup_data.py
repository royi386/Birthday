from datetime import datetime
import os
from pathlib import Path
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from signage.backup import create_backup

class Command(BaseCommand):
    help = "Create an integrity-checked ZIP of the database fixture and uploaded media."
    def add_arguments(self, parser):
        parser.add_argument("--output", default="backups")
        parser.add_argument("--filename", default="")
        parser.add_argument("--loop", action="store_true", help="Repeat backups at BACKUP_INTERVAL_SECONDS intervals.")
    def handle(self, *args, **options):
        folder = Path(options["output"]); folder.mkdir(parents=True, exist_ok=True)
        interval = max(60, int(os.environ.get("BACKUP_INTERVAL_SECONDS", "86400")))
        while True:
            try:
                name = options["filename"] or f"odds-backup-{timezone.now():%Y%m%d-%H%M%S}.zip"
                destination = create_backup(folder / name)
                self.stdout.write(self.style.SUCCESS(f"Backup created and verified: {destination}"))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Backup failed: {exc}"))
                if not options["loop"]: raise
            if not options["loop"]: break
            time.sleep(interval)

import shutil
import zipfile
from io import StringIO
from pathlib import Path
from django.conf import settings
from django.core.management import call_command

def create_backup(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    database = StringIO()
    call_command("dumpdata", format="json", indent=2, natural_foreign=True, natural_primary=True, stdout=database)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("database.json", database.getvalue())
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            for path in media_root.rglob("*"):
                if path.is_file(): archive.write(path, Path("media") / path.relative_to(media_root))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise OSError("Backup archive integrity check failed.")
    return destination

def archive_response_cleanup(path):
    try: Path(path).unlink(missing_ok=True)
    except OSError: pass

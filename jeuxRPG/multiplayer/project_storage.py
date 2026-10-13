from contextlib import contextmanager
import os


@contextmanager
def project_lock(directory):
    with (directory / '.controller.lock').open('a+b') as handle:
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Un autre contrôleur enregistre ce projet. Réessayez après sa sauvegarde.') from error
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sync_directory(directory):
    if os.name != 'nt':
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def prepare_recovery(directory, originals):
    import json
    recovery = directory / '.controller-recovery'
    recovery.mkdir()
    for name, value in originals.items():
        if value is not None:
            with (recovery / name).open('wb') as output:
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
    with (recovery / 'manifest.tmp').open('w', encoding='utf-8') as output:
        json.dump({name: value is not None for name, value in originals.items()}, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(recovery / 'manifest.tmp', recovery / 'manifest')
    sync_directory(recovery)
    sync_directory(directory)


def finish_recovery(directory):
    import shutil
    recovery = directory / '.controller-recovery'
    if (recovery / 'manifest').exists():
        os.replace(recovery / 'manifest', recovery / 'committed')
        sync_directory(recovery)
    shutil.rmtree(recovery)
    sync_directory(directory)


def recover_project(directory):
    import json
    from jeuxRPG.catalog_paths import CATALOG_NAMES
    recovery = directory / '.controller-recovery'
    if not recovery.exists():
        return
    manifest = recovery / 'manifest'
    if manifest.exists() and not (recovery / 'committed').exists():
        files = json.loads(manifest.read_text(encoding='utf-8'))
        if set(files) != set(CATALOG_NAMES) or any(type(value) is not bool for value in files.values()):
            raise ValueError('Journal de récupération invalide. Conservez les fichiers et restaurez une sauvegarde du projet.')
        for name, existed in files.items():
            if existed:
                temporary = recovery / (name + '.restore')
                with temporary.open('wb') as output:
                    output.write((recovery / name).read_bytes())
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, directory / name)
            else:
                (directory / name).unlink(missing_ok=True)
        sync_directory(directory)
    finish_recovery(directory)

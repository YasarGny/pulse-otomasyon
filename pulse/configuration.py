"""Read-only checks for existing production resources."""


def backup_folder(drive, folder_id=None):
    if not folder_id:
        matches = drive.children('root', 'PULSE')
        if len(matches) != 1:
            raise ValueError('Expected one existing PULSE backup folder; no folder was created')
        if matches[0].get('mimeType') != 'application/vnd.google-apps.folder':
            raise ValueError('PULSE backup path is not a folder')
        folder_id = matches[0]['id']
    if not isinstance(folder_id, str) or not folder_id or not all(c.isalnum() or c in '-_' for c in folder_id):
        raise ValueError('Invalid Drive folder ID')
    result = drive.request('GET', drive.api + '/' + folder_id,
                           params={'fields':'id,mimeType,trashed,capabilities(canAddChildren)'}).json()
    if result.get('mimeType') != 'application/vnd.google-apps.folder' or result.get('trashed'):
        raise ValueError('Invalid backup folder')
    if result.get('capabilities', {}).get('canAddChildren') is not True:
        raise ValueError('Backup folder does not allow adding files')
    return result

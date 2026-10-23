"""One explicitly authorized, SHA-pinned silence edit; never voice synthesis."""
import argparse
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from pulse.audio_quality import silence_gaps, assert_no_long_silence
from pulse.chapters import load_chapters, validate_chapters
from pulse.clips import validate_ranges
from pulse.publication import read_json, write_json, digest, audio_info, seal_release


def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True))


def remap(data, asset, stories, start, removed):
    result=copy.deepcopy(data)
    result['audio_sha256']=asset['sha256']
    end=start+removed
    def stamp(t):
        return round(t if t<=start else start if t<end else t-removed,3)
    result['chapters']=[{**row,'start':stamp(row['start'])} for row in data['chapters'] if not start<row['start']<end]
    result['story_ranges']=[{**row,'start':stamp(row['start']),'end':stamp(row['end'])}
        for row in data['story_ranges'] if stamp(row['end'])-stamp(row['start'])>=1]
    result['timing_edit']={'source_audio_sha256':data['audio_sha256'],'start':start,'removed_seconds':removed}
    validate_chapters(result,asset);validate_ranges(result,asset,stories)
    return result


def repair(published, output, instruction):
    published,output=Path(published),Path(output)
    manifest=read_json(published/'data/publication.json')
    assert manifest['status']=='ready' and manifest['publish_date']==instruction['date'], 'Repair date does not match current publication'
    source=published/'releases'/manifest['release_id']
    assert source.resolve().is_relative_to((published/'releases').resolve())
    section=instruction['section'];assert section in ('teknoloji','oyun')
    # Before editing, prove original bytes without approving their speech quality.
    for sec,entry in manifest['editions'].items():
        assert entry['file']==sec+'.json' and digest(source/entry['file'])==entry['sha256']
        edition=read_json(source/entry['file'])
        for kind in ('podcast','summary'):
            asset=edition[kind]
            assert asset['file']==sec+'/'+kind+'.mp3'
            assert digest(source/asset['file'])==asset['sha256']
    shutil.copytree(source,output,dirs_exist_ok=True)
    editions={s:read_json(output/(s+'.json')) for s in ('teknoloji','oyun')}
    data=editions[section];asset=data['podcast']
    already=asset.get('silence_edit',{}).get('source_sha256')==instruction['sha256']
    for sec,edition in editions.items():
        chapters=load_chapters(published/'assets/chapters',edition['podcast'])
        assert chapters, 'Reviewed chapter metadata is required before editing'
        write_json(output/'chapters'/(edition['podcast']['sha256']+'.json'),chapters)
    if already: return manifest
    assert asset['sha256']==instruction['sha256'], 'Refusing to edit a different audio file'
    a,b=instruction['start'],instruction['end']
    assert 0<a<b<asset['duration']
    path=output/asset['file']
    assert any(lo+.1<=a<b<=hi-.1 for lo,hi in silence_gaps(path)), 'Requested edit is not wholly within measured silence'
    before=duration(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for name,args in [('first',['-i',str(path),'-t',str(a)]),('second',['-ss',str(b),'-i',str(path)])]:
            subprocess.run(['ffmpeg','-nostdin','-v','error','-y',*args,'-map','0:a:0','-c:a','copy',str(tmp/(name+'.mp3'))],check=True)
        # MP3 encoder-delay metadata can make concat DTS overlap. A demuxer
        # duration allowance keeps DTS monotonic; no samples are inserted.
        prefix_duration=duration(tmp/'first.mp3')+.1
        (tmp/'concat.txt').write_text(f"file 'first.mp3'\nduration {prefix_duration:.6f}\nfile 'second.mp3'\n")
        target=tmp/'repaired.mp3'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(tmp/'concat.txt'),'-c:a','copy',str(target)],check=True)
        removed=before-duration(target)
        assert abs(removed-(b-a))<.15, 'Unexpected edit length'
        assert_no_long_silence(target)
        shutil.copyfile(target,path)
    old=load_chapters(output/'chapters',asset)
    data['podcast']={**asset,**audio_info(path,20),'silence_edit':{
        'source_sha256':asset['sha256'],'start':a,'end':b,'removed_seconds':round(removed,6),'method':'mp3-frame-copy'}}
    write_json(output/(section+'.json'),data)
    adjusted=remap(old,data['podcast'],data['stories'],a,removed)
    write_json(output/'chapters'/(data['podcast']['sha256']+'.json'),adjusted)
    result=seal_release(output,manifest['publish_date'],manifest['game_start'])
    from pulse.release_checks import check
    check(output)
    for sec in editions:
        if sec != section: assert digest(output/(sec+'.json'))==digest(source/(sec+'.json'))
        assert digest(output/sec/'summary.mp3')==digest(source/sec/'summary.mp3')
    print(f'Repaired only {removed:.3f}s of measured silence; MP3 audio packets copied without re-encoding.')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--published',default='.published');p.add_argument('--output',default='.audio-repair')
    p.add_argument('--instruction',required=True)
    a=p.parse_args();repair(a.published,a.output,read_json(a.instruction))

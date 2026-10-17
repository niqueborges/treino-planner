#!/usr/bin/env python3
"""Read-only inventory and checksum report for GIF exercise ZIP archives."""
from __future__ import annotations
import argparse, collections, hashlib, json, re, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives',nargs='+',type=Path,help='ZIP archives to inspect (not extracted or modified)')
    parser.add_argument('--output',type=Path,default=Path('data/metadata/dataset_report.json'))
    args=parser.parse_args()
    zips=[p for p in args.archives if p.is_file()]
    if not zips:
        parser.error('No readable ZIP archives were provided.')
    gifs=[]; all_entries=[]; failures=[]; category_counts=collections.Counter(); name_counts=collections.Counter(); hash_paths=collections.defaultdict(list); variant_counts=collections.Counter(); extensions=collections.Counter(); total_uncompressed=0
    for archive in zips:
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir(): continue
                    parts=Path(info.filename).parts
                    suffix=Path(info.filename).suffix.lower()
                    extensions[suffix or '[sem extensão]']+=1
                    all_entries.append({'zip':archive.name,'path':info.filename,'size_bytes':info.file_size})
                    if suffix!='.gif': continue
                    total_uncompressed+=info.file_size
                    name=Path(info.filename).name
                    name_counts[name.casefold()]+=1
                    category=parts[-2] if len(parts)>1 else '[raiz]'
                    category_counts[category]+=1
                    lower=info.filename.casefold()
                    variant='female' if re.search(r'female|feminino|mulher',lower) else 'male' if re.search(r'(?<![a-z])male|masculino|homem',lower) else 'unknown'
                    variant_counts[variant]+=1
                    digest=hashlib.sha256()
                    try:
                        with zf.open(info) as stream:
                            while chunk:=stream.read(1024*1024): digest.update(chunk)
                        sha=digest.hexdigest(); hash_paths[sha].append({'zip':archive.name,'path':info.filename})
                    except (OSError,zipfile.BadZipFile,RuntimeError) as exc:
                        sha=None;failures.append({'zip':archive.name,'path':info.filename,'error':str(exc)})
                    gifs.append({'zip':archive.name,'path':info.filename,'size_bytes':info.file_size,'sha256':sha,'category_path':list(parts[1:-1]),'variant_hint':variant})
        except (OSError,zipfile.BadZipFile) as exc:
            failures.append({'zip':archive.name,'error':str(exc)})
    duplicate_hashes={sha:items for sha,items in hash_paths.items() if len(items)>1}
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'source_archives':[{'name':p.name,'size_bytes':p.stat().st_size} for p in zips],'summary':{'zip_count':len(zips),'entry_count':len(all_entries),'gif_count':len(gifs),'unique_gif_contents':len(hash_paths),'duplicate_gif_copies':sum(len(v)-1 for v in duplicate_hashes.values()),'duplicate_hash_groups':len(duplicate_hashes),'gif_uncompressed_bytes':total_uncompressed,'variant_name_hints':dict(variant_counts),'filename_duplicates':sum(n-1 for n in name_counts.values() if n>1),'file_extensions':dict(extensions),'categories':dict(category_counts)},'duplicate_hashes':duplicate_hashes,'gifs':gifs,'non_gif_files':[x for x in all_entries if Path(x['path']).suffix.lower()!='.gif'],'failures':failures,'notes':['Variant hints are inferred from paths and filenames and require review.','A GIF file is a media asset, not automatically a distinct logical exercise.','Original ZIP archives were opened read-only and not extracted or changed.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    s=report['summary']
    print(f"ZIPs: {s['zip_count']} | GIFs: {s['gif_count']} | unique contents: {s['unique_gif_contents']} | duplicate copies: {s['duplicate_gif_copies']}")
    print(f"Variant name hints: {s['variant_name_hints']} | categories: {len(s['categories'])} | non-GIF files: {len(report['non_gif_files'])} | errors: {len(failures)}")
    print(f"Report: {args.output}")
    return 0 if not failures else 2
if __name__=='__main__': sys.exit(main())

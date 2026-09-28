"""Download referenced logos and build readable, self-hosted technology tiles.

Usage: python scripts/build_stack.py (requires network on the first run).
Selection source: profile/stack.json. Generated README section has stable markers.
"""
import base64
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache' / 'icons'
OUT = ROOT / 'assets' / 'stack'
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)

def fetch(tool):
    if not tool['url']:
        return tool, None
    path = CACHE / (tool['id'] + ('.png' if tool['url'].endswith('.png') else '.svg'))
    if path.exists():
        return tool, path.read_bytes()
    request = urllib.request.Request(tool['url'], headers={'User-Agent':'autumn714-profile-builder'})
    with urllib.request.urlopen(request, timeout=40) as response:
        data = response.read(2_000_000)
    if path.suffix == '.svg':
        ET.fromstring(data)
    elif not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError(f'Not a PNG: {tool["name"]}')
    path.write_bytes(data)
    return tool, data

def tile(tool, data):
    name = tool['name']
    parts = [f'<svg xmlns="{SVG}" width="90" height="94" viewBox="0 0 90 94" role="img"><title>{escape(name)}</title>',
             '<rect x="1" y=".5" width="88" height="93" rx="12" fill="#1b2436" stroke="#354055"/><rect x="14" y="2" width="62" height="62" rx="13" fill="#eaf0f8"/>']
    if tool['source'] == 'Text':
        parts.append(f'<text x="45" y="41" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="{20 if name=="SQL" else 15}" font-weight="700" fill="#263c68">{name}</text>')
    elif tool['url'].endswith('.png'):
        payload = base64.b64encode(data).decode('ascii')
        parts.append(f'<image x="21" y="9" width="48" height="48" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{payload}"/>')
    else:
        icon = ET.fromstring(data)
        for parent in list(icon.iter()):
            for child in list(parent):
                if child.tag.rsplit('}',1)[-1] in ('script','foreignObject','title','desc','metadata'):
                    parent.remove(child)
            for key in list(parent.attrib):
                if key.lower().startswith('on'):
                    del parent.attrib[key]
                if key.rsplit('}',1)[-1] == 'href' and not parent.attrib[key].startswith(('#','data:')):
                    raise ValueError(f'External SVG resource in {name}')
        if 'viewBox' not in icon.attrib:
            width = re.sub(r'[^0-9.]','',icon.attrib.get('width','24'))
            height = re.sub(r'[^0-9.]','',icon.attrib.get('height','24'))
            icon.set('viewBox',f'0 0 {width} {height}')
        icon.set('x','23'); icon.set('y','11'); icon.set('width','44'); icon.set('height','44')
        icon.set('preserveAspectRatio','xMidYMid meet')
        if tool['source'] == 'Simple Icons':
            # Dark colours preserve contrast on the light icon surface.
            icon.set('fill',tool['color'])
        parts.append(ET.tostring(icon,encoding='unicode'))
    splits={'Sentence Transformers':['Sentence','Transformers'],'Weights & Biases':['Weights &','Biases'],'GitHub Actions':['GitHub','Actions'],'Hugging Face':['Hugging Face'],'Apache Spark':['Apache Spark']}
    labels = splits.get(name,[name])
    for n,label in enumerate(labels):
        parts.append(f'<text x="45" y="{79+n*12}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="#cad5e8">{escape(label)}</text>')
    parts.append('</svg>')
    value='\n'.join(line.rstrip() for line in ''.join(parts).splitlines())+'\n'
    ET.fromstring(value)
    (OUT/(tool['id']+'.svg')).write_text(value,encoding='utf-8')

def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'profile/stack.json').read_text(encoding='utf-8'))
    tools=[tool for group in manifest['groups'] for tool in group['tools']]
    assert len(tools)==manifest['count']
    with ThreadPoolExecutor(max_workers=8) as pool:
        for tool,data in pool.map(fetch,tools):
            tile(tool,data)
    lines=['<!-- STACK:START -->']
    for group in manifest['groups']:
        lines += [f'#### {group["title"]}','', '<p>']
        for tool in group['tools']:
            lines.append(f'  <img src="./assets/stack/{tool["id"]}.svg" width="90" height="94" alt="{escape(tool["name"],quote=True)}" title="{escape(tool["name"],quote=True)}" />')
        lines += ['</p>','']
    lines.append('<!-- STACK:END -->')
    readme=ROOT/'README.md'
    source=readme.read_text(encoding='utf-8')
    start=source.index('<!-- STACK:START -->')
    end=source.index('<!-- STACK:END -->')+len('<!-- STACK:END -->')
    readme.write_text(source[:start]+'\n'.join(lines)+source[end:],encoding='utf-8')
    print(f'Generated {len(tools)} logo tiles across {len(manifest["groups"])} categories.')

if __name__=='__main__':
    main()

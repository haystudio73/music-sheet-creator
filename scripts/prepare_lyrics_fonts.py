import json,urllib.request
from pathlib import Path
fonts=[('Noto Sans','notosans'),('Noto Serif','notoserif'),('Roboto','roboto'),('Open Sans','opensans'),('Lora','lora'),('Merriweather','merriweather'),('Nunito','nunito'),('Source Sans 3','sourcesans3'),('Source Serif 4','sourceserif4')]
root=Path('frontend/public/fonts'); css=[]
for name,folder in fonts:
    base=f'https://api.github.com/repos/google/fonts/contents/ofl/{folder}'
    req=urllib.request.Request(base,headers={'User-Agent':'SheetStudio-font-bundler'})
    files=json.load(urllib.request.urlopen(req,timeout=30))
    font=next(f for f in files if f['name'].endswith('.ttf') and 'Italic' not in f['name'])
    lic=next(f for f in files if f['name']=='OFL.txt')
    for item,target in [(font,root/f'{folder}.ttf'),(lic,root/f'{folder}-OFL.txt')]:
        if not target.exists(): target.write_bytes(urllib.request.urlopen(item['download_url'],timeout=45).read())
    css.append(f'@font-face{{font-family:"{name}";src:url("/fonts/{folder}.ttf") format("truetype");font-style:normal;font-weight:100 900;font-display:swap}}')
    print(name, (root/f'{folder}.ttf').stat().st_size)
Path('frontend/src/fonts.css').write_text('\n'.join(css),encoding='utf-8')
(root/'NOTICE.md').write_text('Nine unmodified font families from https://github.com/google/fonts, bundled for offline lyrics display. Each family includes its original SIL Open Font License alongside the TTF.\n',encoding='utf-8')

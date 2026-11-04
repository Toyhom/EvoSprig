"""Printable comic pages from service-owned image URLs and editable panel captions."""

import io
import os
from html import escape
from urllib.parse import urlsplit


def compose(destination, title, panels):
    import httpx
    from PIL import Image, ImageDraw, ImageFont

    font_path = os.environ.get("EVOSPRIG_COMIC_FONT")
    font = ImageFont.truetype(font_path or "DejaVuSans.ttf", 28)
    heading = ImageFont.truetype(font_path or "DejaVuSans.ttf", 42)
    pages = []
    assets = []
    allowed = os.environ.get("EVOSPRIG_IMAGE_ORIGIN", "http://127.0.0.1:18880").rstrip("/")
    for index, panel in enumerate(panels):
        url = urlsplit(panel["image"])
        if f"{url.scheme}://{url.netloc}" != allowed or url.username or url.password:
            raise ValueError("Panel images must use EVOSPRIG_IMAGE_ORIGIN")
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=30) as client:
            with client.stream("GET", panel["image"]) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data)>20_000_000:
                        raise ValueError("Panel image exceeds 20 MB")
        picture = Image.open(io.BytesIO(data)).convert("RGB")
        picture.thumbnail((700,420))
        name = f"panel-{index+1:02d}.jpg"
        picture.save(destination / name, quality=92)
        assets.append(name)
    for offset in range(0,len(panels),4):
        page = Image.new("RGB", (1600,1400), "#fffdf8")
        draw = ImageDraw.Draw(page)
        draw.text((70,35),title[:45],font=heading,fill="#253245")
        for local, panel in enumerate(panels[offset:offset+4]):
            x,y=60+(local%2)*770,120+(local//2)*620
            draw.rounded_rectangle((x,y,x+730,y+580),radius=12,fill="white",outline="#c8cdd4",width=2)
            picture=Image.open(destination/assets[offset+local])
            page.paste(picture,(x+(730-picture.width)//2,y+10))
            text=panel["caption"]+"\n"+panel["dialogue"]
            line=""
            yy=y+440
            for character in text:
                if character=="\n" or draw.textlength(line+character,font=font)>670:
                    draw.text((x+25,yy),line,font=font,fill="#253245")
                    yy+=34
                    line=""
                    if yy>y+548:
                        raise ValueError("Panel text exceeds three lines; shorten the dialogue")
                if character!="\n":
                    line+=character
            draw.text((x+25,yy),line,font=font,fill="#253245")
        name=f"page-{len(pages)+1:02d}.jpg"
        page.save(destination/name,quality=92)
        pages.append(page)
    pages[0].save(destination/"chapter.pdf",save_all=True,append_images=pages[1:])
    html='<!doctype html><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{background:#f8f7f4;font:20px system-ui;max-width:1200px;margin:30px auto}.panels{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{padding:16px;background:white}img{width:100%}p{white-space:pre-wrap}</style><h1>'+escape(title)+'</h1><div class="panels">'
    for image,panel in zip(assets,panels,strict=True):
        html+='<article><img src="'+image+'"><p contenteditable="true">'+escape(panel['caption']+'\n'+panel['dialogue'])+'</p></article>'
    (destination/'chapter.html').write_text(html+'</div>')
    return {"files": ["chapter.pdf","chapter.html"]+[f"page-{i+1:02d}.jpg" for i in range(len(pages))],
            "pages":len(pages),"panels":len(panels)}

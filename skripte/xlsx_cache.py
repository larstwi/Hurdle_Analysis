import re, zipfile, io
from xml.sax.saxutils import escape

def sheet_dateien(daten_bytes):
    """Ordnet Blattnamen ihrer XML-Datei im Zip zu - unabhaengig von
    Attributreihenfolge, da openpyxl-Versionen hier variieren."""
    def attribute(tag_text):
        return dict(re.findall(r'(\w[\w:]*)="([^"]*)"', tag_text))

    with zipfile.ZipFile(io.BytesIO(daten_bytes)) as z:
        wbxml = z.read('xl/workbook.xml').decode('utf-8')
        rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8')

    name_zu_rid = {}
    for tag in re.findall(r'<sheet\b[^>]*/>', wbxml):
        a = attribute(tag)
        if 'name' in a and 'r:id' in a:
            name_zu_rid[a['name']] = a['r:id']

    rid_zu_ziel = {}
    for tag in re.findall(r'<Relationship\b[^>]*/>', rels):
        a = attribute(tag)
        if 'Id' in a and 'Target' in a and 'worksheets/' in a['Target']:
            ziel = a['Target'].split('worksheets/')[-1]
            rid_zu_ziel[a['Id']] = ziel

    return {name: rid_zu_ziel[rid] for name, rid in name_zu_rid.items() if rid in rid_zu_ziel}

def injiziere_cache_werte(daten_bytes, werte):
    """werte: {blattname: {zellref: (wert, ist_text)}} -> gepatchte Bytes.

    Schreibt den in Python berechneten Wert in den zwischengespeicherten
    <v>-Tag jeder Formelzelle. openpyxl laesst diesen leer; Excel und
    LibreOffice rechnen beim Oeffnen ohnehin neu, aber Numbers vertraut
    dem leeren Cache und zeigt sonst 0 statt des echten Werts.
    """
    dateien = sheet_dateien(daten_bytes)
    with zipfile.ZipFile(io.BytesIO(daten_bytes)) as z:
        inhalt = {n: z.read(n) for n in z.namelist()}
        infos = {n: z.getinfo(n) for n in z.namelist()}

    for blatt, zellwerte in werte.items():
        datei = 'xl/worksheets/' + dateien[blatt]
        xml = inhalt[datei].decode('utf-8')
        for ref, (wert, ist_text) in zellwerte.items():
            if wert is None:
                continue   # nichts zu injizieren, Formel bleibt wie von openpyxl geschrieben
            muster = re.compile(
                r'(<c r="' + re.escape(ref) + r'"[^>]*>)(<f>.*?</f>)(?:<v>.*?</v>)?(</c>)')
            def ersetze(m, wert=wert, ist_text=ist_text):
                kopf = m.group(1)
                if ist_text and 't="str"' not in kopf:
                    kopf = kopf[:-1] + ' t="str">'
                v = f'<v>{escape(str(wert))}</v>'
                return kopf + m.group(2) + v + m.group(3)
            xml, n = muster.subn(ersetze, xml, count=1)
            if n == 0:
                print(f'WARNUNG: Zelle {blatt}!{ref} nicht gefunden')
        inhalt[datei] = xml.encode('utf-8')

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in inhalt.items():
            zi = zipfile.ZipInfo(name, date_time=infos[name].date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = infos[name].external_attr
            z.writestr(zi, data)
    return out.getvalue()

import re, zipfile, io, copy
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('', NS)


def _q(tag):
    return f'{{{NS}}}{tag}'

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


def setze_rahmen_und_fuellung(daten_bytes, blattname, zellen):
    """zellen: {zellref: {'top'/'right'/'bottom'/'left': (stil, farbe)|None, 'fill': 'RRGGBB'|None}}

    Setzt Rahmen und Fuellung direkt in styles.xml/dem Blatt-XML, statt ueber
    openpyxl-Zellobjekte. Grund: bei vielen ueber zwei Zeilen verschmolzenen
    Zellen (wie in "Saison") vertauscht bzw. verwirft openpyxl beim Speichern
    verlaesslich reproduzierbar den Rahmen einzelner verschmolzener Zellen -
    im Python-Objekt ist er korrekt, in der gespeicherten Datei nicht mehr.
    Diese Funktion umgeht das, indem sie nach dem Speichern die betroffenen
    Zellen direkt auf einen neuen, garantiert korrekten Styleeintrag zeigen
    laesst (dedupliziert gegen bereits vorhandene border/fill/xf-Eintraege).
    """
    dateien = sheet_dateien(daten_bytes)
    with zipfile.ZipFile(io.BytesIO(daten_bytes)) as z:
        inhalt = {n: z.read(n) for n in z.namelist()}
        infos = {n: z.getinfo(n) for n in z.namelist()}

    sheet_datei = 'xl/worksheets/' + dateien[blattname]
    sheet_xml = inhalt[sheet_datei].decode('utf-8')

    stree = ET.fromstring(inhalt['xl/styles.xml'].decode('utf-8'))
    borders_el = stree.find(_q('borders'))
    fills_el = stree.find(_q('fills'))
    cellxfs_el = stree.find(_q('cellXfs'))
    borders_list = list(borders_el)
    fills_list = list(fills_el)
    xfs_list = list(cellxfs_el)

    def gleich(a, b):
        return ET.tostring(a, encoding='unicode') == ET.tostring(b, encoding='unicode')

    def side_el(tag, seite):
        e = ET.Element(_q(tag))
        if seite:
            stil, farbe = seite
            e.set('style', stil)
            ET.SubElement(e, _q('color')).set('rgb', farbe)
        return e

    def border_index(top, right, bottom, left):
        neu = ET.Element(_q('border'))
        for tag, seite in (('left', left), ('right', right), ('top', top), ('bottom', bottom)):
            neu.append(side_el(tag, seite))
        for i, b in enumerate(borders_list):
            if gleich(b, neu):
                return i
        borders_list.append(neu)
        return len(borders_list) - 1

    def fill_index(farbe):
        neu = ET.Element(_q('fill'))
        pf = ET.SubElement(neu, _q('patternFill'))
        pf.set('patternType', 'solid')
        ET.SubElement(pf, _q('fgColor')).set('rgb', farbe)
        for i, f in enumerate(fills_list):
            if gleich(f, neu):
                return i
        fills_list.append(neu)
        return len(fills_list) - 1

    def aktueller_style_index(ref):
        m = re.search(r'<c r="' + re.escape(ref) + r'"[^>]*?\bs="(\d+)"', sheet_xml)
        return int(m.group(1)) if m else 0

    ersatz = {}
    for ref, spec in zellen.items():
        alt_xf = xfs_list[aktueller_style_index(ref)]
        neu_xf = copy.deepcopy(alt_xf)
        bidx = border_index(spec.get('top'), spec.get('right'),
                             spec.get('bottom'), spec.get('left'))
        neu_xf.set('borderId', str(bidx))
        neu_xf.set('applyBorder', '1')
        if spec.get('fill'):
            neu_xf.set('fillId', str(fill_index(spec['fill'])))
            neu_xf.set('applyFill', '1')
        gefunden = None
        for i, xf in enumerate(xfs_list):
            if gleich(xf, neu_xf):
                gefunden = i
                break
        if gefunden is None:
            xfs_list.append(neu_xf)
            gefunden = len(xfs_list) - 1
        ersatz[ref] = gefunden

    for el in list(borders_el):
        borders_el.remove(el)
    for b in borders_list:
        borders_el.append(b)
    borders_el.set('count', str(len(borders_list)))

    for el in list(fills_el):
        fills_el.remove(el)
    for f in fills_list:
        fills_el.append(f)
    fills_el.set('count', str(len(fills_list)))

    for el in list(cellxfs_el):
        cellxfs_el.remove(el)
    for x in xfs_list:
        cellxfs_el.append(x)
    cellxfs_el.set('count', str(len(xfs_list)))

    inhalt['xl/styles.xml'] = ET.tostring(stree, encoding='unicode').encode('utf-8')

    for ref, neu_idx in ersatz.items():
        muster = re.compile(r'(<c r="' + re.escape(ref) + r'"[^>]*?)\bs="\d+"')
        neu_xml, n = muster.subn(lambda m: m.group(1) + f's="{neu_idx}"', sheet_xml, count=1)
        if n == 0:
            # Zelle hatte noch gar keinen Stylevermerk (Standardstil 0)
            muster2 = re.compile(r'(<c r="' + re.escape(ref) + r'")')
            neu_xml, n = muster2.subn(lambda m: m.group(1) + f' s="{neu_idx}"', sheet_xml, count=1)
        if n == 0:
            print(f'WARNUNG: Zelle {blattname}!{ref} nicht gefunden (Rahmen/Fuellung)')
        else:
            sheet_xml = neu_xml
    inhalt[sheet_datei] = sheet_xml.encode('utf-8')

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in inhalt.items():
            zi = zipfile.ZipInfo(name, date_time=infos[name].date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = infos[name].external_attr
            z.writestr(zi, data)
    return out.getvalue()

"""Restore the group's exact project title without changing technical content."""
from pathlib import Path
import json
import re
import shutil
import sys
import zipfile
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
TITLE = 'HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ'
REPORT = ROOT / 'reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx'
BACKUP = ROOT / '.cache/project_title_correction/original'


def backup(path):
    target = BACKUP / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def main():
    source = REPORT.with_suffix('.md')
    for path in (REPORT, REPORT.with_suffix('.pdf'), source, ROOT/'README.md',
                 ROOT/'README_DRIVER_MONITOR.md', ROOT/'tools/build_project_style_report.py'):
        backup(path)
    content = source.read_text(encoding='utf-8')
    content, n = re.subn(r'^Tên đề tài: .+$', 'Tên đề tài: '+TITLE, content, flags=re.MULTILINE)
    assert n == 2, 'Expected two explicit project-title declarations'
    source.write_text(content, encoding='utf-8')
    for name in ('README.md', 'README_DRIVER_MONITOR.md'):
        path=ROOT/name
        content=path.read_text(encoding='utf-8').splitlines(keepends=True)
        content[0]='# '+TITLE+'\n'
        path.write_text(''.join(content),encoding='utf-8')
    builder=ROOT/'tools/build_project_style_report.py'
    text=builder.read_text(encoding='utf-8')
    old='ỨNG DỤNG XỬ LÝ ẢNH VÀ TRÍ TUỆ NHÂN TẠO\\nTRONG HỆ THỐNG GIÁM SÁT\\nTRẠNG THÁI BUỒN NGỦ CỦA TÀI XẾ'
    assert old in text or 'PROJECT_TITLE' in text
    if 'PROJECT_TITLE =' not in text:
        text=text.replace('SOURCE = ROOT /', 'PROJECT_TITLE = '+repr(TITLE)+'\nSOURCE = ROOT /', 1)
    text=text.replace('doc.add_paragraph("'+old+'", "Title")','doc.add_paragraph(PROJECT_TITLE, "Title")')
    text=text.replace('d.core_properties.title="Hệ thống giám sát trạng thái buồn ngủ của tài xế"',
                      'd.core_properties.title=PROJECT_TITLE')
    compile(text,str(builder),'exec')
    builder.write_text(text,encoding='utf-8')
    namespaces={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    entries={}
    changes=[]
    with zipfile.ZipFile(REPORT) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            data=archive.read(member.filename)
            if member.filename=='word/document.xml':
                document=etree.fromstring(data)
                for p in document.xpath('//w:p',namespaces=namespaces):
                    nodes=p.xpath('.//w:t',namespaces=namespaces)
                    value=''.join(node.text or '' for node in nodes)
                    style=p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=namespaces)
                    if value.startswith('Tên đề tài:') or (style==['Title'] and value.startswith('ỨNG DỤNG XỬ LÝ ẢNH')):
                        replacement='Tên đề tài: '+TITLE if value.startswith('Tên đề tài:') else TITLE
                        nodes[0].text=replacement
                        for node in nodes[1:]:node.text=''
                        for br in p.xpath('.//w:br',namespaces=namespaces):br.getparent().remove(br)
                        changes.append({'before':value,'after':replacement})
                data=etree.tostring(document,xml_declaration=True,encoding='UTF-8',standalone=True)
            elif member.filename=='docProps/core.xml':
                document=etree.fromstring(data)
                titles=document.xpath('//*[local-name()="title"]')
                assert len(titles)==1
                titles[0].text=TITLE
                data=etree.tostring(document,xml_declaration=True,encoding='UTF-8',standalone=True)
            entries[member.filename]=(member,data)
    assert len(changes)==3, changes
    temporary=REPORT.with_suffix('.title-fix.docx')
    with zipfile.ZipFile(temporary,'w') as archive:
        for member,data in entries.values():archive.writestr(member,data)
    temporary.replace(REPORT)
    audit={'project_title':TITLE,'docx_paragraph_changes':changes,
           'technical_content_changed':False,'sources_backed_up_at':str(BACKUP)}
    audit_path=BACKUP.parent/'title_edit.json'
    audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()

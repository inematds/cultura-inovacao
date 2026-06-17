#!/usr/bin/env python3
"""
Normalizacao em massa do curso cultura-inovacao.
Transformacoes:
  1. Manifesto canonico: replica bloco data-inema-manifest do index.html em todos os 31 outros arquivos.
  2. Labels do nav: padroniza Fundamentos/Tecnicas/Avancado nos spans de navegacao.
  3. Remove diacriticos: transliteracao ASCII em todo o conteudo.
"""
import re
import os
import unicodedata
import sys

ROOT = "/home/nmaldaner/projetos/cultura-inovacao"

# === LISTA DE ARQUIVOS ===
def get_html_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # excluir .build e assets
        dirnames[:] = [d for d in dirnames if d not in ('.build', 'assets')]
        for f in filenames:
            if f.endswith('.html'):
                files.append(os.path.join(dirpath, f))
    files.sort()
    return files

def remove_diacritics(text):
    """Transliterate accented letters to ASCII via NFKD decomposition."""
    result = []
    for ch in text:
        nfkd = unicodedata.normalize('NFKD', ch)
        ascii_ch = nfkd.encode('ascii', 'ignore').decode('ascii')
        if ascii_ch:
            result.append(ascii_ch)
        else:
            # Non-letter Unicode (typographic quotes, em-dash, etc.) kept as-is
            result.append(ch)
    return ''.join(result)

# === TRANSFORMACAO 2: labels nav ===
NAV_REPLACEMENTS = [
    ('<span class="hidden sm:inline">Praticas</span>',    '<span class="hidden sm:inline">Tecnicas</span>'),
    ('<span class="hidden sm:inline">Metodologias</span>','<span class="hidden sm:inline">Tecnicas</span>'),
    ('<span class="hidden sm:inline">Lideranca</span>',   '<span class="hidden sm:inline">Avancado</span>'),
    ('<span class="hidden sm:inline">Implementacao</span>','<span class="hidden sm:inline">Avancado</span>'),
    # versoes acentuadas (antes de remover diacriticos, ou pode ja vir assim)
    ('<span class="hidden sm:inline">Práticas</span>',      '<span class="hidden sm:inline">Tecnicas</span>'),
    ('<span class="hidden sm:inline">Liderança</span>',     '<span class="hidden sm:inline">Avancado</span>'),
    ('<span class="hidden sm:inline">Implementação</span>', '<span class="hidden sm:inline">Avancado</span>'),
]

# === TRANSFORMACAO 1: manifesto canonico ===
MANIFEST_PATTERN = re.compile(
    r'[ \t]*<script type="application/json" data-inema-manifest>.*?</script>',
    re.DOTALL
)

def extract_canonical_manifest(index_path):
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    m = MANIFEST_PATTERN.search(content)
    if not m:
        raise ValueError(f"Manifesto canonico nao encontrado em {index_path}")
    return m.group(0)

def count_manifest_blocks(content):
    return len(MANIFEST_PATTERN.findall(content))

# === MAIN ===
def main():
    index_path = os.path.join(ROOT, 'index.html')
    files = get_html_files()

    print(f"Arquivos encontrados: {len(files)}")

    # Extrai manifesto canonico
    canonical_manifest = extract_canonical_manifest(index_path)
    id_count = canonical_manifest.count('"id":')
    print(f"Manifesto canonico extraido: {id_count} ocorrencias de \"id\":")

    changed = 0
    errors = []

    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                original = f.read()

            content = original

            # T1: substituir manifesto (em todos, inclusive index.html para garantir idempotencia)
            n_blocks = count_manifest_blocks(content)
            if n_blocks == 0:
                # Injeta antes de </head>
                if '</head>' in content:
                    content = content.replace('</head>', canonical_manifest + '\n</head>', 1)
                else:
                    errors.append(f"SEM_HEAD_SEM_MANIFESTO: {fpath}")
            elif n_blocks > 1:
                # Remove todos e coloca um
                content = MANIFEST_PATTERN.sub('', content, count=n_blocks - 1)
                content = MANIFEST_PATTERN.sub(canonical_manifest, content)
            else:
                content = MANIFEST_PATTERN.sub(canonical_manifest, content)

            # T2: labels nav (aplica antes de remover diacriticos para pegar versoes acentuadas)
            for old, new in NAV_REPLACEMENTS:
                content = content.replace(old, new)

            # T3: remover diacriticos
            content = remove_diacritics(content)

            if content != original:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                changed += 1

        except Exception as e:
            errors.append(f"ERRO {fpath}: {e}")

    print(f"Arquivos modificados: {changed}")
    if errors:
        print("ERROS:")
        for e in errors:
            print(f"  {e}")
    else:
        print("Sem erros.")

    # === VERIFICACAO ===
    print("\n=== VERIFICACAO ===")
    files2 = get_html_files()
    print(f"1. Arquivos processados: {len(files2)}")

    manifest_ok = 0
    manifest_bad = []
    for fpath in files2:
        with open(fpath, 'r', encoding='utf-8') as f:
            c = f.read()
        n = count_manifest_blocks(c)
        id_c = len(re.findall(r'"id":', c))
        # conta apenas os ids dentro do manifesto
        manifest_block_match = MANIFEST_PATTERN.search(c)
        ids_in_manifest = len(re.findall(r'"id":', manifest_block_match.group(0))) if manifest_block_match else 0
        if n == 1 and ids_in_manifest == 28:
            manifest_ok += 1
        else:
            manifest_bad.append(f"  {fpath}: blocos={n}, ids_no_manifesto={ids_in_manifest}")

    print(f"2. Arquivos com exatamente 1 manifesto e 28 ids: {manifest_ok}/{len(files2)}")
    if manifest_bad:
        print("   Fora do padrao:")
        for b in manifest_bad:
            print(b)

    # Verificacao diacriticos
    import unicodedata as ud
    diacritic_remaining = []
    for fpath in files2:
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for lineno, line in enumerate(lines, 1):
            for col, ch in enumerate(line):
                if ord(ch) > 127:
                    cat = ud.category(ch)
                    # So letras (L*) sao diacriticos; ignorar Mn (variation selectors, combining marks de emojis), Po, So, etc.
                    if cat.startswith('L'):
                        rel = os.path.relpath(fpath, ROOT)
                        diacritic_remaining.append(f"  {rel}:{lineno} char={repr(ch)} cat={cat}")

    total_diac = len(diacritic_remaining)
    print(f"3. Caracteres com diacritico remanescentes: {total_diac}")
    if total_diac > 0:
        for d in diacritic_remaining[:50]:
            print(d)
        if total_diac > 50:
            print(f"  ... e mais {total_diac - 50}")

    # Verificacao nav labels
    bad_nav = []
    BAD_PATTERNS = [
        '>Praticas<', '>Metodologias<', '>Lideranca<', '>Implementacao<',
        '>Práticas<', '>Liderança<',
    ]
    for fpath in files2:
        with open(fpath, 'r', encoding='utf-8') as f:
            c = f.read()
        span_pat = re.compile(r'<span class="hidden sm:inline">(.*?)</span>')
        for m in span_pat.finditer(c):
            label = m.group(0)
            for bp in BAD_PATTERNS:
                if bp in label:
                    rel = os.path.relpath(fpath, ROOT)
                    bad_nav.append(f"  {rel}: {label}")

    print(f"4. Nav com labels invalidos: {len(bad_nav)}")
    if bad_nav:
        for b in bad_nav:
            print(b)
    else:
        print("   Nenhum - todos os spans de nav estao com Fundamentos/Tecnicas/Avancado.")

if __name__ == '__main__':
    main()

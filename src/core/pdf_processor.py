"""
Responsabilidade única: transformar um PDF em texto limpo.
Antes: fazer_upload_pdf() usava google.colab.files (só funciona no Colab).
Agora: recebe o caminho local do arquivo (ex.: data/inputs/capitulo.pdf).
"""
import re
from pathlib import Path
import fitz  # PyMuPDF


def extrair_texto_pdf(caminho_pdf: str) -> str:
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_pdf}")

    doc = fitz.open(caminho_pdf)
    paginas = []
    for pagina in doc:
        texto_pagina = pagina.get_text("text")
        if isinstance(texto_pagina, str) and texto_pagina.strip():
            paginas.append(texto_pagina)
    doc.close()

    if not paginas:
        raise ValueError("Nenhum texto extraído. O PDF pode ser escaneado (sem OCR).")

    texto = "\n".join(paginas)
    texto = re.sub(r"-\n([a-záéíóúâêôãõ])", r"\1", texto)  # remove hifenização de fim de linha
    texto = re.sub(r"\n{3,}", "\n\n", texto)                # colapsa linhas em branco excessivas
    return _juntar_linhas_quebradas(texto)


def _juntar_linhas_quebradas(texto: str) -> str:
    """
    PDFs quebram linha pelo layout visual, não pela gramática. Isso faz uma
    única frase virar 2 "sentenças" para o nosso parser. Regra simples: se
    uma linha NÃO termina em pontuação final (. ! ? : ; " ”), ela continua
    na próxima linha -> junta com espaço. Linha em branco continua sendo
    respeitada como fim de parágrafo.
    """
    paragrafos = texto.split("\n\n")
    resultado = []
    for paragrafo in paragrafos:
        linhas = [linha.strip() for linha in paragrafo.split("\n") if linha.strip()]
        linha_unica = ""
        for linha in linhas:
            if not linha_unica:
                linha_unica = linha
            elif re.search(r'[\.\!\?\:\;"”]\s*$', linha_unica):
                linha_unica += "\n" + linha  # frase anterior já fechou, mantém quebra
            else:
                linha_unica += " " + linha  # frase continua, junta
        resultado.append(linha_unica)
    return "\n\n".join(resultado)
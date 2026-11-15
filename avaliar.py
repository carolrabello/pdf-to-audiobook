"""
Acurácia da atribuição de falas (não gasta nenhuma chamada de API).

  1) python avaliar.py exportar data/inputs/capitulo.pdf
       Cria data/outputs/capitulo/avaliacao.csv, com uma linha por fala.
       Para um livro completo, recorte o capítulo: python avaliar.py exportar data/inputs/livro.pdf VIII
  2) Abra o CSV no Excel/Planilhas e preencha a coluna "acertou" de cada linha:
       S = o personagem indicado pelo sistema está certo
           ("Desconhecido" é S só quando o texto não identifica quem fala)
       N = está errado (se quiser, escreva o certo em "observacao")
           ("Desconhecido" é N quando o texto identifica o falante, mesmo sem nome)
       X = bloco inválido (ex.: fala vazia, erro do parser); não entra na conta
  3) python avaliar.py calcular data/outputs/capitulo/avaliacao.csv
       Mostra a acurácia geral e a tabela por regra, no formato do relatório.
"""
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

COLUNAS = ["n", "fala", "narracao_antes", "narracao_depois", "personagem_sistema", "regra", "acertou", "observacao"]

# Camadas do código agrupadas com os nomes usados nas tabelas do relatório.
GRUPOS = [
    ("Sujeito Oculto / Elipse", {"elipse_sujeito", "elipse_relativa"}),
    ("Nome Próprio Exato", {"nome_proprio"}),
    ("Correferência Pronomial (fem/masc)", {"coref_fem", "coref_masc"}),
    ("Substantivo / Descrição", {"descricao", "sujeito_composto"}),
    ("Sem regra (fallback)", {"fallback"}),
]


def exportar(caminho_pdf: str, capitulo: str | None = None):
    from pipeline import processar_pipeline
    from src.core.pdf_processor import nome_da_saida
    from src.core.text_parser import vizinhos_narracao

    saida = Path("data/outputs") / nome_da_saida(caminho_pdf, capitulo) / "avaliacao.csv"
    if saida.exists():
        sys.exit(f"{saida} já existe e pode conter as suas marcações. Renomeie ou apague para exportar de novo.")

    blocos, _ = processar_pipeline(caminho_pdf, capitulo)
    saida.parent.mkdir(parents=True, exist_ok=True)

    def trecho(j):
        return blocos[j]["texto"][:120] if j is not None else ""

    n = 0
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: o Excel abre com acentos certos
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(COLUNAS)
        for i, bloco in enumerate(blocos):
            if bloco["tipo"] != "fala":
                continue
            n += 1
            antes, depois = vizinhos_narracao(blocos, i)
            escritor.writerow([n, bloco["texto"][:120], trecho(antes), trecho(depois),
                               bloco["personagem"], bloco["camada_attr"], "", ""])
    print(f"{n} falas exportadas para {saida}")


def _ler_csv(caminho: str) -> list:
    for codificacao in ("utf-8-sig", "cp1252"):  # o Excel em português às vezes salva em cp1252
        try:
            texto = Path(caminho).read_text(encoding=codificacao)
            break
        except UnicodeDecodeError:
            continue
    separador = ";" if ";" in texto.splitlines()[0] else ","
    return list(csv.DictReader(io.StringIO(texto), delimiter=separador))


def _pct(acertos: int, total: int) -> str:
    return f"{100 * acertos / total:.1f}%".replace(".", ",") if total else "-"


def calcular(caminho_csv: str):
    por_camada = defaultdict(lambda: [0, 0])  # camada do código -> [falas, acertos]
    invalidas = pendentes = 0
    desconhecido = [0, 0]                     # [falas "Desconhecido", marcadas S]

    for linha in _ler_csv(caminho_csv):
        marca = (linha["acertou"] or "").strip().upper()
        if marca == "X":
            invalidas += 1
        elif marca not in ("S", "N"):
            pendentes += 1
        else:
            por_camada[linha["regra"]][0] += 1
            por_camada[linha["regra"]][1] += marca == "S"
            if linha["personagem_sistema"] == "Desconhecido":
                desconhecido[0] += 1
                desconhecido[1] += marca == "S"

    total = sum(v[0] for v in por_camada.values())
    acertos = sum(v[1] for v in por_camada.values())
    if not total:
        sys.exit("Nenhuma linha marcada com S ou N. Preencha a coluna 'acertou' e tente de novo.")

    # agrupa as camadas do código nas linhas da tabela do relatório
    grupos = defaultdict(lambda: [0, 0])
    for camada, (falas, ok) in por_camada.items():
        nome = next((g for g, camadas in GRUPOS if camada in camadas), "Outras")
        grupos[nome][0] += falas
        grupos[nome][1] += ok

    print(f"Falas avaliadas: {total} | blocos inválidos (X): {invalidas} | sem marcação: {pendentes}")
    print(f"Acertos: {acertos} | Acurácia geral: {_pct(acertos, total)}")
    print(f"Falas atribuídas a 'Desconhecido': {desconhecido[0]} (marcadas como acerto: {desconhecido[1]})\n")

    print("Detalhe por camada do código:")
    print(f"{'Camada':<20} {'Falas':>6} {'Acertos':>8} {'Acurácia':>9}")
    for camada, (falas, ok) in sorted(por_camada.items(), key=lambda kv: -kv[1][0]):
        print(f"{camada:<20} {falas:>6} {ok:>8} {_pct(ok, falas):>9}")

    print("\nTabela para o relatório (cole no Word e use Inserir > Tabela > Converter Texto em Tabela):")
    print("Regra de Atribuição\tFalas Avaliadas\tAcertos\tAcurácia")
    nomes = [g for g, _ in GRUPOS] + (["Outras"] if "Outras" in grupos else [])
    for nome in nomes:
        falas, ok = grupos[nome]
        print(f"{nome}\t{falas or '-'}\t{ok if falas else '-'}\t{_pct(ok, falas)}")
    print(f"Total Geral\t{total}\t{acertos}\t{_pct(acertos, total)}")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ("exportar", "calcular"):
        sys.exit(__doc__)
    if sys.argv[1] == "exportar":
        exportar(*sys.argv[2:])
    else:
        calcular(sys.argv[2])
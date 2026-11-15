"""
Confere se os rótulos já preenchidos (avaliacao-preenchida.csv) ainda correspondem ao que o código
atual produz, sem escrever nada e sem gastar API:

  python conferir_rotulos.py

Para cada capítulo, roda o pipeline e compara fala, personagem e regra com a planilha preenchida.
Se tudo bater, as acurácias do relatório continuam valendo para a versão atual do código.
"""
import csv
from pathlib import Path

from gerar_todos import CAPITULOS, ENTRADAS
from pipeline import processar_pipeline
from src.core.pdf_processor import nome_da_saida


def _ler(caminho: Path) -> list:
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main():
    total_dif = 0
    for pdf, capitulo in CAPITULOS:
        caminho = str(ENTRADAS / pdf)
        nome = nome_da_saida(caminho, capitulo)
        planilha = Path("data/outputs") / nome / "avaliacao-preenchida.csv"
        if not planilha.exists():
            print(f"{nome}: sem avaliacao-preenchida.csv")
            continue
        blocos, _ = processar_pipeline(caminho, capitulo)
        falas = [b for b in blocos if b["tipo"] == "fala"]
        linhas = _ler(planilha)
        difs = []
        if len(falas) != len(linhas):
            difs.append(f"  número de falas: código {len(falas)} x planilha {len(linhas)}")
        for n, (b, r) in enumerate(zip(falas, linhas), 1):
            if (b["texto"][:120].strip() != r["fala"].strip() or b["personagem"] != r["personagem_sistema"]
                    or b["camada_attr"] != r["regra"]):
                difs.append(f"  fala {n}: código {b['personagem']}/{b['camada_attr']} x planilha "
                            f"{r['personagem_sistema']}/{r['regra']} | {r['fala'][:40]}")
        total_dif += len(difs)
        print(f"{nome}: {'OK' if not difs else str(len(difs)) + ' diferença(s)'}")
        for d in difs:
            print(d)
    print("\nTudo confere." if not total_dif else f"\n{total_dif} diferença(s) no total: revise antes de usar os números do relatório.")


if __name__ == "__main__":
    main()

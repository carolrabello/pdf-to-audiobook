"""
Gera (ou simula) todos os capítulos avaliados em sequência e salva um levantamento em CSV.

  python gerar_todos.py            -> simulação (não gasta chamadas de API): só mede o PLN
  python gerar_todos.py --gerar    -> gera os MP3 e mede tempo e duração

O modelo usado é o MODELO_TTS do config.py. Cada MP3 é renomeado com o modelo no nome
(ex.: o-cortico-original-cap-VIII-pro.mp3), para a execução seguinte não sobrescrevê-lo.
O levantamento vai para data/outputs/levantamento_<modelo>.csv e o texto que sai no terminal
de cada capítulo vai para data/outputs/<capitulo>/log_<modelo>.txt.
"""
import argparse
import csv
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from config import MODELO_TTS
from pipeline import processar_pipeline
from src.core.pdf_processor import nome_da_saida
from src.services.tts_service import preparar_segmentos, _info_voz, dry_run, gerar_audiobook

ENTRADAS = Path("data/inputs")
CAPITULOS = [
    ("alice-no-pais-das-maravilhas.pdf", "Viagem à toca dos coelhos"),
    ("alice-no-pais-das-maravilhas.pdf", "Lago das lágrimas"),
    ("alice-no-pais-das-maravilhas.pdf", "Uma reunião original"),
    ("O-Picapau-Amarelo-original.pdf", "I"),
    ("O-Picapau-Amarelo-original.pdf", "II"),
    ("O-Picapau-Amarelo-original.pdf", "III"),
    ("o-cortico-original.pdf", "VIII"),
    ("memorias-postumas-de-bras-cubas.pdf", "1"),
    ("memorias-postumas-de-bras-cubas.pdf", "6"),
    ("memorias-postumas-de-bras-cubas.pdf", "7"),
]
COLUNAS = ["data_hora", "capitulo", "modelo", "modo", "falas", "segmentos", "personagens", "vozes_distintas",
           "segmentos_novos", "tempo_pln_s", "tempo_total_min", "duracao_audio_min", "mp3", "status"]


class Tee:
    """Escreve no terminal e no arquivo de log ao mesmo tempo."""
    def __init__(self, *saidas):
        self.saidas = saidas

    def write(self, texto):
        for s in self.saidas:
            s.write(texto)

    def flush(self):
        for s in self.saidas:
            s.flush()


def _contar_wavs(pasta: Path) -> int:
    return len(list(pasta.glob("seg_*.wav"))) if pasta.exists() else 0


def processar(pdf: str, capitulo: str, gerar: bool, modelo: str) -> dict:
    caminho = str(ENTRADAS / pdf)
    nome = nome_da_saida(caminho, capitulo)
    pasta = Path("data/outputs") / nome
    pasta.mkdir(parents=True, exist_ok=True)
    linha = {"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "capitulo": nome, "modelo": MODELO_TTS,
             "modo": "gerar" if gerar else "simulacao"}

    inicio = time.perf_counter()
    blocos, catalogo = processar_pipeline(caminho, capitulo)
    linha["tempo_pln_s"] = round(time.perf_counter() - inicio, 1)
    segmentos = preparar_segmentos(blocos)
    linha["falas"] = sum(1 for b in blocos if b["tipo"] != "narrador")
    linha["segmentos"] = len(segmentos)
    linha["personagens"] = len({s["personagem"] for s in segmentos})
    linha["vozes_distintas"] = len({_info_voz(catalogo, s["personagem"])["voz"] for s in segmentos})

    if not gerar:
        dry_run(blocos, catalogo)
        linha["status"] = "simulacao"
        return linha

    cache = pasta / "cache"
    antes = _contar_wavs(cache)
    arquivo = Path(gerar_audiobook(blocos, catalogo, nome))
    linha["tempo_total_min"] = round((time.perf_counter() - inicio) / 60, 1)
    linha["segmentos_novos"] = _contar_wavs(cache) - antes

    destino = arquivo.with_name(f"{nome}-{modelo}.mp3")
    shutil.copyfile(arquivo, destino)
    from pydub import AudioSegment
    linha["duracao_audio_min"] = round(AudioSegment.from_file(str(destino)).duration_seconds / 60, 1)
    linha["mp3"] = str(destino)
    linha["status"] = "ok"
    return linha


def main():
    parser = argparse.ArgumentParser(description="Gera todos os capítulos avaliados e salva o levantamento")
    parser.add_argument("--gerar", action="store_true", help="Gera os MP3 (gasta chamadas ao Gemini TTS)")
    args = parser.parse_args()

    modelo = "pro" if "pro" in MODELO_TTS else "flash" if "flash" in MODELO_TTS else MODELO_TTS
    csv_saida = Path("data/outputs") / f"levantamento_{modelo}.csv"
    csv_saida.parent.mkdir(parents=True, exist_ok=True)
    novo = not csv_saida.exists()
    print(f"Modelo: {MODELO_TTS} | modo: {'gerar' if args.gerar else 'simulação'} | {len(CAPITULOS)} capítulos")

    inicio_geral = time.perf_counter()
    with open(csv_saida, "a", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        if novo:
            escritor.writeheader()
        for i, (pdf, capitulo) in enumerate(CAPITULOS, 1):
            print(f"\n===== [{i}/{len(CAPITULOS)}] {pdf} | {capitulo} =====")
            nome = nome_da_saida(str(ENTRADAS / pdf), capitulo)
            pasta = Path("data/outputs") / nome
            pasta.mkdir(parents=True, exist_ok=True)
            terminal = sys.stdout
            try:
                with open(pasta / f"log_{modelo}.txt", "a", encoding="utf-8") as log:
                    sys.stdout = Tee(terminal, log)
                    linha = processar(pdf, capitulo, args.gerar, modelo)
            except Exception as erro:  # um capítulo com erro não interrompe os demais
                linha = {"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "capitulo": nome,
                         "modelo": MODELO_TTS, "status": f"erro: {erro}"}
            finally:
                sys.stdout = terminal
            escritor.writerow(linha)
            f.flush()
            print(f"-> {linha.get('status')} | {linha.get('segmentos', '-')} segmentos | "
                  f"{linha.get('tempo_total_min', '-')} min | áudio {linha.get('duracao_audio_min', '-')} min")

    print(f"\nTempo total do lote: {(time.perf_counter() - inicio_geral) / 60:.1f} min")
    print(f"Levantamento salvo em: {csv_saida}")


if __name__ == "__main__":
    main()

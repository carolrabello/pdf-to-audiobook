import spacy

from src.config import BANCO_VOZES_GEMINI
from src.core.nlp_analyzer import (
    inferir_genero_por_contexto,
    identificar_personagem,
    extrair_tag_emocao,
)
from src.core.text_parser import parsear_texto, selecionar_atribuidor
from src.core.catalog_manager import registrar_personagem, atualizar_coref


def processar_pipeline(texto: str, modo_dialogo: str = "auto"):
    print("Carregando modelos NLP (spaCy)...")
    nlp = spacy.load("pt_core_news_lg")
    blocos = parsear_texto(texto, modo=modo_dialogo)

    catalogo = {
        "Narrador": {"voz": BANCO_VOZES_GEMINI["narrador"], "genero": "narrador"}
    }
    estado_coref = {"ultimo_fem": None, "ultimo_masc": None}
    ultimo = None

    for i, bloco in enumerate(blocos):
        if bloco["tipo"] != "fala":
            continue

        atribuidor = selecionar_atribuidor(blocos, i)
        antes = (
            blocos[i - 1]["texto"]
            if i > 0 and blocos[i - 1]["tipo"] == "narrador"
            else ""
        )
        depois = (
            blocos[i + 1]["texto"]
            if i + 1 < len(blocos) and blocos[i + 1]["tipo"] == "narrador"
            else ""
        )
        contexto_total = f"{antes} {depois}".strip()

        # IA infere o gênero baseada na morfologia da frase
        genero_ctx = inferir_genero_por_contexto(nlp, contexto_total)
        personagem, camada = identificar_personagem(nlp, atribuidor, estado_coref)

        if not personagem:
            if ultimo:
                genero_ultimo = catalogo.get(ultimo, {}).get("genero", "neutro")
                # Quebra a herança se houver conflito de gênero no contexto morfológico
                if (
                    genero_ctx != "neutro"
                    and genero_ultimo != "neutro"
                    and genero_ctx != genero_ultimo
                ):
                    personagem = "Desconhecido"
                else:
                    personagem = ultimo
            else:
                personagem = "Desconhecido"

        nome_final = registrar_personagem(personagem, genero_ctx, catalogo)

        bloco["personagem"] = nome_final
        bloco["camada_attr"] = camada or "fallback"
        ultimo = nome_final

        atualizar_coref(nome_final, catalogo, estado_coref)

        tag, fonte = extrair_tag_emocao(nlp, contexto_total)
        bloco["emocao"] = tag
        bloco["fonte_emocao"] = fonte

    return blocos, catalogo

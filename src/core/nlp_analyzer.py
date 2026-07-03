import re
from deep_translator import GoogleTranslator

from config import (
    _LABELS_FALANTE,
    _PRONOMES_FEM,
    _PRONOMES_MASC,
    _STOPWORDS_EMOCAO,
    VERBOS_ELOCUCAO_LEMMAS,
)


def _extrair_entidades_falantes(doc) -> list:
    return [
        ent.text.strip().title() for ent in doc.ents if ent.label_ in _LABELS_FALANTE
    ]


def inferir_genero_por_contexto(nlp_model, contexto: str) -> str:
    """
    Substitui dicionários engessados pela análise morfológica real do spaCy.
    """
    if not contexto:
        return "neutro"

    doc = nlp_model(contexto)
    score_f, score_m = 0, 0

    for token in doc:
        # Analisa pronomes, substantivos, nomes próprios e adjetivos
        if token.pos_ in ["NOUN", "ADJ", "PRON", "PROPN"]:
            gen = token.morph.get("Gender")
            if "Fem" in gen:
                score_f += 1
            elif "Masc" in gen:
                score_m += 1

    if score_f > score_m:
        return "feminino"
    if score_m > score_f:
        return "masculino"
    return "neutro"


def identificar_personagem(nlp_model, sentenca: str, estado_coref: dict) -> tuple:
    if not sentenca:
        return None, None
    doc = nlp_model(sentenca)

    # Verifica se existe verbo de elocução utilizando Lemmas
    if not any(t.lemma_.lower() in VERBOS_ELOCUCAO_LEMMAS for t in doc):
        return None, None

    entidades = _extrair_entidades_falantes(doc)

    for token in doc:
        if token.lemma_.lower() not in VERBOS_ELOCUCAO_LEMMAS:
            continue

        for filho in token.children:
            if filho.dep_ != "nsubj":
                continue

            texto_filho = filho.text.lower()
            if texto_filho in _PRONOMES_FEM and estado_coref.get("ultimo_fem"):
                return estado_coref["ultimo_fem"], "coref_fem"
            if texto_filho in _PRONOMES_MASC and estado_coref.get("ultimo_masc"):
                return estado_coref["ultimo_masc"], "coref_masc"

            # SUBSTITUI O _NAO_NOME: Confia na marcação de Substantivo Próprio do spaCy
            if filho.pos_ == "PROPN":
                nome = filho.text.strip().title()
                if len(nome) > 2:
                    return nome, "dep_parsing_propn"

    if entidades:
        return entidades[0], "ner_fallback"
    return None, None


_tradutor_en = GoogleTranslator(source="pt", target="en")


def _traduzir_token(token_pt: str) -> str:
    try:
        traduzido = _tradutor_en.translate(token_pt.lower())
        return re.sub(r"[^a-z_]", "", traduzido.lower().replace(" ", "_"))
    except Exception:
        return "neutral"


def extrair_tag_emocao(nlp_model, texto_narrador: str) -> tuple:
    if not texto_narrador.strip():
        return "neutral", "sem_narrador -> neutral"
    doc = nlp_model(texto_narrador)
    palavras = []

    for token in doc:
        if token.lemma_.lower() in VERBOS_ELOCUCAO_LEMMAS:
            for filho in token.children:
                if filho.pos_ == "ADV" and filho.text.lower() not in _STOPWORDS_EMOCAO:
                    palavras.append((filho.text.lower(), "adv_verbo"))
                    for neto in filho.children:
                        if (
                            neto.dep_ == "conj"
                            and neto.pos_ == "ADV"
                            and neto.text.lower() not in _STOPWORDS_EMOCAO
                        ):
                            palavras.append((neto.text.lower(), "adv_conj"))
        if token.text.lower() in {"voz", "tom", "olhar", "expressão"}:
            for filho in token.children:
                if (
                    filho.pos_ in ("ADJ", "ADV")
                    and filho.text.lower() not in _STOPWORDS_EMOCAO
                ):
                    palavras.append((filho.text.lower(), "descritor"))
                    for neto in filho.children:
                        if (
                            neto.dep_ == "conj"
                            and neto.pos_ in ("ADJ", "ADV")
                            and neto.text.lower() not in _STOPWORDS_EMOCAO
                        ):
                            palavras.append((neto.text.lower(), "descritor_conj"))

    if not palavras:
        return "neutral", "sem_modificadores -> neutral"

    tags, log, vistos = [], [], set()
    for pt_word, _ in palavras:
        if pt_word in vistos:
            continue
        vistos.add(pt_word)
        en_word = _traduzir_token(pt_word)
        if en_word and en_word != "neutral":
            tags.append(en_word)
            log.append(f"{pt_word} -> [{en_word}]")

    if not tags:
        return "neutral", "falha_traducao -> neutral"
    return ", ".join(tags), " | ".join(log)

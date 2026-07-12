"""
Responsabilidade única: "entender" o texto usando o spaCy.
Aqui ficam os itens 2 e 3 do TCC:
  - Item 2: inferir gênero de personagens não nomeados, pelo contexto.
  - Item 3: em vez de dicionário fixo de nomes/personagens, usa:
      (a) morfologia do spaCy para gênero (Gender=Fem/Masc),
      (b) similaridade de vetores para saber se um substantivo comum
          se refere a uma pessoa (ex.: "senhora", "velho"),
      (c) um "estado de saliência" simples (quem foi mencionado por
          último) para resolver pronomes e sujeitos elípticos - uma
          versão enxuta de correferência, sem depender de um modelo
          de coreference pronto (não existe um confiável para PT-BR).
"""
import re
import spacy
from deep_translator import GoogleTranslator

from config import (
    VERBOS_ELOCUCAO_LEMMAS, ANCORAS_HUMANO, LIMIAR_SIMILARIDADE_HUMANO,
    PALAVRAS_TOM, STOPWORDS_EMOCAO, PRONOMES_FEM, PRONOMES_MASC,
    LABELS_FALANTE, MODELO_SPACY,
)

_tradutor_en = GoogleTranslator(source="pt", target="en")


def carregar_modelo():
    print("Carregando modelo NLP (spaCy)...")
    return spacy.load(MODELO_SPACY)


def _genero_por_morfologia(token) -> str:
    """Usa a marcação morfológica do spaCy (estatística, treinada em corpus
    real) em vez de adivinhar gênero pela terminação da palavra."""
    genero = token.morph.get("Gender")
    if "Fem" in genero:
        return "feminino"
    if "Masc" in genero:
        return "masculino"
    return "neutro"


def _eh_substantivo_humano(nlp_model, token) -> bool:
    """Substitui uma lista fixa tipo {'senhora','velho','moça'...} por
    similaridade semântica com um punhado de âncoras genéricas.
    Aceita NOUN e também ADJ, porque em PT-BR é comum usar um adjetivo
    substantivado para se referir a uma pessoa (ex.: 'os fiéis', 'o velho',
    'a idosa') sem um substantivo explícito ao lado."""
    if token.pos_ not in ("NOUN", "ADJ") or not token.has_vector:
        return False
    for ancora in ANCORAS_HUMANO:
        ancora_tok = nlp_model.vocab[ancora]
        if ancora_tok.has_vector and token.similarity(ancora_tok) >= LIMIAR_SIMILARIDADE_HUMANO:
            return True
    return False


def _traco_emocional(nlp_model, token) -> str:
    """Pega um adjetivo que descreve diretamente a pessoa (ex.: 'a triste
    senhora' -> 'triste'), para usar como pista de emoção se a fala dela
    não tiver nenhuma outra pista mais direta."""
    for filho in token.children:
        if filho.dep_ == "amod" and filho.text.lower() not in STOPWORDS_EMOCAO:
            return filho.text.lower()
    return ""


def extrair_entidades_referenciais(nlp_model, texto: str, exigir_sujeito: bool = True) -> list:
    """Retorna candidatos a personagem citados num trecho de narração:
    nomes próprios (via NER) OU descrições de pessoa (via similaridade).
    Ex.: 'a triste senhora' -> {'chave': 'Senhora', 'genero': 'feminino', 'traco': 'triste'}

    exigir_sujeito=True filtra substantivos comuns que são só objeto/
    complemento da frase (ex.: 'ele escreveu para a Filha') - queremos só
    quem é sujeito, ou seja, protagonista daquela oração. Nomes próprios
    (NER) continuam valendo mesmo fora do papel de sujeito, pois são
    personagens de fato citados na obra.
    """
    # bloco curto demais (título, cabeçalho) não tem sujeito de verdade -
    # o NER erra muito nesses casos, então nem tentamos.
    if not texto.strip() or len(texto.split()) < 4:
        return []

    doc = nlp_model(texto)
    entidades = []

    for ent in doc.ents:
        if ent.label_ not in LABELS_FALANTE:
            continue
        if ent.text.lower().startswith("capítulo"):
            continue
        if ent.root.pos_ in ("VERB", "AUX"):
            continue
        if len(ent.text.split()) > 3:
            continue

        entidades.append({
            "chave": str(ent.text.strip().title()),
            "genero": _genero_por_morfologia(ent.root),
            "traco": "",
        })

    for token in doc:
        if not _eh_substantivo_humano(nlp_model, token):
            continue
        
        # CORREÇÃO 2: Ampliar as dependências aceitas. Personagens podem ser introduzidos como objetos (obj) 
        # ou complementos (obl, nmod) na narração antes de falarem (Ex: "levou os fiéis").
        dependencias_validas = ("nsubj", "appos", "obj", "obl", "nmod")
        if exigir_sujeito and token.dep_ not in dependencias_validas:
            continue
            
        entidades.append({
            "chave": str(token.lemma_.title()),  # Ajuda a identificar no console que foi inferido
            "genero": _genero_por_morfologia(token),
            "traco": _traco_emocional(nlp_model, token),
        })
        
    return entidades


def identificar_personagem(nlp_model, sentenca: str, estado: dict) -> tuple:
    """Descobre quem fala, cobrindo 3 situações comuns em texto literário:
      1) sujeito é nome próprio -> usa NER/dependência
      2) sujeito é pronome (ela/ele) -> usa a última entidade daquele gênero
      3) sujeito está oculto/elíptico (ex.: 'dizia consigo') -> usa a
         última entidade mencionada na narração, seja ela nomeada ou não
      4) sujeito é uma partícula/quantificador ("um", "algum", "nenhum") com o substantivo de verdade a um nível abaixo ("um dos FIÉIS")
    """
    if not sentenca:
        return None, None

    doc = nlp_model(sentenca)
    if not any(t.lemma_.lower() in VERBOS_ELOCUCAO_LEMMAS for t in doc):
        return None, None

    for token in doc:
        if token.lemma_.lower() not in VERBOS_ELOCUCAO_LEMMAS:
            continue

        sujeitos = [filho for filho in token.children if filho.dep_ == "nsubj"]

        if not sujeitos:
            if estado.get("ultima_entidade"):
                return estado["ultima_entidade"], "elipse_sujeito"
            continue

        for filho in sujeitos:
            texto_filho = filho.text.lower()
            # CORREÇÃO 3: pronome como sujeito ("o discurso QUE proferiu")
            if texto_filho in ("que", "quem", "o qual"):
                if estado.get("ultima_entidade"):
                    return estado["ultima_entidade"], "elipse_relativa"
            if texto_filho in PRONOMES_FEM and estado.get("ultimo_fem"):
                return estado["ultimo_fem"], "coref_fem"
            if texto_filho in PRONOMES_MASC and estado.get("ultimo_masc"):
                return estado["ultimo_masc"], "coref_masc"
            if filho.pos_ == "PROPN":
                return filho.text.title(), "nome_proprio"
            if _eh_substantivo_humano(nlp_model, filho):
                return filho.lemma_.title(), "descricao"
            
            # CORREÇÃO 4 (NOVA): sujeito é uma partícula tipo "um"/"algum"
            # e o substantivo humano de verdade está preso dentro dela
            # (ex.: "um DOS FIÉIS disse" -> "fiéis" é filho de "um"
            for neto in filho.children:
                if _eh_substantivo_humano(nlp_model, neto):
                    return neto.lemma_.title(), "sujeito_composto"
                
    return None, None


def extrair_tag_emocao(nlp_model, texto_narrador: str, traco_personagem: str = "") -> tuple:
    """Procura advérbios/adjetivos ligados ao verbo de elocução ou a
    palavras como 'voz'/'tom'. Se não achar nada, usa o traço emocional
    do personagem (adjetivo que o descreve, ex. 'triste') como reforço -
    é mais fraco, mas melhor que devolver neutro sem necessidade."""
    if not texto_narrador.strip() and not traco_personagem:
        return "neutral", "sem_narrador"

    doc = nlp_model(texto_narrador) if texto_narrador.strip() else None
    palavras = []

    if doc is not None:
        for token in doc:
            if token.lemma_.lower() in VERBOS_ELOCUCAO_LEMMAS:
                for filho in token.children:
                    if filho.pos_ == "ADV" and filho.text.lower() not in STOPWORDS_EMOCAO:
                        palavras.append(filho.text.lower())
            if token.text.lower() in PALAVRAS_TOM:
                for filho in token.children:
                    if filho.pos_ in ("ADJ", "ADV") and filho.text.lower() not in STOPWORDS_EMOCAO:
                        palavras.append(filho.text.lower())

    if not palavras and traco_personagem:
        palavras.append(traco_personagem)

    if not palavras:
        return "neutral", "sem_modificadores"

    tags, vistos = [], set()
    for pt_word in palavras:
        if pt_word in vistos:
            continue
        vistos.add(pt_word)
        try:
            traduzido = _tradutor_en.translate(pt_word).lower().replace(" ", "_")
            en_word = re.sub(r"[^a-z_]", "", traduzido)
        except Exception:
            en_word = ""
        if en_word:
            tags.append(en_word)

    return (", ".join(tags), "traduzido") if tags else ("neutral", "falha_traducao")
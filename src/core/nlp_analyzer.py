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

Todas as funções recebem um Doc já analisado: o pipeline roda o spaCy
UMA vez por trecho de narração e reaproveita o resultado.
"""
import spacy

from config import (
    VERBOS_ELOCUCAO_LEMMAS, VERBOS_ELOCUCAO_EXTRA_LEMMAS, ANCORAS_HUMANO, LIMIAR_SIMILARIDADE_HUMANO,
    PALAVRAS_TOM, CATEGORIAS_EMOCAO, LIMIAR_SIMILARIDADE_EMOCAO, LIMIAR_SIMILARIDADE_FORMA, STOPWORDS_EMOCAO,
    PRONOMES_FEM, PRONOMES_MASC, LABELS_FALANTE, MODELO_SPACY, PALAVRAS_IDADE, SUBSTANTIVOS_SEM_GENERO,
)

_TODAS_PALAVRAS_IDADE = set().union(*PALAVRAS_IDADE.values())

# Personagens podem ser introduzidos como sujeito, aposto, objeto ou
# complemento na narração antes de falarem (ex.: "levou os fiéis").
DEPS_PESSOA = ("nsubj", "appos", "obj", "obl", "nmod")


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
    return "desconhecido"


def _eh_substantivo_humano(token) -> bool:
    """Substitui uma lista fixa tipo {'senhora','velho','moça'...} por
    similaridade semântica com um punhado de âncoras genéricas.
    Aceita NOUN e também ADJ, porque em PT-BR é comum usar um adjetivo
    substantivado para se referir a uma pessoa (ex.: 'os fiéis', 'o velho').
    Palavras de idade ('velho', 'criança'...) já denotam pessoa, sem precisar de vetor."""
    if token.pos_ not in ("NOUN", "ADJ"):
        return False
    if token.lemma_.lower() in _TODAS_PALAVRAS_IDADE or token.text.lower() in _TODAS_PALAVRAS_IDADE:
        return True
    if not token.has_vector:
        return False
    for ancora in ANCORAS_HUMANO:
        ancora_tok = token.vocab[ancora]
        if ancora_tok.has_vector and token.similarity(ancora_tok) >= LIMIAR_SIMILARIDADE_HUMANO:
            return True
    return False


def _traco_emocional(token) -> str:
    """Pega um adjetivo que descreve diretamente a pessoa (ex.: 'a triste
    senhora' -> 'triste'), para usar como pista de emoção se a fala dela
    não tiver nenhuma outra pista mais direta."""
    for filho in token.children:
        if filho.dep_ == "amod" and filho.text.lower() not in STOPWORDS_EMOCAO:
            return filho.text.lower()
    return ""


def _idade_por_palavra(token) -> str | None:
    """Detecta a faixa etária só quando o texto diz explicitamente (ex.: 'o velho',
    'a criança', 'a senhora idosa'): olha a palavra que identifica a pessoa e o
    adjetivo que a descreve. Retorna 'idoso', 'crianca' ou None."""
    for palavra in [token] + [f for f in token.children if f.dep_ == "amod"]:
        formas = {palavra.lemma_.lower(), palavra.text.lower()}
        for faixa, conhecidas in PALAVRAS_IDADE.items():
            if formas & conhecidas:
                return faixa
    return None


def extrair_entidades_referenciais(doc) -> list:
    """Retorna candidatos a personagem citados num trecho de narração:
    nomes próprios (via NER) OU descrições de pessoa (via similaridade).
    Ex.: 'a triste senhora' -> {'chave': 'Senhora', 'genero': 'feminino', 'traco': 'triste'}
    """
    # bloco curto demais (título, cabeçalho) não tem sujeito de verdade -
    # o NER erra muito nesses casos, então nem tentamos.
    if len(doc.text.split()) < 2:
        return []

    entidades = []

    for ent in doc.ents:
        if (ent.label_ not in LABELS_FALANTE
                or ent.text.lower().startswith("capítulo")
                or ent.root.pos_ in ("VERB", "AUX")
                or len(ent.text.split()) > 3):
            continue
        entidades.append({
            "chave": ent.text.strip("!?,.;:\"' ").title(),
            "genero": _genero_por_morfologia(ent.root),
            "traco": "",
            "idade": None,
            "origem": "nome",
        })

    for token in doc:
        if token.dep_ not in DEPS_PESSOA or not _eh_substantivo_humano(token):
            continue
        entidades.append({
            "chave": token.lemma_.title(),  # ajuda a ver no console que foi inferido
            "genero": "desconhecido" if token.lemma_.lower() in SUBSTANTIVOS_SEM_GENERO else _genero_por_morfologia(token),
            "traco": _traco_emocional(token),
            "idade": _idade_por_palavra(token),
            "origem": "descricao",
        })

    return entidades


def entidade_do_falante(doc, chave: str) -> dict:
    """Gênero, traço e idade da pessoa 'chave' citada em 'doc'. Serve para registrar o
    falante no catálogo já com a voz certa, mesmo quando ele só é citado na etiqueta
    que vem DEPOIS da fala."""
    if doc is not None:
        for entidade in extrair_entidades_referenciais(doc):
            if entidade["chave"] == chave:
                return entidade
    return {"chave": chave, "genero": "desconhecido", "traco": "", "idade": None, "origem": "nome"}


def identificar_personagem(doc, estado: dict, etiqueta: bool = False) -> tuple:
    """Descobre quem fala (analisando a narração 'doc' que contém o verbo de
    elocução), cobrindo situações comuns em texto literário:
      1) sujeito é nome próprio -> usa NER/dependência
      2) sujeito é pronome (ela/ele) -> usa a última entidade daquele gênero
      3) sujeito oculto/elíptico (ex.: 'dizia consigo') -> usa a última
         entidade mencionada na narração, seja ela nomeada ou não
      4) sujeito é pronome relativo ("o discurso QUE proferiu") -> idem 3
      5) sujeito é quantificador ("um", "algum") com o substantivo de verdade
         um nível abaixo ("um dos FIÉIS")
    Se 'doc' é uma etiqueta de diálogo ("— Fala — esbravejou o idoso."), o primeiro verbo
    dela é o verbo de fala, qualquer que seja, e o sujeito posposto, que o spaCy costuma
    marcar como objeto ("gritou o velho"), é aceito como sujeito.
    Retorna (personagem, camada) ou (None, None).
    """
    if doc is None:
        return None, None

    ultima = estado.get("ultima_entidade")
    achou_verbo = False

    for token in doc:
        if token.lemma_.lower() not in VERBOS_ELOCUCAO_LEMMAS and not (etiqueta and token.pos_ == "VERB"):
            continue
        achou_verbo = True

        sujeitos = [filho for filho in token.children if filho.dep_ == "nsubj"]
        if not sujeitos and etiqueta:
            sujeitos = [f for f in token.children
                        if f.dep_ == "obj" and (f.pos_ == "PROPN" or _eh_substantivo_humano(f))]

        if not sujeitos:
            if ultima:
                return ultima, "elipse_sujeito"
            continue

        for filho in sujeitos:
            texto = filho.text.lower()
            if texto in ("que", "quem") and ultima:
                return ultima, "elipse_relativa"
            if texto in PRONOMES_FEM and estado.get("ultimo_fem"):
                return estado["ultimo_fem"], "coref_fem"
            if texto in PRONOMES_MASC and estado.get("ultimo_masc"):
                return estado["ultimo_masc"], "coref_masc"
            if filho.pos_ == "PROPN":
                return filho.text.strip("!?,.;:\"'").title(), "nome_proprio"
            if _eh_substantivo_humano(filho):
                return filho.lemma_.title(), "descricao"
            for neto in filho.children:
                if _eh_substantivo_humano(neto):
                    return neto.lemma_.title(), "sujeito_composto"

    # Há verbo de fala, mas o sujeito não bateu com nenhuma regra (ex.: "consigo",
    # que o spaCy às vezes marca como sujeito): trata como sujeito oculto.
    if achou_verbo and ultima:
        return ultima, "elipse_sujeito"
    return None, None


def _categoria_emocao_por_similaridade(vocab, palavra: str, limiar: float = LIMIAR_SIMILARIDADE_EMOCAO) -> str | None:
    """Compara 'palavra' (ex.: 'gritando', 'sussurrou') com a âncora de cada
    categoria de CATEGORIAS_EMOCAO por similaridade de vetor. Retorna a chave
    da categoria mais parecida (se passar do limiar) ou None."""
    token = vocab[palavra]
    if not token.has_vector:
        return None

    melhor_categoria, melhor_score = None, limiar
    for chave, info in CATEGORIAS_EMOCAO.items():
        ancora_tok = vocab[info["ancora"]]
        if not ancora_tok.has_vector:
            continue
        score = token.similarity(ancora_tok)
        if score >= melhor_score:
            melhor_categoria, melhor_score = chave, score
    return melhor_categoria


def _pistas_de_emocao(doc) -> tuple[list, list]:
    """Pistas de emoção numa narração vizinha à fala. Devolve (palavras, formas):
      - 'palavras' podem virar tag ou instrução de estilo: advérbios do verbo de elocução,
        adjetivos/advérbios ligados a 'voz'/'tom' e adjetivos ou particípios que descrevem
        quem fala ("disse Alice zangada", "exclamou a menina, assustada");
      - 'formas' só podem virar tag, porque não servem como instrução de estilo: o próprio
        verbo de elocução ("gritou", "sussurrou") e gerúndios ("respondeu rindo")."""
    palavras, formas = [], []
    for token in doc:
        if token.lemma_.lower() in VERBOS_ELOCUCAO_LEMMAS | VERBOS_ELOCUCAO_EXTRA_LEMMAS:
            formas.append(token.lemma_.lower())  # lema: 'gritou' -> 'gritar'
            # só advérbios de modo (terminados em "-mente"): "depois", "tanto", "sim" não dizem como a fala foi dita
            palavras += [f.text.lower() for f in token.children if f.pos_ == "ADV" and f.text.lower().endswith("mente")]
            alvos = [token] + [f for f in token.children if f.dep_ in ("nsubj", "obj")]
            for alvo in alvos:
                for f in alvo.children:
                    if f.dep_ not in ("amod", "acl", "advcl", "xcomp") or f.i == token.i:
                        continue
                    if f.pos_ == "ADJ" or (f.pos_ == "VERB" and "Part" in f.morph.get("VerbForm")):
                        palavras.append(f.text.lower())
                    elif f.pos_ == "VERB" and "Ger" in f.morph.get("VerbForm"):
                        formas.append(f.lemma_.lower())
        if token.text.lower() in PALAVRAS_TOM:
            palavras += [f.text.lower() for f in token.children if f.pos_ in ("ADJ", "ADV")]
    return palavras, formas


def extrair_tag_emocao(nlp_model, docs: list):
    """Junta pistas de emoção na narração vizinha à fala ('docs') e monta a instrução
    pro Gemini TTS em português (pt-BR tem suporte total no Gemini TTS, sem tradução).
    Sem pistas, a fala fica sem emoção (o traço do personagem foi descartado porque gerava
    palavras que não são emoção, como 'segunda' ou 'baixa').

    Duas saídas possíveis, que podem se combinar:
      - tag entre colchetes (ex.: '[shouting]') só pra um punhado de efeitos
        documentados pelo Google (grito, sussurro, riso...), reconhecidos por
        similaridade de vetor com uma âncora em português;
      - comando de estilo em português (ex.: 'Diga a fala a seguir com um tom
        triste') pra qualquer outro adjetivo emocional.

    Retorna {"estilo": str|None, "tags": [...]} ou None se não houver emoção.
    (Evita o bug do TG2: palavra traduzida e jogada crua entre colchetes,
    ex.: 'alta' -> '[high]', que não é tag válida e disparava PROHIBITED_CONTENT.)
    """
    palavras, formas = [], []
    for doc in docs:
        p, f = _pistas_de_emocao(doc)
        palavras += p
        formas += f

    palavras = [p for p in palavras if p not in STOPWORDS_EMOCAO]
    tags, palavra_estilo = [], None
    for palavra in dict.fromkeys(palavras + formas):  # sem repetidas, mantendo a ordem
        # verbos de elocução ficam todos perto uns dos outros no espaço vetorial ("dizer" ~ "gritar"),
        # então para o verbo e o gerúndio vale só uma similaridade bem alta (ou o próprio lema da âncora)
        limiar = LIMIAR_SIMILARIDADE_FORMA if palavra in formas and palavra not in palavras else LIMIAR_SIMILARIDADE_EMOCAO
        categoria = _categoria_emocao_por_similaridade(nlp_model.vocab, palavra, limiar)
        if categoria:
            tags.append(CATEGORIAS_EMOCAO[categoria]["tag"])
        elif palavra_estilo is None and palavra in palavras:
            # guarda só a primeira, pra não empilhar comandos de estilo
            # contraditórios na mesma fala (ex.: "triste" e "nervoso" juntos)
            palavra_estilo = palavra

    tags = list(dict.fromkeys(tags))
    if not tags and not palavra_estilo:
        return None

    estilo = f"Diga a fala a seguir com um tom {palavra_estilo}" if palavra_estilo else None
    return {"estilo": estilo, "tags": tags}

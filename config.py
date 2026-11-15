"""
Configurações centrais do projeto.
A síntese de voz usa o Vertex AI (faturamento do Google Cloud) para consumir o crédito do GCP.
"""
# ---------------------------------------------------------------- Google Cloud / TTS
# Projeto da conta de teste grátis (crédito). Fixo no código de propósito.
GCP_PROJECT_ID = "tg2system"
GCP_LOCATION = "us-central1"

# Flash para desenvolver/testar; Pro na geração final (custa o dobro).
# Para trocar de modelo, edite só esta linha: "gemini-2.5-flash-tts" ou "gemini-2.5-pro-tts".
MODELO_TTS = "gemini-2.5-pro-tts"
IDIOMA_TTS = "pt-BR"                # define idioma/sotaque no TTS (não precisa pedir no prompt)

LIMITE_CHARS_TTS = 800              # tamanho máx. de texto por chamada ao TTS
PAUSA_ENTRE_CHAMADAS_S = 6.5        # respeita o limite de requisições por minuto
MAX_TENTATIVAS = 3                  # só para erros temporários (429/5xx/sem áudio)
SILENCIO_ENTRE_SEGMENTOS_MS = 350

# Instrução enviada junto de TODO trecho que não tem estilo/idade (equivale ao
# "Say the following" do guia). Sem ela, trechos curtos como "dizia em voz alta."
# chegam ao modelo como texto cru e ele pode cortar palavras ou inventar fala.
DIRECAO_PADRAO = "Diga exatamente o texto a seguir, sem alterar palavras"

# ---------------------------------------------------------------- NLP
MODELO_SPACY = "pt_core_news_lg"

# Vozes do Gemini TTS. O serviço só classifica cada voz como feminina ou masculina
# (não existe voz neutra). Isso NÃO é um dicionário de personagens, é só o catálogo
# de vozes disponíveis no serviço - precisa continuar fixo.
BANCO_VOZES_GEMINI = {
    "narrador":     "Charon",
    # Vozes de adulto (a classificação por gênero é a da página do Gemini-TTS). A ordem importa:
    # as primeiras são as mais usadas.
    "feminino":     ["Aoede", "Zephyr", "Laomedeia", "Achernar", "Sulafat", "Erinome", "Kore"],
    "masculino":    ["Alnilam", "Orus", "Achird", "Enceladus", "Iapetus", "Rasalgethi", "Sadaltager", "Schedar"],
    # Gênero não identificado pelo spaCy (inclui o "Desconhecido"): vozes próprias,
    # para não repetir a voz de nenhum personagem de gênero definido.
    "desconhecido": ["Umbriel", "Callirrhoe"],
}

# Vozes por faixa etária, usadas quando a idade aparece de forma explícita no texto
# ("o velho", "a menina"). Escolhidas de ouvido; podem ser trocadas livremente. Se as vozes da
# faixa acabarem, o sistema usa as do adulto e, por fim, as das outras faixas do mesmo gênero.
VOZES_POR_IDADE = {
    ("feminino", "idoso"):    ["Gacrux", "Vindemiatrix", "Autonoe", "Pulcherrima"],
    ("masculino", "idoso"):   ["Sadachbia", "Zubenelgenubi", "Algenib", "Algieba"],
    ("feminino", "crianca"):  ["Leda", "Despina"],
    ("masculino", "crianca"): ["Fenrir", "Puck"],
    ("feminino", "jovem"):    ["Despina", "Leda"],
    ("masculino", "jovem"):   ["Puck", "Fenrir"],
}

# Lemmas (infinitivos) de verbos de elocução.
# Usar lemma em vez de forma conjugada cobre "disse", "dizia", "dirá" etc.
# de uma vez só - é o motivo do bug original (TG1 usava forma fixa).
VERBOS_ELOCUCAO_LEMMAS = {
    "dizer", "responder", "perguntar", "continuar", "retrucar", "gritar",
    "afirmar", "replicar", "discordar", "retomar", "chamar", "exclamar",
    "murmurar", "sussurrar", "falar", "começar", "acrescentar", "dirigir",
    "declarar", "confessar", "explicar", "exigir", "pensar", "indagar", 
    "comentar", "berrar", "esbravejar", "choramingar",
}

# Verbos de fala acrescentados depois da primeira avaliação. Só o text_parser os usa, para achar
# onde a fala termina; a atribuição do falante (nlp_analyzer) continua com a lista acima.
VERBOS_ELOCUCAO_EXTRA_LEMMAS = {
    "observar", "tornar", "interromper", "intervir", "prosseguir", "concordar", "suspirar",
    "insistir", "lembrar", "sugerir", "advertir", "bradar", "resmungar", "objetar", "protestar",
    "aconselhar", "completar", "concluir", "ponderar", "redarguir", "retorquir", "reclamar",
    "ordenar", "pedir", "implorar", "atalhar", "rosnar", "soluçar", "insinuar", "propor",
}

# Formas irregulares que as regras de conjugação do text_parser não geram sozinhas
# (o pretérito de "dizer", "intervir" e "propor" e o presente de "dizer").
FORMAS_VERBAIS_IRREGULARES = {"disse", "diz", "dizes", "dizem", "interveio", "propôs"}

# Âncoras semânticas para reconhecer substantivos que se referem a PESSOAS
# (ex.: "senhora", "velho", "moça") por similaridade de vetor de palavra,
# em vez de manter uma lista fixa dessas palavras.
ANCORAS_HUMANO = ["pessoa", "homem", "mulher"]
LIMIAR_SIMILARIDADE_HUMANO = 0.55

# Faixa etária só é detectada quando o texto diz EXPLICITAMENTE (lemma ou forma
# da palavra). Por vetor de palavra não funcionou: "senhora" ficava mais perto de
# "menina" do que de "idoso". Limitação a registrar no relatório.
PALAVRAS_IDADE = {
    "idoso":   {"idoso", "idosa", "velho", "velha", "ancião", "anciã"},
    "crianca": {"criança", "menino", "menina", "garoto", "garota", "menininho", "menininha"},
    "jovem":   {"jovem", "rapaz", "moço", "moça"},
}
# Palavras diferentes costumam designar a mesma pessoa ("o velho", "o ancião", "o idoso").
# Faixas do mesmo grupo são tratadas como a mesma pessoa (se o gênero for compatível).
GRUPO_IDADE = {"idoso": "idosos", "crianca": "jovens", "jovem": "jovens"}
# Substantivos cujo gênero gramatical não diz o gênero da pessoa ("a criança" pode ser menino).
SUBSTANTIVOS_SEM_GENERO = {"criança", "pessoa"}
# Referências genéricas ("o homem", "a mulher") normalmente retomam uma pessoa adulta já descrita.
# Papéis específicos ("a filha", "a senhora") não entram: podem ser pessoas diferentes.
SUBSTANTIVOS_GENERICOS = {"homem", "mulher"}
DESCRICOES_IDADE = {
    "idoso":   "Fale com voz de pessoa idosa",
    "crianca": "Fale com voz infantil",
    "jovem":   "Fale com voz jovem",
}

PALAVRAS_TOM = {"voz", "tom", "olhar", "expressão"}

# Tags oficiais do Gemini TTS (Modo 1 = som não-verbal, Modo 2 = modificador
# de estilo — nenhuma delas é falada pelo modelo, por isso são seguras).
# "ancora" é a palavra em português usada pra comparar por similaridade de
# vetor (mesma técnica do ANCORAS_HUMANO); "tag" é o texto oficial em
# colchetes; "estilo" é um reforço em linguagem natural, recomendado pela
# própria doc do Gemini pra aumentar a confiabilidade da tag.
CATEGORIAS_EMOCAO = {
    "grito":      {"ancora": "gritar",    "tag": "[shouting]",       "estilo": "Diga a fala a seguir gritando"},
    "sussurro":   {"ancora": "sussurrar", "tag": "[whispering]",     "estilo": "Diga a fala a seguir sussurrando"},
    "velocidade": {"ancora": "rápido",    "tag": "[extremely fast]", "estilo": "Fale rapidamente"},
    "riso":       {"ancora": "rir",       "tag": "[laughing]",       "estilo": "Reaja com uma risada"},
    "suspiro":    {"ancora": "suspirar",  "tag": "[sigh]",           "estilo": "Solte um suspiro"},
    "hesitacao":  {"ancora": "hesitar",   "tag": "[uhm]",            "estilo": "Fale com uma hesitação natural"},
    "sarcasmo":   {"ancora": "irônico",   "tag": "[sarcasm]",        "estilo": "Diga a fala a seguir com sarcasmo"},
}
LIMIAR_SIMILARIDADE_EMOCAO = 0.5
# Para o verbo de elocução e o gerúndio ("gritou", "rindo"): bem mais alto, porque os verbos de fala
# ficam todos próximos no espaço vetorial ("dizer" fica a 0,61 de "gritar").
LIMIAR_SIMILARIDADE_FORMA = 0.8

STOPWORDS_EMOCAO = {
    "muito", "bastante", "pouco", "tão", "quase", "apenas", "bem", "mal",
    "mais", "menos", "já", "ainda", "assim", "então", "aqui", "ali", "lá",
    "cá", "agora", "hoje", "ontem", "sempre", "nunca", "talvez", "realmente",
    "alta",  # "em voz alta" = em som audível, não é emoção
}

# Só "ela"/"ele" aparecem como sujeito (nsubj) de verdade; possessivos
# ("sua", "dele") nunca são sujeito, e "lhe" estava nas duas listas.
PRONOMES_FEM = {"ela"}
PRONOMES_MASC = {"ele"}
LABELS_FALANTE = {"PER", "ORG", "MISC"}
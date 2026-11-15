"""
Orquestra a ordem das chamadas entre os módulos. Não tem regra de NLP
nem de TTS aqui dentro - só decide "o que chamar, em que ordem".
"""
from src.core.pdf_processor import extrair_texto_pdf
from src.core.text_parser import parsear_texto, vizinhos_narracao, selecionar_atribuidor
from src.core.nlp_analyzer import (
    carregar_modelo, identificar_personagem, extrair_entidades_referenciais, extrair_tag_emocao,
    entidade_do_falante,
)
from src.core.catalog_manager import (
    criar_catalogo, criar_estado_saliencia, registrar_personagem, atualizar_saliencia, resolver_alias,
)


def processar_pipeline(caminho_pdf: str, capitulo: str | None = None):
    texto = extrair_texto_pdf(caminho_pdf, capitulo)
    nlp = carregar_modelo()
    blocos = parsear_texto(texto, nlp)

    # Cada trecho de narração é analisado pelo spaCy uma única vez e o
    # resultado é reaproveitado (entidades, quem fala e emoção).
    indices = [i for i, b in enumerate(blocos) if b["tipo"] == "narrador"]
    docs = dict(zip(indices, nlp.pipe(blocos[i]["texto"] for i in indices)))

    catalogo = criar_catalogo()
    estado = criar_estado_saliencia()

    for i, bloco in enumerate(blocos):
        if bloco["tipo"] == "narrador":
            # Toda menção a pessoa na narração (nomeada ou não) atualiza
            # quem é "a entidade mais recente" - é isso que resolve o
            # sujeito elíptico ("dizia consigo") mais adiante.
            if not bloco.get("e_cabecalho"):
                atualizar_saliencia(extrair_entidades_referenciais(docs[i]), estado, catalogo)
            continue

        antes, depois = vizinhos_narracao(blocos, i)
        atribuidor = selecionar_atribuidor(blocos, antes, depois)

        etiqueta = atribuidor is not None and blocos[atribuidor].get("e_etiqueta", False)
        personagem, camada = identificar_personagem(docs.get(atribuidor), estado, etiqueta)
        personagem = personagem or estado["ultima_entidade"] or "Desconhecido"

        if personagem not in catalogo:
            # Primeira aparição do personagem é como falante: registra com os dados que a
            # própria etiqueta traz (gênero, idade) e reaproveita quem já existe com outro nome.
            entidade = entidade_do_falante(docs.get(atribuidor), personagem)
            personagem = resolver_alias(entidade, catalogo)
            registrar_personagem(personagem, entidade["genero"], catalogo,
                                 entidade["traco"], entidade["idade"], entidade["origem"])

        contexto = [docs[j] for j in (antes, depois) if j is not None]
        bloco["personagem"] = personagem
        bloco["camada_attr"] = camada or "fallback"
        bloco["emocao"] = extrair_tag_emocao(nlp, contexto)

    return blocos, catalogo
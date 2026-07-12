"""
Orquestra a ordem das chamadas entre os módulos. Não tem regra de NLP
nem de TTS aqui dentro - só decide "o que chamar, em que ordem".
"""
from src.core.pdf_processor import extrair_texto_pdf
from src.core.text_parser import parsear_texto, selecionar_atribuidor
from src.core.nlp_analyzer import (
    carregar_modelo, identificar_personagem,
    extrair_entidades_referenciais, extrair_tag_emocao,
)
from src.core.catalog_manager import criar_catalogo, criar_estado_saliencia, registrar_personagem, atualizar_saliencia


def processar_pipeline(caminho_pdf: str, modo_dialogo: str = "auto"):
    texto = extrair_texto_pdf(caminho_pdf)

    nlp = carregar_modelo()
    blocos = parsear_texto(texto, modo=modo_dialogo)

    catalogo = criar_catalogo()
    estado = criar_estado_saliencia()

    for i, bloco in enumerate(blocos):
        if bloco["tipo"] == "narrador":
                # Toda menção a pessoa na narração (nomeada ou não) atualiza
                # quem é "a entidade mais recente" - é isso que resolve o
                # sujeito elíptico ("dizia consigo") mais adiante.
            if not bloco.get("e_cabecalho"):
                entidades = extrair_entidades_referenciais(nlp, bloco["texto"])
                atualizar_saliencia(entidades, estado, catalogo)
            continue

        atribuidor = selecionar_atribuidor(blocos, i)
        antes = blocos[i - 1]["texto"] if i > 0 and blocos[i - 1]["tipo"] == "narrador" else ""
        depois = blocos[i + 1]["texto"] if i + 1 < len(blocos) and blocos[i + 1]["tipo"] == "narrador" else ""

        personagem, camada = identificar_personagem(nlp, atribuidor, estado)
        personagem = personagem or estado.get("ultima_entidade") or "Desconhecido"

        if personagem not in catalogo:
            registrar_personagem(personagem, "neutro", catalogo)

        bloco["personagem"] = personagem
        bloco["camada_attr"] = camada or "fallback"

        traco = catalogo.get(personagem, {}).get("traco", "")
        tag, fonte = extrair_tag_emocao(nlp, f"{antes} {depois}".strip(), traco_personagem=traco)
        bloco["emocao"] = tag
        bloco["fonte_emocao"] = fonte

    return blocos, catalogo